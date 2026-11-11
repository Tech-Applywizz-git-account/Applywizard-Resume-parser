"""Indian school/college levels returned by the resume parser."""

import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resume_parser import _classify_education_text, _extract_deterministic, parse_resume


FILLER = (
    "Candidate background note for parser length. "
    "Email candidate@example.com. Phone 9876543210. "
    "Lives in Hyderabad Telangana. Neutral prose follows so this document "
    "has enough extracted characters to parse as text rather than a scan."
)

AKASH_LINES = [
    "Bachelor of Technology in Computer Science, VNR College of Engineering, CGPA 8.6",
    "Intermediate",
    "Narayana Junior College, Hyderabad",
    "97%",
    "School Education",
    "Sri Chaitanya High School",
    "100%",
]

VIGNESH_LINES = [
    "Bachelor of Computer Science , Geethanjali college of engineering",
    "2020 - 2022",
    "Secondary School , Narayana junior college (Percentage - 98.1)",
]

RAJAGIRI_LINES = [
    "B.Tech in Computer Science, Rajagiri School of Engineering and Technology, CGPA 8.2",
]

MASTER_BACHELOR_LINES = [
    "Master of Technology in Computer Science, JNTU College of Engineering, CGPA 8.4",
    "2018 - 2020",
    "Bachelor of Technology in Computer Science, CBIT College of Engineering, CGPA 7.9",
    "2014 - 2018",
]


def _line(text: str, top: float, size: float = 12) -> dict:
    return {
        "text": text,
        "page": 1,
        "x0": 72.0,
        "x1": 72.0 + max(40, len(text) * 5),
        "top": float(top),
        "bottom": float(top) + size,
        "font_size": float(size),
        "font_name": "Helvetica",
    }


def parse_lines(lines: list[str]):
    blocks = [[_line(FILLER, 20, 11)], [_line("Education", 70, 16)]]
    top = 100
    for text in lines:
        blocks.append([_line(text, top)])
        top += 24
    raw = FILLER + "\nEducation\n" + "\n".join(lines)
    return _extract_deterministic(blocks, raw)


def describe(entries) -> str:
    rows = []
    for entry in entries:
        rows.append(
            {
                "level": entry.level,
                "degree": entry.degree,
                "institution": entry.institution,
                "college": entry.college,
                "school": entry.school,
                "source_text": entry.source_text,
            }
        )
    return repr(rows)


def build_pdf(lines: list[str]) -> bytes:
    """Minimal one-column PDF that pdfplumber can read back as text lines."""

    def esc(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    commands = ["BT", "/F1 11 Tf"]
    y = 1900
    for line in [FILLER, "Education", *lines]:
        commands.append(f"1 0 0 1 48 {y} Tm ({esc(line)}) Tj")
        y -= 36
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 2000 2200] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref = len(output)
    output += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    output += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        output += f"{offset:010d} 00000 n \n".encode("ascii")
    output += (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF"
    ).encode("ascii")
    return bytes(output)


class EducationClassificationTests(unittest.TestCase):
    def test_signal_priority(self):
        cases = {
            "Secondary School , Narayana junior college (Percentage - 98.1)": "Intermediate",
            "Narayana Junior College": "Intermediate",
            "Intermediate": "Intermediate",
            "Class XII": "Intermediate",
            "Class 12": "Intermediate",
            "HSC": "Intermediate",
            "PUC": "Intermediate",
            "Plus Two": "Intermediate",
            "Secondary School 2020 - 2022": "Intermediate",
            "High School": "10th",
            "High School 2020 - 2022": "10th",
            "School Education": "10th",
            "SSC": "10th",
            "SSC 2020 - 2022": "10th",
            "Class X": "10th",
            "Class 10": "10th",
            "Matriculation": "10th",
            "B.Tech": "Bachelor",
            "Bachelor of Technology": "Bachelor",
            "M.Tech": "Master",
            "MBA": "Master",
            "PhD": "PhD",
            "Doctorate": "PhD",
            "Diploma in Mechanical Engineering": "Diploma",
            "ITI Electrician": "Diploma",
        }
        for text, level in cases.items():
            self.assertEqual(_classify_education_text(text), level, text)

    def test_akash_keeps_bachelor_intermediate_and_tenth(self):
        entries = parse_lines(AKASH_LINES).education
        levels = [entry.level for entry in entries]
        self.assertEqual(sorted(levels), ["10th", "Bachelor", "Intermediate"], describe(entries))

        intermediate = next(entry for entry in entries if entry.level == "Intermediate")
        tenth = next(entry for entry in entries if entry.level == "10th")
        self.assertIn("intermediate", (intermediate.degree or "").lower())
        self.assertNotIn("secondary", (intermediate.degree or "").lower())
        self.assertIn("narayana", (intermediate.institution or "").lower())
        self.assertIn("junior college", (intermediate.institution or "").lower())
        self.assertIn("narayana", (intermediate.college or "").lower())
        self.assertFalse(intermediate.school)
        self.assertNotIn("(SSC)", intermediate.source_text or "")
        self.assertIn("high school", (tenth.institution or "").lower())
        self.assertIn("high school", (tenth.school or "").lower())
        self.assertIn((tenth.degree or ""), {"High School", "SSC", "Class 10"})

    def test_vignesh_junior_college_is_intermediate_not_tenth(self):
        entries = parse_lines(VIGNESH_LINES).education
        levels = [entry.level for entry in entries]
        self.assertIn("Bachelor", levels, describe(entries))
        self.assertIn("Intermediate", levels, describe(entries))
        self.assertNotIn("10th", levels, describe(entries))
        self.assertEqual(len(entries), 2, describe(entries))

        intermediate = next(entry for entry in entries if entry.level == "Intermediate")
        self.assertIn("narayana junior college", (intermediate.institution or "").lower())
        self.assertIn("narayana junior college", (intermediate.college or "").lower())
        self.assertFalse(intermediate.school)
        degree = (intermediate.degree or "").lower()
        self.assertNotIn("secondary school", degree)
        self.assertNotIn("ssc", degree)
        self.assertNotIn("10th", degree)
        self.assertNotIn("(SSC)", intermediate.source_text or "")
        self.assertNotIn("(SSC)", intermediate.degree or "")
        self.assertNotIn("(SSC)", intermediate.institution or "")

    def test_degree_only_resume_is_one_bachelor_row(self):
        entries = parse_lines(RAJAGIRI_LINES).education
        self.assertEqual([entry.level for entry in entries], ["Bachelor"], describe(entries))

    def test_master_does_not_drop_bachelor(self):
        entries = parse_lines(MASTER_BACHELOR_LINES).education
        levels = [entry.level for entry in entries]
        self.assertIn("Master", levels, describe(entries))
        self.assertIn("Bachelor", levels, describe(entries))
        self.assertEqual(sorted(levels), ["Bachelor", "Master"], describe(entries))

    def test_two_year_secondary_school_span_is_intermediate(self):
        entries = parse_lines(["Secondary School", "2020 - 2022"]).education
        self.assertEqual([entry.level for entry in entries], ["Intermediate"], describe(entries))
        self.assertNotIn("secondary", (entries[0].degree or "").lower())

    def test_high_school_with_two_year_span_stays_tenth(self):
        entries = parse_lines(
            ["High School", "Springfield High School", "2020 - 2022"]
        ).education
        self.assertEqual([entry.level for entry in entries], ["10th"], describe(entries))

    def test_ssc_with_two_year_span_stays_tenth(self):
        entries = parse_lines(["SSC", "Board of Secondary Education", "2020 - 2022"]).education
        self.assertEqual([entry.level for entry in entries], ["10th"], describe(entries))
        self.assertEqual(entries[0].degree, "SSC")

    def test_class_12_and_class_10_are_distinct(self):
        entries = parse_lines(
            [
                "Class XII, Narayana Junior College",
                "Class X, Springfield High School",
            ]
        ).education
        levels = sorted(entry.level for entry in entries)
        self.assertEqual(levels, ["10th", "Intermediate"], describe(entries))
        intermediate = next(entry for entry in entries if entry.level == "Intermediate")
        tenth = next(entry for entry in entries if entry.level == "10th")
        self.assertEqual(intermediate.degree, "Class 12")
        self.assertEqual(tenth.degree, "Class 10")
        self.assertTrue(intermediate.college)
        self.assertFalse(intermediate.school)

    def test_phd_and_diploma_level_names(self):
        phd = parse_lines(["PhD in Computer Science, IIT Delhi"]).education
        self.assertEqual([entry.level for entry in phd], ["PhD"], describe(phd))
        diploma = parse_lines(
            ["Diploma in Mechanical Engineering, Government Polytechnic"]
        ).education
        self.assertEqual([entry.level for entry in diploma], ["Diploma"], describe(diploma))


class ApiParseEducationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from app import app

        cls.client = TestClient(app)

    def _parse_pdf(self, lines: list[str]) -> list[dict]:
        payload = build_pdf(lines)
        response = self.client.post(
            "/api/parse",
            files={"file": ("resume.pdf", io.BytesIO(payload), "application/pdf")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["education"]

    def test_api_akash(self):
        education = self._parse_pdf(AKASH_LINES)
        levels = sorted(row["level"] for row in education)
        self.assertEqual(levels, ["10th", "Bachelor", "Intermediate"], education)

    def test_api_vignesh(self):
        education = self._parse_pdf(VIGNESH_LINES)
        levels = [row["level"] for row in education]
        self.assertEqual(sorted(levels), ["Bachelor", "Intermediate"], education)
        intermediate = next(row for row in education if row["level"] == "Intermediate")
        self.assertIn("narayana junior college", (intermediate["institution"] or "").lower())
        self.assertNotIn("(SSC)", intermediate.get("source_text") or "")
        self.assertNotIn("secondary school", (intermediate.get("degree") or "").lower())

    def test_api_degree_only(self):
        education = self._parse_pdf(RAJAGIRI_LINES)
        self.assertEqual([row["level"] for row in education], ["Bachelor"], education)

    def test_api_master_and_bachelor(self):
        education = self._parse_pdf(MASTER_BACHELOR_LINES)
        levels = sorted(row["level"] for row in education)
        self.assertEqual(levels, ["Bachelor", "Master"], education)

    def test_api_matches_parse_resume(self):
        payload = build_pdf(VIGNESH_LINES)
        response = self._parse_pdf(VIGNESH_LINES)
        import tempfile
        import os

        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        handle.write(payload)
        handle.close()
        try:
            parsed = parse_resume(handle.name)
        finally:
            os.unlink(handle.name)
        self.assertEqual(
            [row["level"] for row in response],
            [entry.level for entry in parsed.education],
        )


if __name__ == "__main__":
    unittest.main()
