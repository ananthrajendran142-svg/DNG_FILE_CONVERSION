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
        meta = converter.convert_dgn(input_path, output_pdf, options=options)

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
