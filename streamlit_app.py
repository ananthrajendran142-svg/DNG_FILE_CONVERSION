import os
import sys
import tempfile
import base64
import streamlit as st
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

    tab_visual, tab_interactive = st.tabs(["🖼️ High-Res Image Preview", "📑 Interactive PDF Viewer"])

    with tab_visual:
        if data["png_bytes"]:
            st.image(
                data["png_bytes"],
                caption=f"{data['dl_name']} ({meta['paper_size']} · {meta['theme'].title()} Theme)",
                use_container_width=True
            )
        else:
            st.info("Preview image could not be rendered.")

    with tab_interactive:
        b64_pdf = base64.b64encode(data["pdf_bytes"]).decode("utf-8")
        pdf_display = (
            f'<iframe src="data:application/pdf;base64,{b64_pdf}" '
            f'width="100%" height="650" type="application/pdf" '
            f'style="border: 1px solid #e2e8f0; border-radius: 8px;"></iframe>'
        )
        st.markdown(pdf_display, unsafe_allow_html=True)
