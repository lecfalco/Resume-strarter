"""
scorer.py — Uses OpenAI to score a candidate's resume against a job description.

Set your key in a .env file:
    OPENAI_API_KEY=sk-...

If you don't have an OpenAI key yet, the module falls back to a simple
keyword-overlap scorer so the rest of the app still runs.
"""
import os
import json
import re
from dataclasses import dataclass

try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    _openai_available = False

from dotenv import load_dotenv

load_dotenv()

SHORTLIST_THRESHOLD   = 70   # score >= 70  → shortlisted
TALENT_POOL_THRESHOLD = 40   # score 40–69  → talent pool
                              # score < 40   → rejected


@dataclass
class ScoreResult:
    score: float          # 0–100
    summary: str          # 2-3 sentence human-readable explanation
    status: str           # "shortlisted" | "talent_pool" | "rejected"


# ── OpenAI scorer ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are an expert technical recruiter. You will be given a job description and a
candidate's resume text. Evaluate the candidate's fit for the role and respond
ONLY with a valid JSON object in this exact format (no markdown, no explanation):

{
  "score": <integer 0-100>,
  "summary": "<2-3 sentence explanation of fit, highlighting strengths and gaps>"
}

Scoring rubric:
- 80-100: Excellent fit — meets or exceeds all key requirements.
- 60-79 : Good fit — meets most requirements with minor gaps.
- 40-59 : Partial fit — relevant background but significant gaps.
- 20-39 : Weak fit — some tangential skills but mostly mismatched.
- 0-19  : No fit — clearly mismatched for this role.
"""


def _score_with_openai(resume_text: str, job_title: str,
                        job_description: str, required_skills: str,
                        experience_level: str) -> ScoreResult:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    user_message = f"""
JOB TITLE: {job_title}
EXPERIENCE LEVEL: {experience_level}
REQUIRED SKILLS: {required_skills}
JOB DESCRIPTION:
{job_description}

---

CANDIDATE RESUME:
{resume_text[:3000]}  
"""
    # Truncate resume to 3000 chars to stay within token limits for a demo

    response = client.chat.completions.create(
        model="gpt-4o-mini",          # cheap and fast — good for demos
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.2,
        max_tokens=300,
    )

    raw = response.choices[0].message.content.strip()
    data = json.loads(raw)
    score = float(data["score"])
    summary = data["summary"]
    return _build_result(score, summary)


# ── Fallback keyword scorer (no API key needed) ───────────────────────────────

def _score_with_keywords(resume_text: str, required_skills: str) -> ScoreResult:
    """
    Simple overlap scorer used when OpenAI is unavailable.
    Not smart — just for dev/testing without an API key.
    """
    required = [s.strip().lower() for s in required_skills.split(",") if s.strip()]
    if not required:
        return _build_result(50, "No required skills specified; defaulting to 50.")

    resume_lower = resume_text.lower()
    matched = [s for s in required if re.search(r'\b' + re.escape(s) + r'\b', resume_lower)]
    score = round((len(matched) / len(required)) * 100, 1)

    if matched:
        summary = (
            f"Keyword match: {len(matched)}/{len(required)} required skills found "
            f"({', '.join(matched[:4])}{'...' if len(matched) > 4 else ''}). "
            "This is a basic keyword match — enable OpenAI for deeper analysis."
        )
    else:
        summary = "No matching skills found via keyword search. Enable OpenAI for a full evaluation."

    return _build_result(score, summary)


def _build_result(score: float, summary: str) -> ScoreResult:
    if score >= SHORTLIST_THRESHOLD:
        status = "shortlisted"
    elif score >= TALENT_POOL_THRESHOLD:
        status = "talent_pool"
    else:
        status = "rejected"
    return ScoreResult(score=score, summary=summary, status=status)


# ── Public interface ──────────────────────────────────────────────────────────

def score_candidate(
    resume_text: str,
    job_title: str,
    job_description: str,
    required_skills: str,
    experience_level: str,
) -> ScoreResult:
    """
    Score a candidate against a job opening.
    Uses OpenAI if configured, otherwise falls back to keyword matching.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if _openai_available and api_key.startswith("sk-"):
        try:
            return _score_with_openai(
                resume_text, job_title, job_description,
                required_skills, experience_level
            )
        except Exception as e:
            print(f"[scorer] OpenAI call failed ({e}), falling back to keyword scorer.")

    return _score_with_keywords(resume_text, required_skills)
