import os
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pdfplumber

from models import (
    ResumeSchema, PersonalInfo, Skills, EducationEntry, 
    ExperienceEntry, ProjectEntry, Score
)


try:
    from pdf2image import convert_from_path
    import pytesseract
except ImportError:
    pytesseract = None
    convert_from_path = None


def parse_resume(pdf_path: str | Path) -> ResumeSchema:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF resumes are supported.")

    blocks = _extract_blocks(path)
    raw_text = "\n".join([line["text"] for block in blocks for line in block])
    
    if len(raw_text.strip()) < 100:
        raw_text = _extract_ocr(path)
        blocks = [{"text": raw_text, "page": 1, "x0": 0, "x1": 0, "top": 0, "bottom": 0, "font_size": 12, "font_name": ""}]
        if len(raw_text.strip()) < 100:
            raise ValueError("No text could be extracted from PDF even with OCR.")

    return _extract_deterministic(blocks, raw_text)


def _extract_blocks(path: Path) -> List[List[Dict]]:
    blocks = []
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words(extra_attrs=["size", "fontname"])
            if not words:
                continue
                
            mid_x = page.width / 2.0
            
            # Sort by top coordinate first
            words.sort(key=lambda w: w["top"])
            
            visual_lines = []
            for w in words:
                placed = False
                for vl in visual_lines:
                    vl_top = sum(x["top"] for x in vl) / len(vl)
                    vl_bottom = sum(x.get("bottom", x["top"] + x.get("size", 10)) for x in vl) / len(vl)
                    w_bottom = w.get("bottom", w["top"] + w.get("size", 10))
                    
                    # Check vertical overlap > 50%
                    overlap = max(0, min(vl_bottom, w_bottom) - max(vl_top, w["top"]))
                    h1 = vl_bottom - vl_top
                    h2 = w_bottom - w["top"]
                    
                    if h1 > 0 and h2 > 0 and (overlap / h1 > 0.4 or overlap / h2 > 0.4):
                        vl.append(w)
                        placed = True
                        break
                if not placed:
                    visual_lines.append([w])
                    
            visual_lines.sort(key=lambda vl: sum(x["top"] for x in vl) / len(vl))
            for vl in visual_lines:
                vl.sort(key=lambda x: x["x0"])

            lines = []
            for vl in visual_lines:
                current_line = []
                for w in vl:
                    if not current_line:
                        current_line.append(w)
                        continue
                    prev = current_line[-1]
                    gap = w["x0"] - prev["x1"]
                    if gap > 35.0 or gap < -5.0:  # Column gap threshold or backwards wrap
                        lines.append(current_line)
                        current_line = [w]
                    else:
                        current_line.append(w)
                if current_line:
                    lines.append(current_line)
                    
            # 2. Classify lines by column
            col_lines = {'full': [], 'left': [], 'right': []}
            for l in lines:
                l_dict = _merge_words_to_line(l, page_num)
                x0 = l_dict["x0"]
                x1 = l_dict["x1"]
                center_x = (x0 + x1) / 2.0
                
                if x0 < mid_x - 50 and x1 > mid_x + 50:
                    col_lines['full'].append(l_dict)
                elif center_x < mid_x:
                    col_lines['left'].append(l_dict)
                else:
                    col_lines['right'].append(l_dict)
                    
            # Check if left or right column is just metadata (dates/locations)
            def is_metadata_column(c_lines):
                if not c_lines: return False
                avg_len = sum(len(x['text']) for x in c_lines) / len(c_lines)
                if avg_len > 35: return False
                
                dr_re = re.compile(r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4}|\d{1,2}/\d{4}|\d{4})\s*(?:-|to|–|—)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4}|\d{1,2}/\d{4}|\d{4}|Present|Current|Ongoing)', re.I)
                sy_re = re.compile(r'\b(?:19|20)\d{2}\b')
                
                date_loc_count = 0
                for x in c_lines:
                    text = x['text']
                    if dr_re.search(text) or sy_re.search(text):
                        date_loc_count += 1
                    elif len(text.split()) <= 4:
                        date_loc_count += 1
                return (date_loc_count / len(c_lines)) > 0.7

            if is_metadata_column(col_lines['right']) or is_metadata_column(col_lines['left']):
                col_lines['full'].extend(col_lines['left'])
                col_lines['full'].extend(col_lines['right'])
                col_lines['left'] = []
                col_lines['right'] = []

            # 3. Form blocks within each column
            page_blocks = []
            for col_key in ['full', 'left', 'right']:
                c_lines = col_lines[col_key]
                if not c_lines: continue
                # Sort by approximate top (to group same row) then x0
                c_lines.sort(key=lambda x: (round(x["top"] / 5.0), x["x0"]))
                
                col_blocks = []
                for l_dict in c_lines:
                    added = False
                    for block in reversed(col_blocks):
                        last_line = block[-1]
                        v_dist = l_dict["top"] - last_line["bottom"]
                        min_x0 = min(x["x0"] for x in block)
                        h_dist = abs(l_dict["x0"] - min_x0)
                        
                        same_line = abs(l_dict["top"] - last_line["top"]) < 5.0
                        
                        if same_line or (0 <= v_dist < min(l_dict["font_size"], last_line["font_size"]) * 2.5 and h_dist < 60):
                            if _detect_section(l_dict["text"]) != "unknown" and not same_line:
                                break # Don't merge a header into any block, force a new block
                            block.append(l_dict)
                            added = True
                            break
                    if not added:
                        col_blocks.append([l_dict])
                        
                page_blocks.extend(col_blocks)
                page_blocks.append([{"text": "---COLUMN_BREAK---", "font_size": 0, "x0": 0, "x1": 0, "top": 0, "bottom": 0}])
                
            blocks.extend(page_blocks)
    return blocks

def _merge_words_to_line(words, page_num):
    text = " ".join(w["text"] for w in words)
    x0 = min(w["x0"] for w in words)
    x1 = max(w["x1"] for w in words)
    top = min(w["top"] for w in words)
    bottom = max(w["bottom"] for w in words)
    sizes = [w["size"] for w in words if "size" in w]
    fonts = [w["fontname"] for w in words if "fontname" in w]
    return {
        "text": text,
        "page": page_num,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": bottom,
        "font_size": max(sizes) if sizes else 10,
        "font_name": fonts[0] if fonts else ""
    }

def _extract_ocr(path: Path) -> str:
    if not pytesseract or not convert_from_path:
        return ""
    try:
        pages = convert_from_path(path)
        text_parts = []
        for page in pages:
            text = pytesseract.image_to_string(page)
            text_parts.append(text)
        return "\n\n".join(text_parts)
    except Exception as e:
        return ""


def _detect_section(text: str) -> str:
    """
    Identify whether a text line is a standalone section heading.

    Guards applied in order:
    1. Must be short (≤5 words).
    2. Must not contain digits (section headings are never dates or scores).
    3. Must not be a phrase: disqualify if it contains lowercase linking words
       that only appear in full phrases ('of', 'the', 'in', 'for', 'from',
       'to', 'by', 'at') — BUT allow them when the entire string is all-caps
       (e.g. 'WORK EXPERIENCE', 'TECHNICAL SKILLS').
    4. Then match against known section keyword patterns.
    """
    stripped = text.strip()
    if not stripped:
        return "unknown"

    word_count = len(stripped.split())
    if word_count > 5:
        return "unknown"

    if re.search(r'\d', stripped):
        return "unknown"

    # If the text is NOT entirely uppercase/alphanumeric labels,
    # check for disqualifying phrase words
    is_all_caps_label = stripped == stripped.upper() or re.fullmatch(r'[A-Z0-9 &/,\-_]+', stripped)
    if not is_all_caps_label:
        # Mixed-case text with prepositions → phrase, not heading
        if re.search(r'\b(of|the|in|for|from|to|by|at|board|department)\b', stripped):
            return "unknown"

    lower = stripped.lower()
    clean_text = re.sub(r'[\s:.\-_/|]+', '', lower)
    
    if re.match(r'^(education|academics?|academicprofile|academicbackground|qualifications?|educationalqualifications|scholastics)$', clean_text): return "education"
    if re.match(r'^(experience|workexperience|professionalexperience|employment|employmenthistory|career|internships?|workhistory|experience&internship|experienceandinternship)$', clean_text): return "experience"
    if re.match(r'^(skills?|technicalskills?|techstack|technologies|competencies|itsskills|softskills|hardskills|corecompetencies)$', clean_text): return "skills"
    if re.match(r'^(projects?|personalprojects?|academicprojects?|majorprojects?|minorprojects?|keyprojects?)$', clean_text): return "projects"
    if re.match(r'^(summary|profile|objective|about|aboutme|careerobjective|professionalsummary)$', clean_text): return "summary"
    if re.match(r'^(certifications?(and|&)?internships?|internships?|certifications?|certificates?|licenses?|courses?|training)$', clean_text): return "certifications"
    if re.match(r'^(awards?|honors?|recognitions?|achievements?)$', clean_text): return "awards"
    if re.match(r'^(languages?|knownlanguages)$', clean_text): return "languages"
    if re.match(r'^(interests?|hobbies|activities|extracurriculars?|cocurriculars?)$', clean_text): return "interests"
    if re.match(r'^(websites?|profiles?|socials?|links?|portfolios?|contact|details)$', clean_text): return "profiles"
    
    return "unknown"


def _infer_section(block_text: str) -> str:
    lower_text = block_text.lower()
    if re.search(r'\b(b\.?tech|b\.e\.|m\.?tech|mba|mca|b\.?sc|cgpa|gpa|university|college|semester)\b', lower_text):
        return "education"
    if re.search(r'\b(objective|summary|profile|about me|looking for|career objective)\b', lower_text):
        return "summary"
    if re.search(r'\b(software engineer|developer|intern|manager|technologies used|responsibilities)\b', lower_text):
        return "experience"
    return "unknown"

def _extract_deterministic(blocks: List[List[Dict]], raw_text: str) -> ResumeSchema:
    schema = ResumeSchema(raw_text=raw_text)
    
    # 1. Contact & Personal
    email_re = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    phone_re = re.compile(r"(?:(?:\+|00)\d{1,3}[\s\-]?)?(?:\d[\s\-]?){9,14}")
    linkedin_re = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s)|]+", re.I)
    github_re = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s)|]+", re.I)
    
    # More robust Date Regex for "2021 - Present" or "2021"
    date_range_re = re.compile(r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4}|\d{1,2}/\d{4}|\d{4})\s*(?:-|to|–|—)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4}|\d{1,2}/\d{4}|\d{4}|Present|Current)", re.I)
    single_year_re = re.compile(r"\b(?:19|20)\d{2}\b")
    
    schema.personal.emails = list(set(email_re.findall(raw_text)))
    phones = [m.strip() for m in phone_re.findall(raw_text) if 10 <= len(re.sub(r"\D", "", m)) <= 15 and not single_year_re.fullmatch(m.strip())]
    schema.personal.phones = list(set(phones))
    schema.personal.linkedin = list(set(linkedin_re.findall(raw_text)))
    schema.personal.github = list(set(github_re.findall(raw_text)))
    
    location_re = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*(?: - \d{6})?, (?:[A-Z][a-z]+|[A-Z]{2})|[A-Z][a-z]+ \d{6})\b")
    
    header_blocks = []
    for block in blocks:
        if _detect_section(block[0]["text"]) not in ("unknown", "summary"):
            break
        header_blocks.append(block)
        
    for block in header_blocks[:10]:
        for line in block:
            m = location_re.search(line["text"])
            if m:
                schema.personal.location = m.group(1)
                break
        if schema.personal.location: break

    largest_font = 0
    header_lines = []
    for block in blocks[:5]:
        for line in block:
            text = line["text"].strip()
            if not text: continue
            header_lines.append(text)
            if email_re.search(text) or phone_re.search(text) or location_re.search(text): continue
            if _detect_section(text) != "unknown": continue
            if len(text.split()) > 6: continue
            if line["font_size"] > largest_font:
                largest_font = line["font_size"]
                schema.personal.name = text

    if schema.personal.name and schema.personal.name in header_lines:
        idx = header_lines.index(schema.personal.name)
        if idx + 1 < len(header_lines):
            headline = header_lines[idx + 1]
            if not email_re.search(headline) and not phone_re.search(headline) and not location_re.search(headline):
                if len(headline.split()) <= 6 and _detect_section(headline) == "unknown":
                    schema.personal.headline = headline

    # Group blocks into sections
    sections = {"personal": [], "summary": [], "education": [], "experience": [], "projects": [], "skills": [], "certifications": [], "awards": [], "languages": [], "interests": [], "profiles": [], "unknown": []}
    current_section = "unknown"
    for block in blocks:
        block_text = "\n".join(l["text"] for l in block)
        if not block_text.strip(): continue
        
        if block_text == "---COLUMN_BREAK---":
            current_section = "unknown"
            continue
        
        header_detect = _detect_section(block[0]["text"])
        if header_detect != "unknown":
            current_section = header_detect
            if len(block) > 1:
                sections[current_section].append(block[1:])
            continue
            
        inferred = _infer_section(block_text)
        if inferred != "unknown" and current_section == "unknown":
            current_section = inferred
            
        sections[current_section].append(block)

    # Parse Education
    BACHELOR_RE = re.compile(r"\b(B\.?Tech|B\.?Sc|B\.?Com|BCA|BBA)\b|\b(B\.E\.|B\.A\.)\b|\b(Bachelor of [A-Za-z]+(?: \b(?!(?:in|at|from)\b|\w*(?:University|College|Institute|School|Academy|Polytechnic))\w+)?)\b|\b(Bachelor(?:'s)?)\b(?=\s*(?:in|-|\n|$))", re.I)
    MASTER_RE = re.compile(r"\b(M\.?Tech|M\.?Sc|M\.?Com|MCA|MBA|Master Degree)\b|\b(M\.E\.|M\.A\.|M\.S\.)\b|\b(Master of [A-Za-z]+(?: \b(?!(?:in|at|from)\b|\w*(?:University|College|Institute|School|Academy|Polytechnic))\w+)?)\b|\b(Master(?:'s)?)\b(?=\s*(?:in|-|\n|$))", re.I)
    PHD_RE = re.compile(r"\b(PhD|Ph\.?D\.|Doctor of Philosophy|Doctorate)\b", re.I)
    DIPLOMA_RE = re.compile(r"\b(Diploma(?: in [A-Za-z ]+)?|Polytechnic)\b", re.I)
    INTER_RE = re.compile(r"\b(Intermediate|Inter|12th(?: Standard)?|Class XII|Class 12|HSC|Higher Secondary(?: Certificate)?|PUC|Pre-University|Plus Two)\b", re.I)
    TENTH_RE = re.compile(r"\b(10th(?: Standard)?|Class X|Class 10|SSC|Secondary School(?: Certificate)?|Secondary Education|School Education|High School|Matriculation|Matric)\b", re.I)
    # Institution regex: case-insensitive so it matches title-case AND ALL-CAPS names
    INST_RE = re.compile(
        r'(?<![\w])((?:[\w][\w&\'’‘.,\- ]*?)?(?:University|Universities|College|Colleges|Institute|Institutions?|School(?!\s+Education)|Academy|Polytechnic|Kalasala|\bIIT\b|\bNIT\b|\bIIIT\b|\bJNTU\b)(?:[\w&\'’‘.,\- ]*))',
        re.I
    )

    edu_lines = []
    for block in sections["education"]:
        for l in block:
            edu_lines.append(l)
    edu_lines.sort(key=lambda x: (x["top"], x["x0"]))
    
    edu_chunks = []
    current_chunk = []
    last_top = None
    for l in edu_lines:
        text = l["text"].strip()
        if not text: continue
        
        is_new_entity = False
        has_degree_kw = bool(BACHELOR_RE.search(text) or MASTER_RE.search(text) or PHD_RE.search(text) or INTER_RE.search(text) or TENTH_RE.search(text) or DIPLOMA_RE.search(text))
        has_date_kw = bool(date_range_re.search(text) or single_year_re.search(text))
        has_inst_kw = bool(INST_RE.search(text))

        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            chunk_has_degree = bool(BACHELOR_RE.search(chunk_text) or MASTER_RE.search(chunk_text) or PHD_RE.search(chunk_text) or INTER_RE.search(chunk_text) or TENTH_RE.search(chunk_text) or DIPLOMA_RE.search(chunk_text))
            chunk_has_date = bool(date_range_re.search(chunk_text) or single_year_re.search(chunk_text))
            chunk_has_inst = bool(INST_RE.search(chunk_text))

            if has_degree_kw and chunk_has_degree:
                def get_level(t):
                    if BACHELOR_RE.search(t): return 1
                    if MASTER_RE.search(t): return 2
                    if PHD_RE.search(t): return 3
                    if INTER_RE.search(t): return 4
                    if TENTH_RE.search(t): return 5
                    if DIPLOMA_RE.search(t): return 6
                    return 0

                if get_level(text) != 0 and get_level(chunk_text) != 0 and get_level(text) != get_level(chunk_text):
                    is_new_entity = True
                elif len(current_chunk) > 1 or bool(re.search(r'\d', chunk_text)):
                    # Don't split if the new text is just a degree label without dates/institutions AND is the same level
                    if not has_inst_kw and not has_date_kw and len(text.split()) <= 3:
                        pass
                    else:
                        is_new_entity = True
            elif has_date_kw and chunk_has_date:
                is_new_entity = True
            elif has_inst_kw and chunk_has_inst:
                text_lower = text.lower()
                chunk_lower = chunk_text.lower()
                is_continuation = "affiliated" in text_lower or ("university" in text_lower and "college" in chunk_lower) or ("board" in text_lower)
                if not is_continuation and (chunk_has_degree or chunk_has_date):
                    is_new_entity = True
                    
        # Force keep together if on the exact same visual row
        if last_top is not None and abs(l["top"] - last_top) < 5.0:
            is_new_entity = False

        if is_new_entity:
            edu_chunks.append("\n".join(current_chunk))
            current_chunk = [text]
        else:
            current_chunk.append(text)
        
        last_top = l["top"]
            
    if current_chunk:
        edu_chunks.append("\n".join(current_chunk))
        
    def safe_replace(text, target):
        if not target: return text
        if re.search(r'(University|College|Institute|School|Academy|Polytechnic|Board)', target, re.I):
            return text
        return text.replace(target, ' ')

    def safe_replace(text, target):
        if not target: return text
        if re.search(r'(University|College|Institute|School|Academy|Polytechnic|Board)', target, re.I):
            return text
        return text.replace(target, ' ')

    for chunk in edu_chunks:
        if not chunk.strip(): continue
        entry = EducationEntry()
        entry.source_text = chunk
        inst_candidate = chunk
        
        # ---------------------------------------------------------
        # NEW STRUCTURAL BRANCH
        # ---------------------------------------------------------
        structural_match = False
        for line in chunk.split('\n'):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                is_deg = bool(BACHELOR_RE.search(parts[0]) or MASTER_RE.search(parts[0]) or PHD_RE.search(parts[0]) or DIPLOMA_RE.search(parts[0]) or INTER_RE.search(parts[0]) or TENTH_RE.search(parts[0]))
                has_inst = bool(re.search(r'\b(University|Universities|College|Colleges|Institute|Institutions?|School|Academy|Polytechnic|Kalasala|IIT|NIT|IIIT|JNTU)\b', parts[1], re.I))
                if is_deg and has_inst:
                    structural_match = True
                    
                    deg_str = parts[0]
                    b_m = BACHELOR_RE.search(deg_str)
                    m_m = MASTER_RE.search(deg_str)
                    if b_m:
                        entry.level = "Bachelor"
                        entry.degree = b_m.group(1) or b_m.group(2) or b_m.group(3) or b_m.group(4)
                    elif m_m:
                        entry.level = "Master"
                        entry.degree = m_m.group(1) or m_m.group(2) or m_m.group(3) or m_m.group(4)
                    elif PHD_RE.search(deg_str):
                        entry.level = "Doctorate"
                        entry.degree = PHD_RE.search(deg_str).group(1).strip()
                    elif INTER_RE.search(deg_str):
                        entry.level = "Intermediate"
                        entry.degree = INTER_RE.search(deg_str).group(1).strip()
                    elif TENTH_RE.search(deg_str):
                        entry.level = "10th"
                        entry.degree = TENTH_RE.search(deg_str).group(1).strip()
                    elif DIPLOMA_RE.search(deg_str):
                        entry.level = "Diploma"
                        entry.degree = DIPLOMA_RE.search(deg_str).group(1).strip()
                        
                    if entry.degree:
                        fos_m = re.search(re.escape(entry.degree) + r"(?:[ \t]+(?:in|-))?[ \t]+([A-Za-z &]{2,30})(?=[ \t]*(?:\n|$))", deg_str, re.I)
                        if fos_m:
                            entry.field_of_study = fos_m.group(1).strip()
                        else:
                            fos_m = re.search(re.escape(entry.degree) + r"\s*(?:in|-)\s*([A-Za-z &]+)", deg_str, re.I)
                            if fos_m:
                                entry.field_of_study = fos_m.group(1).strip()
                        entry.branch = entry.field_of_study
                        if entry.level == "Intermediate":
                            g_m = re.search(r"\b(MPC|BiPC|BIPC|CEC|MEC|HEC|Science|Commerce|Arts)\b", deg_str, re.I)
                            if g_m:
                                entry.group = g_m.group(1).strip()
                                entry.branch = entry.group
                                
                    entry.institution = parts[1]
                    if "university" in entry.institution.lower() or "jntu" in entry.institution.lower():
                        entry.university = entry.institution
                    elif "school" in entry.institution.lower():
                        entry.school = entry.institution
                    else:
                        entry.college = entry.institution
                        
                    if len(parts) > 2:
                        entry.location = parts[2]
                        
                    inst_candidate = inst_candidate.replace(line, ' ')
                    break
        # ---------------------------------------------------------

        # Generic Extraction (if not structural)
        if not structural_match:
            b_match = BACHELOR_RE.search(chunk)
            m_match = MASTER_RE.search(chunk)
            if b_match:
                entry.level = "Bachelor"
                entry.degree = b_match.group(1) or b_match.group(2) or b_match.group(3) or b_match.group(4)
                inst_candidate = safe_replace(inst_candidate, b_match.group(0))
            elif m_match:
                entry.level = "Master"
                entry.degree = m_match.group(1) or m_match.group(2) or m_match.group(3) or m_match.group(4)
                inst_candidate = safe_replace(inst_candidate, m_match.group(0))
            elif PHD_RE.search(chunk):
                entry.level = "Doctorate"
                m = PHD_RE.search(chunk)
                entry.degree = m.group(1).strip()
                inst_candidate = safe_replace(inst_candidate, m.group(0))
            elif INTER_RE.search(chunk):
                entry.level = "Intermediate"
                m = INTER_RE.search(chunk)
                entry.degree = m.group(1).strip()
                inst_candidate = safe_replace(inst_candidate, m.group(0))
            elif TENTH_RE.search(chunk):
                entry.level = "10th"
                m = TENTH_RE.search(chunk)
                entry.degree = m.group(1).strip()
                inst_candidate = safe_replace(inst_candidate, m.group(0))
            elif DIPLOMA_RE.search(chunk):
                entry.level = "Diploma"
                m = DIPLOMA_RE.search(chunk)
                entry.degree = m.group(1).strip()
                inst_candidate = safe_replace(inst_candidate, m.group(0))
                
            if entry.degree:
                fos_m = re.search(re.escape(entry.degree) + r"(?:[ \t]+(?:in|-))?[ \t]+([A-Za-z &]{2,30})(?=[ \t]*(?:\n|$))", chunk, re.I)
                if fos_m:
                    entry.field_of_study = fos_m.group(1).strip()
                    entry.branch = entry.field_of_study
                    inst_candidate = inst_candidate.replace(fos_m.group(1), ' ')
                else:
                    fos_m = re.search(re.escape(entry.degree) + r"\s*(?:in|-)\s*([A-Za-z &]+)", chunk, re.I)
                    if fos_m:
                        entry.field_of_study = fos_m.group(1).strip()
                        entry.branch = entry.field_of_study
                        inst_candidate = inst_candidate.replace(fos_m.group(1), ' ')
            
            if entry.level == "Intermediate":
                group_m = re.search(r"\b(MPC|BiPC|BIPC|CEC|MEC|HEC|Science|Commerce|Arts)\b", chunk, re.I)
                if group_m:
                    entry.group = group_m.group(1).strip()
                    entry.branch = entry.group
                    inst_candidate = inst_candidate.replace(group_m.group(0), ' ')

            board_m = re.search(r"\b([A-Za-z &.\-]*Board(?: of [A-Za-z &.\-]*)?|CBSE|ICSE)\b", chunk, re.I)
            if board_m:
                entry.board = board_m.group(1).strip()
                inst_candidate = safe_replace(inst_candidate, board_m.group(0))

        # Score (Runs for BOTH structural and generic)
        cgpa_m = re.search(r"(?:CGPA|GPA)[ \t:]*([\d.]+)(?:[ \t]*/[ \t]*([\d.]+))?|([\d.]+)(?:[ \t]*/[ \t]*([\d.]+))?[ \t:]*(?:CGPA|GPA)", chunk, re.I)
        if cgpa_m:
            val = cgpa_m.group(1) or cgpa_m.group(3)
            scale = cgpa_m.group(2) or cgpa_m.group(4) or "10"
            entry.cgpa = val
            entry.gpa = val
            entry.gpa_scale = scale
            entry.score = Score(type="CGPA", value=val, scale=scale, raw=cgpa_m.group(0))
            inst_candidate = inst_candidate.replace(cgpa_m.group(0), ' ')
        else:
            raw_cgpa_m = re.search(r"\b([4-9]\.\d{1,2})(?:/(10(?:\.0)?))?\b", chunk)
            if raw_cgpa_m:
                entry.cgpa = raw_cgpa_m.group(1)
                entry.gpa_scale = raw_cgpa_m.group(2) if raw_cgpa_m.group(2) else "10"
                entry.score = Score(type="CGPA", value=entry.cgpa, scale=entry.gpa_scale, raw=raw_cgpa_m.group(0))
                inst_candidate = inst_candidate.replace(raw_cgpa_m.group(0), ' ')

        perc_m = re.search(r"\b(100(?:\.0{1,2})?|[3-9]\d(?:\.\d{1,2})?)\s*(?:%|percent)(?!\w)", chunk, re.I)
        if perc_m:
            entry.percentage = perc_m.group(1)
            entry.score = Score(type="Percentage", value=entry.percentage, scale="100", raw=perc_m.group(0))
            inst_candidate = inst_candidate.replace(perc_m.group(0), ' ')
        else:
            raw_perc_m = re.search(r"\b([3-9]\d\.\d{1,2})\b", chunk)
            if raw_perc_m and not entry.score:
                entry.percentage = raw_perc_m.group(1)
                entry.score = Score(type="Percentage", value=entry.percentage, scale="100", raw=raw_perc_m.group(0))
                inst_candidate = inst_candidate.replace(raw_perc_m.group(0), ' ')
            
        marks_m = re.search(r"(?:Marks(?: Obtained)?:?\s*)?([1-9]\d{2,3})\s*(?:/|out of)\s*([1-9]\d{2,3})(?!\d)", chunk, re.I)
        if marks_m:
            entry.marks_obtained = marks_m.group(1)
            entry.maximum_marks = marks_m.group(2)
            entry.score = Score(type="Marks", value=entry.marks_obtained, scale=entry.maximum_marks, raw=marks_m.group(0))
            inst_candidate = inst_candidate.replace(marks_m.group(0), ' ')
            
        # Dates (Runs for BOTH structural and generic)
        date_m = date_range_re.search(chunk)
        if date_m:
            dates = date_m.group(0).split("-") if "-" in date_m.group(0) else re.split(r'\s*(?:to|–|—)\s*', date_m.group(0), flags=re.I)
            if len(dates) == 2:
                entry.start_date = dates[0].strip()
                entry.end_date = dates[-1].strip()
                sy_m = single_year_re.search(entry.start_date)
                if sy_m: entry.start_year = sy_m.group(0)
                ey_m = single_year_re.search(entry.end_date)
                if ey_m: entry.end_year = ey_m.group(0)
                else: entry.end_year = entry.end_date
                if "present" not in entry.end_date.lower() and "current" not in entry.end_date.lower():
                    entry.graduation_year = entry.end_year
                    entry.passing_year = entry.end_year
            inst_candidate = inst_candidate.replace(date_m.group(0), ' ')
        else:
            s_year_m = single_year_re.findall(chunk)
            if s_year_m:
                entry.graduation_year = s_year_m[-1]
                entry.passing_year = s_year_m[-1]
                for sy in s_year_m:
                    inst_candidate = inst_candidate.replace(sy, ' ')
                
        # Location (Only if NOT structural_match, otherwise it was already set)
        if not structural_match:
            loc_m = location_re.search(chunk)
            if loc_m:
                entry.location = loc_m.group(1).strip()
            
        # Match Institution (Only if NOT structural_match)
        if not structural_match:
            inst_candidate = re.sub(r'\b(ongoing|current|present)\b', ' ', inst_candidate, flags=re.I)
            institutions = INST_RE.findall(inst_candidate)
            if institutions:
                inst_clean = institutions[0].replace('\n', ' ').strip()
                inst_clean = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', inst_clean).strip()
                entry.institution = inst_clean
                if "university" in entry.institution.lower() or "jntu" in entry.institution.lower():
                    entry.university = entry.institution
                elif "school" in entry.institution.lower():
                    entry.school = entry.institution
                else:
                    entry.college = entry.institution
                    
                # Check for pipe-separated metadata on the institution line
                inst_line = next((l for l in chunk.split('\n') if entry.institution in l), None)
                if inst_line and '|' in inst_line:
                    parts = [p.strip() for p in inst_line.split('|')]
                    for p in parts:
                        if p and p != entry.institution:
                            p_lower = p.lower()
                            if "university" in p_lower or "jntu" in p_lower or "board" in p_lower:
                                entry.university = p
                            elif "college" in p_lower or "institute" in p_lower or "school" in p_lower:
                                entry.details.append(p)
                            elif not re.search(r'\d', p) and len(p.split()) <= 4:
                                if not entry.location:
                                    entry.location = p
                            else:
                                entry.details.append(p)
                                
                # If a second institution is mentioned and it's a University or JNTU, extract it
                if len(institutions) > 1 and ("university" in institutions[1].lower() or "jntu" in institutions[1].lower()):
                    entry.university = re.sub(r'(?i)Affiliated to\s*', '', institutions[1].replace('\n', ' ').strip()).strip()
                
                # Post-process primary institution if it incorrectly merged Affiliated
                if entry.university:
                    entry.university = re.sub(r'(?i)Affiliated to\s*', '', entry.university).strip()
                if entry.institution:
                    entry.institution = re.sub(r'(?i)Affiliated to\s*', '', entry.institution).strip()

        # Determine if Formal Education or Training
        is_formal_edu = bool(BACHELOR_RE.search(chunk) or MASTER_RE.search(chunk) or PHD_RE.search(chunk) or INTER_RE.search(chunk) or TENTH_RE.search(chunk) or DIPLOMA_RE.search(chunk))
        
        if is_formal_edu:
            if entry.degree or entry.institution or entry.score:
                schema.education.append(entry)
        else:
            schema.training.append(chunk.strip())

    exp_lines = []
    for block in sections["experience"]:
        for l_dict in block:
            text = l_dict["text"].strip()
            # Skip the section header itself
            if text and _detect_section(text) != "experience":
                exp_lines.append(text)
                
    date_indices = []
    for i, line in enumerate(exp_lines):
        if date_range_re.search(line):
            date_indices.append(i)
            
    record_boundaries = []
    prev_boundary = 0
    for idx in date_indices:
        start = idx - 2
        if start < prev_boundary:
            start = prev_boundary
        record_boundaries.append(start)
        prev_boundary = start
        
    if not record_boundaries:
        record_boundaries = [0]
    record_boundaries.append(len(exp_lines))
    
    tech_keywords = ['Python', 'HTML', 'JavaScript', 'CSS', 'SQL', 'React', 'Node.js', 'Java', 'C++', 'AWS', 'Docker', 'Machine Learning', 'CNN', 'CNNs']
    
    for i in range(len(record_boundaries) - 1):
        start = record_boundaries[i]
        end = record_boundaries[i+1]
        chunk_lines = exp_lines[start:end]
        if not chunk_lines: continue
        
        entry = ExperienceEntry()
        desc_lines = []
        
        for j, line in enumerate(chunk_lines):
            date_m = date_range_re.search(line)
            if date_m:
                dates = date_m.group(0).split("-") if "-" in date_m.group(0) else re.split(r'\s*(?:to|–|—)\s*', date_m.group(0), flags=re.I)
                if len(dates) == 2:
                    entry.start_date = dates[0].strip()
                    entry.end_date = dates[-1].strip()
                    if "present" in entry.end_date.lower() or "current" in entry.end_date.lower():
                        entry.is_current = True
            elif not entry.job_title and j < 2:
                entry.job_title = line
            elif not entry.company and j < 3:
                entry.company = line
            elif not entry.location and j < 4 and len(line.split()) <= 3 and "achievement" not in line.lower():
                entry.location = line
            else:
                if not re.search(r'^(achievements/tasks|responsibilities|duties|key contributions|roles & responsibilities|description)$', line, re.I):
                    desc_lines.append(line.strip("-•* "))
                    
        if desc_lines:
            entry.description = desc_lines
            desc_text = " ".join(desc_lines)
            techs = []
            for tk in tech_keywords:
                if tk.lower() == 'cnn' and 'cnn' in desc_text.lower():
                    if 'CNN' not in techs: techs.append('CNN')
                elif re.search(r'\b' + re.escape(tk) + r'\b', desc_text, re.I):
                    techs.append(tk)
            if techs:
                entry.technologies = techs
                
        if entry.job_title or entry.company or entry.description:
            # Swap heuristics
            if entry.company and re.search(r'\b(developer|engineer|intern|trainee|manager|analyst|associate|lead|expert|consultant)\b', entry.company.lower()):
                entry.job_title, entry.company = entry.company, entry.job_title
            elif entry.job_title and re.search(r'\b(technologies|systems|solutions|private limited|pvt\.? ltd|inc\.?|llc|group|corporation|llp)\b', entry.job_title.lower()):
                entry.job_title, entry.company = entry.company, entry.job_title
                
            # Classify internship
            if (entry.job_title and re.search(r'\bintern(ship)?\b', entry.job_title, re.I)) or \
               (entry.company and re.search(r'\bintern(ship)?\b', entry.company, re.I)) or \
               (entry.description and any(re.search(r'\bintern(ship)?\b', d, re.I) for d in entry.description)):
                entry.employment_type = "Internship"
            
            # Clean up bullets
            if entry.job_title: entry.job_title = entry.job_title.strip("•* -")
            if entry.company: entry.company = entry.company.strip("•* -")
            
            schema.experience.append(entry)

    # Parse Projects
    proj_lines = []
    for block in sections["projects"]:
        for l in block:
            proj_lines.append(l)
    proj_lines.sort(key=lambda x: (x["top"], x["x0"]))
    
    if proj_lines:
        from collections import Counter
        sizes = [l["font_size"] for l in proj_lines]
        base_size = Counter(sizes).most_common(1)[0][0] if sizes else 10
        
        current_proj = None
        
        for l in proj_lines:
            text = l["text"].strip()
            if not text: continue
            
            if l["font_size"] > base_size + 1.5:
                # Category heading, ignore
                continue
            elif l["font_size"] > base_size + 0.1:
                # Project Title
                if current_proj:
                    schema.projects.append(current_proj)
                current_proj = ProjectEntry(name=text, description="")
            else:
                # Description
                if not current_proj:
                    if text.isupper() and len(text) > 5 and not re.search(r'^\d+$', text):
                        current_proj = ProjectEntry(name=text, description="")
                        continue
                    else:
                        current_proj = ProjectEntry(name="Project", description="")
                elif text.isupper() and len(text) > 5 and not re.search(r'^\d+$', text) and not text.startswith("HTTP"):
                    schema.projects.append(current_proj)
                    current_proj = ProjectEntry(name=text, description="")
                    continue
                    
                if current_proj.description:
                    current_proj.description += "\n" + text
                else:
                    current_proj.description = text
                    
        if current_proj:
            schema.projects.append(current_proj)
            
    # Summary
    summary_text = "\n".join("\n".join(l["text"] for l in b) for b in sections["summary"])
    if summary_text.strip():
        schema.summary = summary_text.strip()
                
    # Skills
    skills_text = ""
    for block in sections["skills"]:
        skills_text += "\n".join(l["text"] for l in block) + "\n"
    
    if skills_text:
        skills_text = skills_text.replace(":", ",")
        schema.skills.explicit = [s.strip() for s in re.split(r"[,|•\n]", skills_text) if s.strip() and len(s.strip()) < 40]

    # Certifications
    cert_lines = []
    for block in sections["certifications"]:
        for l in block:
            cert_lines.append(l)
    cert_lines.sort(key=lambda x: (x["top"], x["x0"]))
    
    if cert_lines:
        from collections import Counter
        sizes = [l["font_size"] for l in cert_lines]
        base_size = Counter(sizes).most_common(1)[0][0] if sizes else 10
        current_cert = []
        for l in cert_lines:
            text = l["text"].strip("-•* ")
            if not text: continue
            if l["font_size"] > base_size + 0.1 or text.isupper():
                if current_cert:
                    cert_str = " ".join(current_cert)
                    if re.search(r'\bintern(ship)?\b', cert_str, re.I) and not re.search(r'\bcertificat(e|ions?)?\b', cert_str, re.I):
                        schema.training.append(cert_str)
                    else:
                        schema.certifications.append(cert_str)
                current_cert = [text]
            else:
                if not current_cert:
                    current_cert = [text]
                else:
                    current_cert.append(text)
        if current_cert:
            cert_str = " ".join(current_cert)
            if re.search(r'\bintern(ship)?\b', cert_str, re.I) and not re.search(r'\bcertificat(e|ions?)?\b', cert_str, re.I):
                schema.training.append(cert_str)
            else:
                schema.certifications.append(cert_str)
                
    # Awards
    for block in sections["awards"]:
        for line in block:
            text = line["text"].strip("-•* ")
            if text and len(text) > 3:
                schema.awards.append(text)

    # Languages
    for block in sections["languages"]:
        for line in block:
            text = line["text"].strip("-•* ")
            if text and len(text) > 2 and "proficiency" not in text.lower():
                schema.languages.append(text)
                
    # Interests
    for block in sections["interests"]:
        for line in block:
            text = line["text"].strip("-•* ")
            if text and len(text) > 3:
                schema.interests.append(text)
                
    return schema
