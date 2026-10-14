import os
import sys
import tempfile
import base64
import streamlit as st
import streamlit.components.v1 as components
import pymupdf

# Configure globalization and libraries on Linux
os.environ["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"
os.environ["COMPlus_GlobalizationInvariant"] = "1"

if sys.platform.startswith("linux"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(base_dir, "lib")
    if os.path.isdir(lib_dir):
        curr_ld = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{curr_ld}" if curr_ld else lib_dir

import converter

st.set_page_config(page_title="DGN to PDF Converter", page_icon="📐", layout="centered")

st.title("📐 DGN to PDF Converter")
st.markdown("Convert Bentley MicroStation **DGN** drawings (V7 and V8) into sharp, clean, watermark-free vector **PDF** documents.")

# Initialize session state for persistent preview
if "converted_data" not in st.session_state:
    st.session_state.converted_data = None
if "last_file_name" not in st.session_state:
    st.session_state.last_file_name = None

uploaded_file = st.file_uploader("Upload MicroStation .dgn file", type=["dgn"])

# Reset preview if a new file is uploaded
if uploaded_file and uploaded_file.name != st.session_state.last_file_name:
    st.session_state.converted_data = None
    st.session_state.last_file_name = uploaded_file.name

col1, col2 = st.columns(2)
with col1:
    paper_size = st.selectbox(
        "Paper Size",
        ["A1", "A4", "A3", "A0", "Letter"],
        index=0,
        help="A1 Architectural is recommended for maximum clarity on detailed drawings."
    )
with col2:
    theme_labels = {
        "white": "White (Standard Clean)",
        "blueprint": "Blueprint Blue",
        "dark": "Dark CAD Station",
        "cream": "Architectural Cream"
    }
    theme = st.selectbox(
        "Color Theme",
        list(theme_labels.keys()),
        index=0,
        format_func=lambda x: theme_labels[x]
    )

PDF_VIEWER_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #1e293b; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; color: white; }
    #toolbar { background: #0f172a; padding: 10px 14px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: center; position: sticky; top: 0; z-index: 100; border-bottom: 1px solid #334155; }
    button { background: #2563eb; color: white; border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px; transition: background 0.15s; }
    button:hover { background: #1d4ed8; }
    .badge { background: #334155; padding: 4px 10px; border-radius: 4px; font-size: 13px; font-weight: 500; }
    #canvas-container { display: flex; justify-content: center; padding: 20px 10px; overflow: auto; min-height: 580px; }
    canvas { box-shadow: 0 8px 24px rgba(0,0,0,0.5); background: white; max-width: 100%; height: auto; border-radius: 4px; }
  </style>
</head>
<body>
  <div id="toolbar">
    <button id="prev">◀ Prev</button>
    <span class="badge">Page <span id="page_num">1</span> / <span id="page_count">1</span></span>
    <button id="next">Next ▶</button>
    <span style="color: #64748b;">|</span>
    <button id="zoom_out">🔍 -</button>
    <span class="badge" id="zoom_percent">100%</span>
    <button id="zoom_in">🔍 +</button>
    <button id="zoom_fit">Fit Width</button>
  </div>
  <div id="canvas-container">
    <canvas id="pdf-canvas"></canvas>
  </div>
  <script>
    const pdfData = atob("__B64_PDF__");
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    let pdfDoc = null,
        pageNum = 1,
        pageRendering = false,
        pageNumPending = null,
        scale = 1.0,
        canvas = document.getElementById('pdf-canvas'),
        ctx = canvas.getContext('2d');

    function renderPage(num) {
      pageRendering = true;
      pdfDoc.getPage(num).then(function(page) {
        let viewport = page.getViewport({scale: scale});
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        let renderContext = {
          canvasContext: ctx,
          viewport: viewport
        };
        let renderTask = page.render(renderContext);

        renderTask.promise.then(function() {
          pageRendering = false;
          if (pageNumPending !== null) {
            renderPage(pageNumPending);
            pageNumPending = null;
          }
        });
      });

      document.getElementById('page_num').textContent = num;
      document.getElementById('zoom_percent').textContent = Math.round(scale * 100) + '%';
    }

    function queueRenderPage(num) {
      if (pageRendering) {
        pageNumPending = num;
      } else {
        renderPage(num);
      }
    }

    document.getElementById('prev').addEventListener('click', function() {
      if (pageNum <= 1) return;
      pageNum--;
      queueRenderPage(pageNum);
    });

    document.getElementById('next').addEventListener('click', function() {
      if (pageNum >= pdfDoc.numPages) return;
      pageNum++;
      queueRenderPage(pageNum);
    });

    document.getElementById('zoom_in').addEventListener('click', function() {
      scale = Math.min(scale + 0.25, 3.5);
      queueRenderPage(pageNum);
    });

    document.getElementById('zoom_out').addEventListener('click', function() {
      scale = Math.max(scale - 0.25, 0.35);
      queueRenderPage(pageNum);
    });

    document.getElementById('zoom_fit').addEventListener('click', function() {
      pdfDoc.getPage(pageNum).then(function(page) {
        let containerWidth = document.getElementById('canvas-container').clientWidth - 40;
        let unscaledViewport = page.getViewport({scale: 1.0});
        scale = Math.max(0.4, Math.min(containerWidth / unscaledViewport.width, 2.5));
        queueRenderPage(pageNum);
      });
    });

    pdfjsLib.getDocument({data: pdfData}).promise.then(function(pdfDoc_) {
      pdfDoc = pdfDoc_;
      document.getElementById('page_count').textContent = pdfDoc.numPages;
      pdfDoc.getPage(1).then(function(page) {
        let containerWidth = document.getElementById('canvas-container').clientWidth - 40;
        let unscaledViewport = page.getViewport({scale: 1.0});
        if (containerWidth > 200) {
          scale = Math.max(0.4, Math.min(containerWidth / unscaledViewport.width, 1.5));
        }
        renderPage(pageNum);
      });
    }).catch(function(err) {
      document.getElementById('canvas-container').innerHTML = '<div style="color:#f87171; padding:20px;">PDF Viewer Error: ' + err.message + '</div>';
    });
  </script>
</body>
</html>"""

if st.button("Convert to PDF", type="primary", disabled=uploaded_file is None):
    with st.spinner("Processing CAD elements and generating preview..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dgn") as tmp_in:
            tmp_in.write(uploaded_file.getbuffer())
            tmp_in_path = tmp_in.name

        out_pdf_path = tmp_in_path + ".pdf"
        try:
            options = {"paper_size": paper_size, "theme": theme, "orientation": "auto"}
            meta = converter.convert_dgn(tmp_in_path, out_pdf_path, options=options, isolated=True)

            with open(out_pdf_path, "rb") as f:
                pdf_bytes = f.read()

            # Generate high-resolution preview image of the first page
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            png_bytes = None
            if len(doc) > 0:
                page = doc[0]
                rect = page.rect
                scale = 1600.0 / max(max(1.0, rect.width), max(1.0, rect.height))
                mat = pymupdf.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                png_bytes = pix.tobytes("png")
            doc.close()

            dl_name = os.path.splitext(uploaded_file.name)[0] + ".pdf"
            st.session_state.converted_data = {
                "pdf_bytes": pdf_bytes,
                "png_bytes": png_bytes,
                "dl_name": dl_name,
                "meta": meta
            }
        except Exception as e:
            st.error(f"Conversion Error: {e}")
        finally:
            if os.path.exists(tmp_in_path):
                os.remove(tmp_in_path)
            if os.path.exists(out_pdf_path):
                os.remove(out_pdf_path)

# Display Preview and Download Option
if st.session_state.converted_data:
    data = st.session_state.converted_data
    meta = data["meta"]

    st.divider()
    st.success(
        f"✓ Converted in **{meta['total_time_seconds']}s**! "
        f"({meta['vector_elements_count']} vectors · {meta['output_size_formatted']} · {meta['dgn_version']})"
    )

    # Download Button right above the preview
    st.download_button(
        label="📥 Download Vector PDF",
        data=data["pdf_bytes"],
        file_name=data["dl_name"],
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )

    st.subheader("📄 Drawing Preview")

    tab_interactive, tab_visual = st.tabs(["📑 Interactive PDF Viewer", "🖼️ High-Res Image View"])

    with tab_interactive:
        b64_pdf = base64.b64encode(data["pdf_bytes"]).decode("utf-8")
        viewer_html = PDF_VIEWER_HTML.replace("__B64_PDF__", b64_pdf)
        components.html(viewer_html, height=720, scrolling=True)

    with tab_visual:
        if data["png_bytes"]:
            st.image(
                data["png_bytes"],
                caption=f"{data['dl_name']} ({meta['paper_size']} · {meta['theme'].title()} Theme)",
                use_container_width=True
            )
        else:
            st.info("Preview image could not be rendered.")
