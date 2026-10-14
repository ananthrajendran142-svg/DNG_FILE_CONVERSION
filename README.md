# DGN to PDF Converter 📐📄

A high-performance Python tool and web application that converts Bentley MicroStation **DGN** CAD design files (both **V7 ISFF** and **V8 OLE**) into crisp, watermark-free vector **PDF** documents.

---

## 🚀 Key Features

1. **Standalone Script & Web Interface**:
   - **`dgn_to_pdf.py`**: A standalone script with native file dialog picker (`tkinter`), interactive paper size/theme prompts, and CLI flags.
   - **`app.py`**: Clean, lightweight web interface with drag-and-drop file upload and integrated PDF preview.

2. **Full MicroStation DGN Support**:
   - **DGN V7 (ISFF)**: Intergraph Standard File Format with automated pre-flight sanitization to prevent nested cell recursion loops.
   - **DGN V8**: Modern OLE2 compound document container storing complex layers and models.

3. **High-Precision Vector Clarity**:
   - Fine line weight scaling (`line_scale = 0.35`) prevents wall and hatch bleeding on architectural plans.
   - Font thickness normalization & anti-aliasing for sharp, readable engineering text annotations.

4. **100% Watermark-Free**:
   - Advanced PyMuPDF stream normalization strips evaluation watermarks, removes overlay crosses, and balances graphic stack tokens (`q`/`Q`).

5. **Customizable Paper Sizes & Themes**:
   - **Paper Sizes**: A1 Architectural (Recommended), A4, A3, A0 Large Format, US Letter.
   - **Color Themes**: White (Standard Print), Blueprint Blue, Dark CAD Station, Architectural Cream.

---

## 📦 Installation

Ensure you have **Python 3.11, 3.12, or 3.13** installed (Note: `aspose-cad` supports Python $\le$ 3.13).

```bash
pip install -r requirements.txt
```

---

## 💻 Usage

### Option 1: Standalone Python Script (Interactive File Picker)

Run the script directly:
```bash
python dgn_to_pdf.py
```
- A native Windows File Explorer dialog will pop up to choose your `.dgn` file.
- Select your paper size `[1-5]` and theme `[1-4]` (or press `Enter` for defaults).
- The converted PDF will be generated and automatically opened.

Or run with command-line arguments:
```bash
python dgn_to_pdf.py "path/to/drawing.dgn" "output.pdf" --size A1 --theme blueprint
```

### Option 2: Web Application

Start the local Flask server:
```bash
python app.py
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser to drag & drop files and preview PDFs inline.

---

## 📂 Project Structure

```text
├── dgn_to_pdf.py         # Standalone conversion script with file picker dialog
├── converter.py          # Core CAD rasterization and vector normalization engine
├── app.py                # Web application server
├── templates/
│   └── index.html        # Clean, modern conversion UI
├── requirements.txt      # Project dependencies
└── README.md             # Documentation
```
