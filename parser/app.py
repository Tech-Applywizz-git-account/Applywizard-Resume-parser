"""Tkinter app to pick a PDF resume and parse it with resume_parser."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None
    filedialog = None
    messagebox = None
    ttk = None

from resume_parser import parse_resume

# --- FastAPI Setup for Vercel ---
from fastapi import FastAPI, UploadFile, File, HTTPException
import tempfile
import os

app = FastAPI(title="Resume Parser API")

@app.post("/api/parse")
async def parse_resume_api(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
            
        parsed_schema = parse_resume(tmp_path)
        return parsed_schema.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# --- Tkinter Desktop App ---
class ResumeParserApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Resume Parser")
        self.root.geometry("980x720")
        self.root.minsize(720, 520)

        self.selected_path: Path | None = None
        self.parsed_json = ""

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 8}

        header = ttk.Frame(self.root)
        header.pack(fill="x", **pad)

        ttk.Label(
            header,
            text="Select a PDF resume to extract contact info, skills, experience, education, and more.",
            wraplength=900,
        ).pack(anchor="w")

        controls = ttk.Frame(self.root)
        controls.pack(fill="x", **pad)

        ttk.Button(controls, text="Choose PDF…", command=self.choose_pdf).pack(side="left")
        ttk.Button(controls, text="Parse Resume", command=self.parse_selected).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Save JSON…", command=self.save_json).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Copy JSON", command=self.copy_json).pack(side="left", padx=(8, 0))

        self.path_var = tk.StringVar(value="No file selected")
        ttk.Label(self.root, textvariable=self.path_var).pack(anchor="w", padx=12)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, foreground="#444").pack(anchor="w", padx=12, pady=(0, 4))

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        summary_frame = ttk.Frame(body)
        json_frame = ttk.Frame(body)
        body.add(summary_frame, weight=1)
        body.add(json_frame, weight=2)

        ttk.Label(summary_frame, text="Quick summary").pack(anchor="w")
        self.summary = tk.Text(summary_frame, wrap="word", height=20, width=40)
        self.summary.pack(fill="both", expand=True, pady=(4, 0))
        self.summary.configure(state="disabled")

        ttk.Label(json_frame, text="Parsed JSON").pack(anchor="w")
        self.output = tk.Text(json_frame, wrap="none", height=20)
        yscroll = ttk.Scrollbar(json_frame, orient="vertical", command=self.output.yview)
        xscroll = ttk.Scrollbar(json_frame, orient="horizontal", command=self.output.xview)
        self.output.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.output.pack(side="left", fill="both", expand=True, pady=(4, 0))
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")

    def choose_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Select resume PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        self.selected_path = Path(path)
        self.path_var.set(str(self.selected_path))
        self.status_var.set("PDF selected. Click Parse Resume.")

    def parse_selected(self) -> None:
        if self.selected_path is None:
            path = filedialog.askopenfilename(
                title="Select resume PDF",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            )
            if not path:
                return
            self.selected_path = Path(path)
            self.path_var.set(str(self.selected_path))

        self.status_var.set("Parsing…")
        self.root.update_idletasks()
        try:
            parsed = parse_resume(self.selected_path)
            self.parsed_json = parsed.to_json()
            self._set_text(self.output, self.parsed_json, read_only=False)
            self._set_text(self.summary, self._format_summary(parsed.to_dict()), read_only=True)
            self.status_var.set("Parsed successfully.")
        except Exception as exc:
            self.parsed_json = ""
            self._set_text(self.output, "", read_only=False)
            self._set_text(self.summary, "", read_only=True)
            self.status_var.set("Parsing failed.")
            messagebox.showerror("Parse failed", f"{exc}\n\n{traceback.format_exc()}")

    def save_json(self) -> None:
        if not self.parsed_json:
            messagebox.showinfo("Nothing to save", "Parse a resume first.")
            return
        default = "resume.json"
        if self.selected_path:
            default = self.selected_path.with_suffix(".json").name
        path = filedialog.asksaveasfilename(
            title="Save parsed resume",
            defaultextension=".json",
            initialfile=default,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(self.parsed_json, encoding="utf-8")
        self.status_var.set(f"Saved {path}")

    def copy_json(self) -> None:
        if not self.parsed_json:
            messagebox.showinfo("Nothing to copy", "Parse a resume first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.parsed_json)
        self.status_var.set("JSON copied to clipboard.")

    def _format_summary(self, data: dict) -> str:
        personal = data.get("personal", {})
        skills = data.get("skills", {})
        skills_list = skills.get("explicit", []) + skills.get("from_experience", [])
        
        lines = [
            f"Name: {personal.get('name') or '—'}",
            f"Emails: {', '.join(personal.get('emails') or []) or '—'}",
            f"Phones: {', '.join(personal.get('phones') or []) or '—'}",
            f"Location: {personal.get('location') or '—'}",
            f"Skills: {', '.join(skills_list[:20]) or '—'}",
            f"Education entries: {len(data.get('education') or [])}",
            f"Experience entries: {len(data.get('experience') or [])}",
            f"Projects count: {len(data.get('projects') or [])}",
            f"Certifications count: {len(data.get('certifications') or [])}",
            ""
        ]
        
        education = data.get("education") or []
        if education:
            lines.append("Education Preview:")
            ed = education[0]
            lines.append(f"Degree: {ed.get('degree') or '—'}")
            lines.append(f"Institution: {ed.get('institution') or '—'}")
            dates = []
            if ed.get('start_year'): dates.append(ed['start_year'])
            if ed.get('end_year') or ed.get('graduation_year'): dates.append(ed.get('end_year') or ed.get('graduation_year'))
            lines.append(f"Dates: {' - '.join(dates) if dates else '—'}")
            lines.append(f"Score: {ed.get('cgpa') or ed.get('percentage') or '—'}")
            lines.append("")
            
        lines.append("Summary:")
        lines.append(data.get("summary") or "—")
        return "\n".join(lines)

    @staticmethod
    def _set_text(widget: tk.Text, value: str, read_only: bool = False) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        if read_only:
            widget.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except tk.TclError:
        pass
    ResumeParserApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
