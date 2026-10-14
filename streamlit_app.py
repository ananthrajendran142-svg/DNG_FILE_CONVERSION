import os
import sys
import tempfile
import streamlit as st

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

uploaded_file = st.file_uploader("Upload MicroStation .dgn file", type=["dgn"])

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
    with st.spinner("Processing CAD elements and normalizing vectors..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dgn") as tmp_in:
            tmp_in.write(uploaded_file.getbuffer())
            tmp_in_path = tmp_in.name

        out_pdf_path = tmp_in_path + ".pdf"
        try:
            options = {"paper_size": paper_size, "theme": theme, "orientation": "auto"}
            meta = converter.convert_dgn(tmp_in_path, out_pdf_path, options=options, isolated=True)

            with open(out_pdf_path, "rb") as f:
                pdf_bytes = f.read()

            st.success(f" Converted in {meta['total_time_seconds']}s! ({meta['vector_elements_count']} vector drawings, {meta['output_size_formatted']})")

            dl_name = os.path.splitext(uploaded_file.name)[0] + ".pdf"
            st.download_button(
                label="📥 Download Vector PDF",
                data=pdf_bytes,
                file_name=dl_name,
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Conversion Error: {e}")
        finally:
            if os.path.exists(tmp_in_path):
                os.remove(tmp_in_path)
            if os.path.exists(out_pdf_path):
                os.remove(out_pdf_path)
