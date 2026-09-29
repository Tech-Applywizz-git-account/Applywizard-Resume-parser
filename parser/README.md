# Resume Parser

Parse a PDF resume into structured fields (name, contact info, skills, experience, education, projects, and more). Pick a file in a Tkinter window, or call the parser from Python.

## Files

| File | What it is |
| --- | --- |
| `app.py` | GUI. Choose a PDF, parse it, view/save JSON. **This is the file you run.** |
| `resume_parser.py` | Library that extracts text from the PDF and parses resume details. Imported by `app.py`. |
| `requirements.txt` | Python packages (`pdfplumber`). |
| `sample_resume.pdf` | Optional test PDF you can open in the GUI. |

## Setup

In this folder (`parser`), install dependencies:

```bash
python -m pip install -r requirements.txt
```

On Windows, if `python` is not found, try `py`:

```bash
py -m pip install -r requirements.txt
```

Tkinter ships with standard Python on Windows. You do not install it separately.

## Run the GUI (upload a PDF)

```bash
python app.py
```

Or:

```bash
py app.py
```

Then:

1. Click **Choose PDF…** and select a `.pdf` resume (for example `sample_resume.pdf`).
2. Click **Parse Resume**.
3. Review the summary and JSON.
4. Optionally **Save JSON…** or **Copy JSON**.

## Use the library in code

You do not run `resume_parser.py` by itself. Import it from another script:

```python
from resume_parser import parse_resume

parsed = parse_resume("sample_resume.pdf")
print(parsed.to_json())
```

Save JSON to a file:

```python
from pathlib import Path
from resume_parser import parse_resume

result = parse_resume(r"C:\path\to\resume.pdf")
Path("resume.json").write_text(result.to_json(), encoding="utf-8")
```

## Notes

- **100% Local Parsing**: The parsing engine operates entirely locally using Python, layout geometry, and heuristics. No LLMs, Gemini, OpenAI, or external cloud APIs are required or used.
- **Generic Layout Support**: Built to dynamically interpret document structures. Robustly supports a vast range of standard, multi-column, sidebar, text-box, and tabular resume layouts without hardcoded coordinate assumptions.
- **OCR Support**: The parser uses pdfplumber for geometric text extraction with layout preservation. If the document consists of scanned images, it will automatically fallback to pytesseract and pdf2image for OCR (requires Tesseract and poppler installed on your system).
