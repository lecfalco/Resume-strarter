"""
parser.py — Extracts raw text from uploaded resume files.
Supports PDF and plain-text files. DOCX support requires python-docx.
"""
import io
import re
from typing import Tuple

import pdfplumber


# ── Common skill keywords to look for ───────────────────────────────────────
SKILL_KEYWORDS = [
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "kotlin", "swift", "ruby", "php", "scala", "r",
    # Web
    "react", "vue", "angular", "next.js", "html", "css", "tailwind",
    "fastapi", "django", "flask", "node.js", "express",
    # Data / AI
    "sql", "postgresql", "mysql", "mongodb", "redis",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
    "langchain", "openai", "huggingface",
    # DevOps / Cloud
    "docker", "kubernetes", "aws", "gcp", "azure", "git", "ci/cd", "linux",
    # Soft skills
    "leadership", "communication", "teamwork", "problem solving",
]


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF given its raw bytes."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Decode a plain-text resume."""
    return file_bytes.decode("utf-8", errors="ignore")


def extract_skills_from_text(text: str) -> list[str]:
    """
    Simple keyword-matching skill extractor.
    For production, replace with spaCy NER or a HuggingFace pipeline.
    """
    lower = text.lower()
    found = []
    for skill in SKILL_KEYWORDS:
        # whole-word match to avoid false positives
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, lower):
            found.append(skill.title())
    return list(dict.fromkeys(found))   # preserve order, deduplicate


def extract_name(text: str) -> str:
    """
    Heuristic: first non-empty line of the resume is usually the candidate's name.
    Replace with a proper NER model for better accuracy.
    """
    for line in text.splitlines():
        line = line.strip()
        if line and len(line.split()) <= 5 and not any(c.isdigit() for c in line):
            return line
    return "Unknown Candidate"


def extract_email(text: str) -> str | None:
    """Extract first email address found in the text."""
    match = re.search(r'[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else None


def parse_resume(file_bytes: bytes, filename: str) -> Tuple[str, str, str | None, list[str]]:
    """
    Main entry point called by the API.

    Returns:
        (raw_text, candidate_name, candidate_email, skills_list)
    """
    if filename.lower().endswith(".pdf"):
        raw_text = extract_text_from_pdf(file_bytes)
    else:
        # fallback: treat as plain text
        raw_text = extract_text_from_txt(file_bytes)

    name   = extract_name(raw_text)
    email  = extract_email(raw_text)
    skills = extract_skills_from_text(raw_text)

    return raw_text, name, email, skills
