import sys
import os
import subprocess

# Auto-shim: aspose-cad requires Python <= 3.13.
# If invoked on Python 3.14+, automatically delegates to Python 3.13 or 3.12:
if sys.version_info >= (3, 14):
    import shutil
    py_launcher = shutil.which("py")
    if py_launcher:
        for ver in ["-3.13", "-3.12", "-3.11"]:
            try:
                res = subprocess.run([py_launcher, ver, "-c", "import aspose.cad"], capture_output=True)
                if res.returncode == 0:
                    code = subprocess.call([py_launcher, ver] + sys.argv)
                    sys.exit(code)
            except Exception:
                pass

    user_home = os.path.expanduser("~")
    for candidate in [
        os.path.join(user_home, r"AppData\Local\Programs\Python\Python313\python.exe"),
        os.path.join(user_home, r"Python312\python.exe"),
        r"C:\Python313\python.exe",
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
    ]:
        if os.path.exists(candidate):
            code = subprocess.call([candidate] + sys.argv)
            sys.exit(code)

    print("ERROR: aspose-cad requires Python <= 3.13. Please run using Python 3.12 or 3.13.")
    sys.exit(1)

import re
import struct
import aspose.cad as cad
from aspose.cad.imageoptions import CadRasterizationOptions, PdfOptions, RasterizationQualityValue
import pymupdf


PAGE_SIZES = {
    '1': ('A1', 2384.0, 1684.0, "A1 Architectural (Recommended for clarity)"),
    '2': ('A4', 842.0, 595.0, "A4 Standard"),
    '3': ('A3', 1191.0, 842.0, "A3 Standard"),
    '4': ('A0', 3370.0, 2384.0, "A0 Large Format"),
    '5': ('Letter', 792.0, 612.0, "US Letter"),
}

THEMES = {
    '1': ('white', "White (Standard Clean Print)"),
    '2': ('blueprint', "Blueprint Blue (Classic CAD Blueprint)"),
    '3': ('dark', "Dark CAD Station (Workstation Dark)"),
    '4': ('cream', "Architectural Cream (Warm Parchment)"),
}


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


def clean_pdf_watermark(pdf_path):
    """
    Strips evaluation watermark artifacts to ensure a 100% clean CAD PDF.
    Removes full-sheet dashed diagonal cross lines, evaluation banner boxes,
    and text without leaving solid redaction marks on dark or blueprint themes.
    """
    doc = pymupdf.open(pdf_path)
    for page in doc:
        # Transparent text redactions to prevent solid black boxes on dark/blueprint themes
        for pattern in ['Evaluation only', 'Created with Aspose', 'Aspose Pty Ltd']:
            for rect in page.search_for(pattern):
                page.add_redact_annot(rect, fill=False)
        page.apply_redactions()

        for xref in page.get_contents():
            stream = doc.xref_stream(xref).decode('latin1', errors='ignore')
            cut_idx = None

            # 1. Dashed diagonal cross watermark (covers both black and white cross passes)
            # Matches: 'q <color> RG <linewidth> w [<dash> <dash>] <phase> d 0 0 m'
            m = re.search(r'q\s+[0-9\.\s]+RG\s+[0-9\.]+\s+w\s*\[[0-9\.\s]+\]\s*[0-9\.]*\s*d\s*0\s+0\s+m', stream)
            if m:
                cut_idx = m.start()
            else:
                # Fallback: dashed line starting directly at origin (0, 0)
                m = re.search(r'\[[0-9\.\s]+\]\s*[0-9\.]*\s*d\s*0\s+0\s+m', stream)
                if m:
                    q_idx = stream.rfind('q', 0, m.start())
                    cut_idx = q_idx if q_idx != -1 else m.start()
                else:
                    # Watermark evaluation banner background box starting at (0, 0)
                    m = re.search(r'q\s+[0-9\.\s]+r[gG]\s+[0-9\.\s]*[rRgG]\s*0\s+0\s+m\s+[0-9\.]+\s+0\s+l', stream)
                    if m:
                        cut_idx = m.start()
                    else:
                        idx = stream.rfind('q 1 1 1 RG')
                        if idx != -1:
                            cut_idx = idx

            if cut_idx is not None:
                clean_stream = stream[:cut_idx].strip()
                tokens = clean_stream.split()
                q_cnt = tokens.count('q')
                Q_cnt = tokens.count('Q')
                if Q_cnt < q_cnt:
                    clean_stream += ' ' + ' '.join(['Q'] * (q_cnt - Q_cnt))
                doc.update_stream(xref, clean_stream.encode('latin1'))

    temp_path = pdf_path + '.clean.tmp'
    doc.save(temp_path)
    doc.close()

    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    os.rename(temp_path, pdf_path)


THEME_BG_COLORS = {
    'blueprint': (12 / 255.0, 36 / 255.0, 70 / 255.0),
    'dark': (18 / 255.0, 24 / 255.0, 38 / 255.0),
    'cream': (252 / 255.0, 250 / 255.0, 242 / 255.0),
    'white': (1.0, 1.0, 1.0),
}


def normalize_pdf_page_size(pdf_path, target_w, target_h, theme='white'):
    """
    Normalizes PDF page dimensions to the requested target size (e.g. A1, A3, A4).
    MicroStation DGN files (especially V7 in master units/UOR) often cause Aspose.CAD
    to export giant raw coordinate canvases (e.g. 14,000+ pt / 200 inches wide),
    ignoring rasterization page dimensions. When opened in Microsoft Edge or Google Chrome,
    extreme zoom-out causes hairline strokes to disappear below subpixel thresholds,
    rendering pages completely blank.
    This function embeds the vector drawing into standard architectural page rects,
    centering it with exact margins and matching background theme.
    """
    if not os.path.exists(pdf_path):
        return False

    try:
        doc = pymupdf.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return False

        src_page = doc[0]
        src_rect = src_page.rect
        w_diff = abs(src_rect.width - target_w) / max(1.0, target_w)
        h_diff = abs(src_rect.height - target_h) / max(1.0, target_h)

        # If already matching target within 2%, no resizing needed
        if w_diff < 0.02 and h_diff < 0.02:
            doc.close()
            return True

        bg_color = THEME_BG_COLORS.get((theme or 'white').lower(), (1.0, 1.0, 1.0))

        new_doc = pymupdf.open()
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            rect = page.rect
            scale = min(target_w / max(1.0, rect.width), target_h / max(1.0, rect.height))
            scaled_w = rect.width * scale
            scaled_h = rect.height * scale
            offset_x = (target_w - scaled_w) / 2.0
            offset_y = (target_h - scaled_h) / 2.0
            dest_rect = pymupdf.Rect(offset_x, offset_y, offset_x + scaled_w, offset_y + scaled_h)

            new_page = new_doc.new_page(width=target_w, height=target_h)
            if bg_color:
                new_page.draw_rect(new_page.rect, color=None, fill=bg_color)
            new_page.show_pdf_page(dest_rect, doc, page_idx)

        temp_norm = pdf_path + '.norm.tmp'
        new_doc.save(temp_norm, deflate=True)
        new_doc.close()
        doc.close()

        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        os.rename(temp_norm, pdf_path)
        return True
    except Exception as e:
        print(f"Warning during PDF page normalization: {e}")
        return False


def convert_dgn_to_pdf(input_dgn_path, output_pdf_path=None, page_width=2384.0, page_height=1684.0, theme='white', line_scale=0.35):
    """
    Converts a MicroStation DGN file (V7 or V8) into a high-precision,
    vector-sharp PDF with customizable page sizes, themes, and fine lines.
    """
    if not os.path.exists(input_dgn_path):
        raise FileNotFoundError(f"DGN file not found: {input_dgn_path}")

    if not output_pdf_path:
        output_pdf_path = os.path.splitext(input_dgn_path)[0] + '.pdf'

    # Pre-flight sanitizer eliminates exponential cell recursion hangs on V7 files
    dgn_to_load = sanitize_dgn_file(input_dgn_path)

    print(f"\n[1/3] Loading DGN: {input_dgn_path}...")
    try:
        load_opts = cad.LoadOptions()
        try:
            load_opts.ignore_errors = True
        except Exception:
            pass
        cad_image = cad.Image.load(dgn_to_load, load_opts)
    finally:
        if dgn_to_load != input_dgn_path and os.path.exists(dgn_to_load):
            try:
                os.remove(dgn_to_load)
            except OSError:
                pass

    # 1. Canvas Dimensions & Scaling
    raster_opts = CadRasterizationOptions()
    raster_opts.page_width = float(page_width)
    raster_opts.page_height = float(page_height)
    raster_opts.automatic_layouts_scaling = True
    raster_opts.no_scaling = False

    # 2. Theme Background Color
    theme = (theme or 'white').lower()
    if theme == 'blueprint':
        raster_opts.background_color = cad.Color.from_argb(255, 12, 36, 70)
    elif theme == 'dark':
        raster_opts.background_color = cad.Color.from_argb(255, 18, 24, 38)
    elif theme == 'cream':
        raster_opts.background_color = cad.Color.from_argb(255, 252, 250, 242)
    else:
        raster_opts.background_color = cad.Color.white

    # 3. Fine Line Weight Scaling (Prevents thick line bleeding)
    raster_opts.line_scale = float(line_scale)

    # 4. Text & Vector Graphics Anti-Aliasing
    try:
        raster_opts.graphics_options.smoothing_mode = cad.SmoothingMode.HIGH_QUALITY
        raster_opts.graphics_options.text_rendering_hint = cad.TextRenderingHint.ANTI_ALIAS_GRID_FIT
        raster_opts.graphics_options.interpolation_mode = cad.InterpolationMode.HIGH_QUALITY_BICUBIC
    except Exception:
        pass

    # 5. High-Precision Quality & Text Thickness Normalization
    try:
        raster_opts.quality.text = RasterizationQualityValue.HIGH
        raster_opts.quality.text_thickness_normalization = True
        raster_opts.quality.objects_precision = RasterizationQualityValue.HIGH
        raster_opts.quality.arc = RasterizationQualityValue.HIGH
        raster_opts.quality.hatch = RasterizationQualityValue.HIGH
    except Exception:
        pass

    # 6. Export to Vector PDF
    pdf_opts = PdfOptions()
    pdf_opts.vector_rasterization_options = raster_opts

    temp_pdf = output_pdf_path + '.raw.pdf'
    print(f"[2/3] Generating vector PDF (Theme: {theme.title()})...")
    cad_image.save(temp_pdf, pdf_opts)

    print("[3/3] Normalizing vectors and removing watermark...")
    clean_pdf_watermark(temp_pdf)
    if os.path.exists(output_pdf_path):
        os.remove(output_pdf_path)
    os.rename(temp_pdf, output_pdf_path)

    normalize_pdf_page_size(output_pdf_path, float(page_width), float(page_height), theme=theme)

    file_size_mb = os.path.getsize(output_pdf_path) / (1024 * 1024)
    print(f"\n SUCCESS! Clean vector PDF created:")
    print(f" -> File: {output_pdf_path} ({file_size_mb:.2f} MB)")
    return output_pdf_path


def select_file_dialog():
    """Opens a native Windows File Explorer dialog to choose a DGN file."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        print("Opening file browser... Select your .dgn file.")
        file_path = filedialog.askopenfilename(
            title="Select MicroStation DGN File to Convert",
            filetypes=[
                ("MicroStation DGN Files", "*.dgn"),
                ("All Files", "*.*")
            ]
        )
        root.destroy()
        return file_path
    except Exception:
        return None


def prompt_options():
    """Prompts the user to select page size and color theme with safe defaults."""
    try:
        print("\n" + "-" * 50)
        print(" Select Page Size:")
        for key, (name, _, _, desc) in PAGE_SIZES.items():
            print(f"   [{key}] {desc}")
        size_choice = input(" Choose [1-5] (Press Enter for [1] A1): ").strip()
        size_info = PAGE_SIZES.get(size_choice, PAGE_SIZES['1'])
        page_name, page_w, page_h, _ = size_info

        print("\n Select Color Theme:")
        for key, (code, desc) in THEMES.items():
            print(f"   [{key}] {desc}")
        theme_choice = input(" Choose [1-4] (Press Enter for [1] White): ").strip()
        theme_code, _ = THEMES.get(theme_choice, THEMES['1'])
    except (EOFError, KeyboardInterrupt):
        page_name, page_w, page_h, _ = PAGE_SIZES['1']
        theme_code = 'white'
        print("\n Using default: A1 Architectural, White Theme.")

    print("-" * 50)
    print(f" Configured: Size={page_name}, Theme={theme_code.title()}")
    return page_w, page_h, theme_code


def lookup_size_and_theme(size_arg=None, theme_arg=None):
    """Resolves page width/height and theme from string names or aliases."""
    pw, ph = PAGE_SIZES['1'][1], PAGE_SIZES['1'][2]
    if size_arg:
        size_clean = size_arg.strip().upper()
        for key, (name, w, h, _) in PAGE_SIZES.items():
            if size_clean == name.upper() or size_clean == key:
                pw, ph = w, h
                break

    theme_code = 'white'
    if theme_arg:
        t_clean = theme_arg.strip().lower()
        for key, (code, _) in THEMES.items():
            if t_clean == code.lower() or t_clean == key:
                theme_code = code
                break

    return pw, ph, theme_code


if __name__ == '__main__':
    selected_dgn = None
    output_pdf = None
    cli_size = None
    cli_theme = None

    # Parse CLI arguments if provided:
    # Usage: python dgn_to_pdf.py [input.dgn] [output.pdf] [size] [theme]
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) >= 1:
        selected_dgn = args[0].strip('"\'')
    if len(args) >= 2:
        output_pdf = args[1].strip('"\'')
    if len(args) >= 3:
        cli_size = args[2].strip()
    if len(args) >= 4:
        cli_theme = args[3].strip()

    # Check for --size and --theme flags
    for i, a in enumerate(sys.argv):
        if a in ('--size', '-s') and i + 1 < len(sys.argv):
            cli_size = sys.argv[i + 1]
        elif a in ('--theme', '-t') and i + 1 < len(sys.argv):
            cli_theme = sys.argv[i + 1]

    # If no file was passed via CLI, open Windows File Explorer picker
    if not selected_dgn:
        selected_dgn = select_file_dialog()

    # Terminal fallback if file dialog was cancelled or unavailable
    if not selected_dgn:
        try:
            user_input = input("\nEnter path or Drag & Drop your .dgn file here: ").strip('"\'')
            if user_input:
                selected_dgn = user_input
        except (EOFError, KeyboardInterrupt):
            pass

    if selected_dgn and os.path.exists(selected_dgn):
        print(f"\nSelected file: {os.path.basename(selected_dgn)}")

        # If size & theme specified via CLI, use them directly; otherwise prompt interactively
        if cli_size or cli_theme:
            pw, ph, theme = lookup_size_and_theme(cli_size, cli_theme)
            print(f"CLI Configured: Size={cli_size or 'A1'}, Theme={theme.title()}")
        else:
            pw, ph, theme = prompt_options()

        result_pdf = convert_dgn_to_pdf(selected_dgn, output_pdf, page_width=pw, page_height=ph, theme=theme)

        # Automatically open the generated PDF on Windows
        try:
            if sys.platform == 'win32':
                os.startfile(result_pdf)
        except Exception:
            pass
    else:
        print("\nNo file was selected or file does not exist. Exiting.")

