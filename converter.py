"""
DGN to PDF Conversion and Vector Normalization Engine
Supports MicroStation DGN V7 and V8 format conversion with clean vector output.
Includes isolated-process execution for thread and COM memory safety.
Configured with High-Precision CAD rendering and Text Normalization.
"""

import os
import sys

# Ensure .NET Core globalization invariant mode on Linux (fixes missing ICU package crash)
os.environ["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"
os.environ["COMPlus_GlobalizationInvariant"] = "1"

import time
import json
import struct
import subprocess
import traceback
import pymupdf
import olefile

try:
    import aspose.cad as cad
    from aspose.cad.imageoptions import CadRasterizationOptions, PdfOptions, RasterizationQualityValue
    ASPOSE_AVAILABLE = True
except ImportError:
    ASPOSE_AVAILABLE = False


PAPER_DIMENSIONS = {
    'A4': (842.0, 595.0),
    'A3': (1191.0, 842.0),
    'A2': (1684.0, 1191.0),
    'A1': (2384.0, 1684.0),
    'A0': (3370.0, 2384.0),
    'Letter': (792.0, 612.0),
    'Legal': (1008.0, 612.0),
    'Tabloid': (1224.0, 792.0),
    'Auto': (1600.0, 1200.0),
}


def detect_dgn_info(file_path):
    """Detects DGN format version and structural metadata."""
    if not os.path.exists(file_path):
        return {'valid': False, 'error': 'File not found'}

    size_bytes = os.path.getsize(file_path)
    info = {
        'valid': True,
        'size_bytes': size_bytes,
        'size_formatted': format_size(size_bytes),
        'filename': os.path.basename(file_path),
        'version': 'MicroStation DGN',
        'is_v8_ole': False,
        'is_v7_isff': False,
    }

    try:
        with open(file_path, 'rb') as f:
            header = f.read(64)

        if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
            info['version'] = 'MicroStation DGN V8'
            info['is_v8_ole'] = True
        elif len(header) >= 4:
            b1 = header[1]
            elem_type = b1 & 0x7F
            if elem_type in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 66):
                info['version'] = 'MicroStation DGN V7 (ISFF)'
                info['is_v7_isff'] = True
    except Exception as e:
        info['read_error'] = str(e)

    return info


def format_size(num_bytes):
    """Formats bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def get_paper_size(paper_name='A4', orientation='auto', img_aspect=1.33):
    """Calculates width and height according to paper size and orientation."""
    base_w, base_h = PAPER_DIMENSIONS.get(paper_name, PAPER_DIMENSIONS['A4'])
    max_d = max(base_w, base_h)
    min_d = min(base_w, base_h)

    if orientation == 'landscape':
        return max_d, min_d
    elif orientation == 'portrait':
        return min_d, max_d
    else:  # auto
        if img_aspect >= 1.0:
            return max_d, min_d
        else:
            return min_d, max_d


def clean_cad_watermark(pdf_path, output_pdf_path=None):
    """Strips out evaluation watermark vectors and text from CAD-generated PDF."""
    if output_pdf_path is None:
        output_pdf_path = pdf_path

    doc = pymupdf.open(pdf_path)
    try:
        for page in doc:
            for text_pattern in ['Evaluation only', 'Created with Aspose', 'Aspose Pty Ltd']:
                for rect in page.search_for(text_pattern):
                    page.add_redact_annot(rect)
                    page.apply_redactions()

            for xref in page.get_contents():
                stream = doc.xref_stream(xref).decode('latin1', errors='ignore')
                idx = stream.rfind('q 1 1 1 RG')
                if idx != -1:
                    clean_stream = stream[:idx].strip()
                    tokens = clean_stream.split()
                    q_cnt = tokens.count('q')
                    Q_cnt = tokens.count('Q')
                    if Q_cnt < q_cnt:
                        clean_stream += ' ' + ' '.join(['Q'] * (q_cnt - Q_cnt))
                    doc.update_stream(xref, clean_stream.encode('latin1'))

        temp_out = output_pdf_path + '.clean.tmp'
        doc.save(temp_out)
        doc.close()
        if os.path.exists(output_pdf_path):
            os.remove(output_pdf_path)
        os.rename(temp_out, output_pdf_path)
        return True
    except Exception as e:
        print(f"Warning during PDF watermark cleaning: {e}")
        doc.close()
        return False


def generate_pdf_thumbnail(pdf_path, thumb_path, max_dim=1200):
    """Renders a crisp thumbnail preview of the first page of the PDF."""
    try:
        doc = pymupdf.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return False

        page = doc[0]
        rect = page.rect
        w = max(1.0, rect.width)
        h = max(1.0, rect.height)
        scale = max_dim / max(w, h)
        mat = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(thumb_path)
        doc.close()
        return True
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return False


def sanitize_dgn_file(input_path):
    """
    Pre-flight optimization for MicroStation DGN files (especially V7 ISFF).
    Fixes nested cell recursion anomalies where Type 2 (Cell Header) elements
    with the complex bit set cause CAD parsers to freeze or enter O(N^2) loops.
    Returns: sanitized_path (or original input_path if no changes needed).
    """
    if not os.path.exists(input_path):
        return input_path

    try:
        with open(input_path, 'rb') as f:
            header = f.read(4)

        # Only applies to V7 ISFF files (not V8 OLE compound files)
        if header.startswith(b'\xd0\xcf\x11\xe0'):
            return input_path

        with open(input_path, 'rb') as f:
            data = bytearray(f.read())

        offset = 0
        modified = False
        data_len = len(data)

        while offset + 4 <= data_len:
            w0, words = struct.unpack_from('<HH', data, offset)
            if w0 == 0xFFFF:  # ISFF EOF marker
                break

            elem_type = (w0 >> 8) & 0x7F
            elem_len = (words + 2) * 2

            if elem_len <= 0:
                break

            # Type 2: Cell Header
            # If the complex bit (0x0080) is set, Aspose CAD attempts recursive tree
            # reconstruction on subsequent elements, causing exponential hang times.
            if elem_type == 2 and (w0 & 0x0080):
                struct.pack_into('<H', data, offset, w0 & ~0x0080)
                modified = True

            offset += elem_len

        if modified:
            sanitized_path = input_path + '.opt.tmp'
            with open(sanitized_path, 'wb') as f:
                f.write(data)
            return sanitized_path

        return input_path
    except Exception as e:
        print(f"Warning in DGN pre-flight sanitizer: {e}", file=sys.stderr)
        return input_path


def convert_dgn_direct(input_path, output_pdf_path, thumb_path=None, options=None):
    """Direct conversion routine with High-Precision CAD vector and font tuning."""
    if not ASPOSE_AVAILABLE:
        raise RuntimeError("Aspose.CAD library is not loaded.")

    if options is None:
        options = {}

    paper_name = options.get('paper_size', 'A4')
    orientation = options.get('orientation', 'auto')
    theme = options.get('theme', 'white')

    start_time = time.time()
    dgn_meta = detect_dgn_info(input_path)

    # Pre-flight sanitizer eliminates exponential cell recursion hangs on V7 files
    dgn_to_load = sanitize_dgn_file(input_path)
    try:
        print(f"Loading CAD image from {input_path}...", file=sys.stderr)
        image = cad.Image.load(dgn_to_load)
    finally:
        if dgn_to_load != input_path and os.path.exists(dgn_to_load):
            try:
                os.remove(dgn_to_load)
            except OSError:
                pass

    load_time = time.time() - start_time

    img_aspect = (image.width / image.height) if (image.height and image.height > 0) else 1.33
    target_w, target_h = get_paper_size(paper_name, orientation, img_aspect)

    raster_opts = CadRasterizationOptions()
    raster_opts.page_width = float(target_w)
    raster_opts.page_height = float(target_h)
    raster_opts.automatic_layouts_scaling = True
    raster_opts.no_scaling = False
    
    # Line scale tuning: fine lines prevent dense walls from smearing
    raster_opts.line_scale = 0.35

    # Text rendering hint & smoothing mode for crisp typography and clean arcs
    try:
        raster_opts.graphics_options.smoothing_mode = cad.SmoothingMode.HIGH_QUALITY
        raster_opts.graphics_options.text_rendering_hint = cad.TextRenderingHint.ANTI_ALIAS_GRID_FIT
        raster_opts.graphics_options.interpolation_mode = cad.InterpolationMode.HIGH_QUALITY_BICUBIC
    except Exception:
        pass

    # High-precision rendering quality & sharp font normalization
    try:
        raster_opts.quality.text = RasterizationQualityValue.HIGH
        raster_opts.quality.text_thickness_normalization = True
        raster_opts.quality.objects_precision = RasterizationQualityValue.HIGH
        raster_opts.quality.arc = RasterizationQualityValue.HIGH
        raster_opts.quality.hatch = RasterizationQualityValue.HIGH
    except Exception:
        pass

    if theme == 'blueprint':
        raster_opts.background_color = cad.Color.from_argb(255, 12, 36, 70)
    elif theme == 'dark':
        raster_opts.background_color = cad.Color.from_argb(255, 18, 24, 38)
    elif theme == 'cream':
        raster_opts.background_color = cad.Color.from_argb(255, 252, 250, 242)
    else:
        raster_opts.background_color = cad.Color.white

    pdf_opts = PdfOptions()
    pdf_opts.vector_rasterization_options = raster_opts

    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
    temp_raw_pdf = output_pdf_path + '.raw.pdf'
    image.save(temp_raw_pdf, pdf_opts)

    clean_cad_watermark(temp_raw_pdf, output_pdf_path)
    if os.path.exists(temp_raw_pdf):
        try:
            os.remove(temp_raw_pdf)
        except OSError:
            pass

    thumb_generated = False
    if thumb_path:
        os.makedirs(os.path.dirname(os.path.abspath(thumb_path)), exist_ok=True)
        thumb_generated = generate_pdf_thumbnail(output_pdf_path, thumb_path)

    total_time = time.time() - start_time

    doc = pymupdf.open(output_pdf_path)
    page_count = len(doc)
    page_rect = doc[0].rect if page_count > 0 else None
    drawings_count = len(doc[0].get_drawings()) if page_count > 0 else 0
    doc.close()

    result_meta = {
        'success': True,
        'dgn_version': dgn_meta.get('version', 'DGN'),
        'input_size': os.path.getsize(input_path),
        'input_size_formatted': format_size(os.path.getsize(input_path)),
        'output_size': os.path.getsize(output_pdf_path),
        'output_size_formatted': format_size(os.path.getsize(output_pdf_path)),
        'page_count': page_count,
        'page_width': round(page_rect.width, 1) if page_rect else target_w,
        'page_height': round(page_rect.height, 1) if page_rect else target_h,
        'vector_elements_count': drawings_count,
        'paper_size': paper_name,
        'orientation': orientation,
        'theme': theme,
        'load_time_seconds': round(load_time, 2),
        'total_time_seconds': round(total_time, 2),
        'has_thumbnail': thumb_generated
    }

    return result_meta


def convert_dgn(input_path, output_pdf_path, thumb_path=None, options=None, isolated=True):
    """
    Main conversion entrypoint.
    Executes conversion in an isolated process to guarantee clean memory,
    main thread execution, and COM/OLE stability on Windows.
    """
    if not isolated:
        return convert_dgn_direct(input_path, output_pdf_path, thumb_path, options)

    python_exe = sys.executable
    script_path = os.path.abspath(__file__)
    opts_json = json.dumps(options or {})
    thumb_arg = thumb_path or "NONE"

    cmd = [python_exe, script_path, input_path, output_pdf_path, thumb_arg, opts_json]

    sub_env = os.environ.copy()
    sub_env["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"
    sub_env["COMPlus_GlobalizationInvariant"] = "1"

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=sub_env)

    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or proc.stdout.strip() or f"Process exited with code {proc.returncode}"
        raise RuntimeError(f"CAD Conversion Error: {err_msg}")

    output_lines = [line.strip() for line in proc.stdout.strip().split('\n') if line.strip()]
    if not output_lines:
        raise RuntimeError("No output received from conversion process.")

    try:
        return json.loads(output_lines[-1])
    except json.JSONDecodeError:
        raise RuntimeError(f"Failed to parse conversion result: {proc.stdout}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: converter.py <input_dgn> <output_pdf> [thumb_png] [options_json]", file=sys.stderr)
        sys.exit(1)

    in_file = sys.argv[1]
    out_file = sys.argv[2]
    thumb_file = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "NONE" else None
    opts = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}

    try:
        res = convert_dgn_direct(in_file, out_file, thumb_file, opts)
        print(json.dumps(res))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
