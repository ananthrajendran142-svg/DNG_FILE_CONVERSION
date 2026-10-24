"""
Simple Python Flask Server for DGN to PDF Conversion
"""

import os
import sys

# Ensure .NET Core globalization invariant mode on Linux (fixes missing ICU package crash)
os.environ["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"
os.environ["COMPlus_GlobalizationInvariant"] = "1"

# Preload OpenSSL 1.1 compatibility libraries on Linux (fixes "No usable version of libssl was found" crash)
if sys.platform.startswith("linux"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(base_dir, "lib")
    if os.path.isdir(lib_dir):
        curr_ld = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{curr_ld}" if curr_ld else lib_dir
        try:
            import ctypes
            crypto_so = os.path.join(lib_dir, "libcrypto.so.1.1")
            ssl_so = os.path.join(lib_dir, "libssl.so.1.1")
            if os.path.exists(crypto_so):
                ctypes.CDLL(crypto_so, mode=ctypes.RTLD_GLOBAL)
            if os.path.exists(ssl_so):
                ctypes.CDLL(ssl_so, mode=ctypes.RTLD_GLOBAL)
        except Exception as e:
            print(f"Warning preloading OpenSSL 1.1: {e}", file=sys.stderr)

import uuid
import time
import base64
import traceback
import threading
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

import converter

app = Flask(__name__, template_folder='templates')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Thread-safe lock for CAD conversions
LOCK = threading.Lock()
ACTIVE_FILES = {}


@app.errorhandler(Exception)
def handle_error(e):
    traceback.print_exc()
    return jsonify({'success': False, 'error': str(e)}), 500


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response


@app.route('/api/health', methods=['GET'])
def api_health():
    """Quick health check endpoint for Excel and other API clients."""
    return jsonify({
        'success': True,
        'status': 'online',
        'service': 'DGN to PDF Converter API'
    })


@app.route('/api/convert', methods=['POST'])
def api_convert():
    """
    REST API endpoint for programmatic and Excel web-connected conversions.
    Supports both Base64 JSON and multipart/form-data.
    """
    try:
        file_bytes = None
        orig_name = "drawing.dgn"
        paper_size = "A1"
        theme = "white"

        if request.is_json:
            data = request.get_json() or {}
            b64_content = data.get('file_base64')
            if not b64_content:
                return jsonify({'success': False, 'error': 'Missing file_base64 in JSON payload.'}), 400
            orig_name = secure_filename(data.get('file_name', 'drawing.dgn'))
            paper_size = data.get('paper_size', 'A1')
            theme = data.get('theme', 'white')
            try:
                file_bytes = base64.b64decode(b64_content)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Invalid base64 payload: {str(e)}'}), 400
        elif 'file' in request.files and request.files['file'].filename != '':
            f = request.files['file']
            orig_name = secure_filename(f.filename)
            paper_size = request.form.get('paper_size', 'A1')
            theme = request.form.get('theme', 'white')
            file_bytes = f.read()
        else:
            return jsonify({'success': False, 'error': 'No file provided. Send JSON with file_base64 or multipart file.'}), 400

        if not orig_name.lower().endswith('.dgn'):
            orig_name += '.dgn'

        file_id = str(uuid.uuid4())
        input_path = os.path.join(UPLOAD_DIR, f"{file_id}_{orig_name}")
        output_pdf = os.path.join(OUTPUT_DIR, f"{file_id}.pdf")
        thumb_png = os.path.join(OUTPUT_DIR, f"{file_id}_thumb.png")

        with open(input_path, 'wb') as f_out:
            f_out.write(file_bytes)

        options = {'paper_size': paper_size, 'theme': theme, 'orientation': 'auto'}

        with LOCK:
            meta = converter.convert_dgn(input_path, output_pdf, thumb_path=thumb_png, options=options, isolated=False)
            import gc
            gc.collect()

        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except OSError:
                pass

        clean_pdf_name = os.path.splitext(orig_name)[0] + '.pdf'
        ACTIVE_FILES[file_id] = {
            'path': output_pdf,
            'name': clean_pdf_name,
            'created': time.time()
        }

        with open(output_pdf, 'rb') as f_pdf:
            pdf_b64 = base64.b64encode(f_pdf.read()).decode('utf-8')

        thumb_b64 = ""
        if os.path.exists(thumb_png):
            with open(thumb_png, 'rb') as f_th:
                thumb_b64 = base64.b64encode(f_th.read()).decode('utf-8')

        return jsonify({
            'success': True,
            'file_id': file_id,
            'pdf_filename': clean_pdf_name,
            'pdf_base64': pdf_b64,
            'preview_base64': thumb_b64,
            'download_url': f'/download/{file_id}',
            'view_url': f'/view/{file_id}',
            'metadata': meta
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert():
    """Converts uploaded DGN file to PDF."""
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({'success': False, 'error': 'No DGN file uploaded.'}), 400

    f = request.files['file']
    orig_name = secure_filename(f.filename)
    if not orig_name.lower().endswith('.dgn'):
        return jsonify({'success': False, 'error': 'Please upload a valid .dgn file.'}), 400

    file_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{file_id}_{orig_name}")
    output_pdf = os.path.join(OUTPUT_DIR, f"{file_id}.pdf")

    f.save(input_path)
    paper_size = request.form.get('paper_size', 'A4')
    theme = request.form.get('theme', 'white')

    # Perform conversion
    options = {'paper_size': paper_size, 'theme': theme, 'orientation': 'auto'}

    with LOCK:
        meta = converter.convert_dgn(input_path, output_pdf, options=options, isolated=False)
        import gc
        gc.collect()

    if os.path.exists(input_path):
        try:
            os.remove(input_path)
        except OSError:
            pass

    clean_pdf_name = os.path.splitext(orig_name)[0] + '.pdf'
    ACTIVE_FILES[file_id] = {
        'path': output_pdf,
        'name': clean_pdf_name,
        'created': time.time()
    }

    return jsonify({
        'success': True,
        'file_id': file_id,
        'pdf_filename': clean_pdf_name,
        'download_url': f'/download/{file_id}',
        'view_url': f'/view/{file_id}',
        'metadata': meta
    })


@app.route('/download/<file_id>')
def download(file_id):
    """Downloads the converted PDF."""
    entry = ACTIVE_FILES.get(file_id)
    pdf_path = entry['path'] if entry else os.path.join(OUTPUT_DIR, f"{file_id}.pdf")
    dl_name = entry['name'] if entry else f"{file_id}.pdf"

    if not os.path.exists(pdf_path):
        return jsonify({'error': 'PDF file not found'}), 404

    return send_file(pdf_path, as_attachment=True, download_name=dl_name, mimetype='application/pdf')


@app.route('/view/<file_id>')
def view(file_id):
    """Inline view of the converted PDF for the iframe viewer."""
    entry = ACTIVE_FILES.get(file_id)
    pdf_path = entry['path'] if entry else os.path.join(OUTPUT_DIR, f"{file_id}.pdf")

    if not os.path.exists(pdf_path):
        return jsonify({'error': 'PDF file not found'}), 404

    return send_file(pdf_path, as_attachment=False, mimetype='application/pdf')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Server started: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
