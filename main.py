"""
main.py — SmartHire FastAPI backend
Run with: uvicorn main:app --reload
Docs at:  http://localhost:8000/docs
"""
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from database import init_db, get_db, Job, Candidate, TalentPool
from models import JobCreate, JobOut, CandidateOut, TalentPoolOut
from parser import parse_resume
from scorer import score_candidate

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SmartHire API",
    description="AI-powered applicant screening platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite / CRA
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "SmartHire API is running 🚀"}


# ── Jobs ─────────────────────────────────────────────────────────────────────

@app.post("/jobs", response_model=JobOut, tags=["Jobs"])
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    """Create a new job opening."""
    db_job = Job(**job.model_dump())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


@app.get("/jobs", response_model=List[JobOut], tags=["Jobs"])
def list_jobs(db: Session = Depends(get_db)):
    """List all job openings."""
    return db.query(Job).order_by(Job.created_at.desc()).all()


@app.get("/jobs/{job_id}", response_model=JobOut, tags=["Jobs"])
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/jobs/{job_id}", tags=["Jobs"])
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"message": f"Job {job_id} deleted."}


# ── Candidates ────────────────────────────────────────────────────────────────

@app.post("/jobs/{job_id}/apply", response_model=CandidateOut, tags=["Candidates"])
async def apply_for_job(
    job_id: int,
    resume: UploadFile = File(..., description="PDF or TXT resume"),
    db: Session = Depends(get_db),
):
    """
    Upload a resume for a specific job.
    The API will parse the resume, score it with AI, and determine candidate status.
    """
    # 1. Fetch the job
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # 2. Parse the resume
    file_bytes = await resume.read()
    raw_text, name, email, skills = parse_resume(file_bytes, resume.filename)

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from the uploaded file.")

    # 3. Score with AI
    result = score_candidate(
        resume_text=raw_text,
        job_title=job.title,
        job_description=job.description,
        required_skills=job.required_skills,
        experience_level=job.experience_level,
    )

    # 4. Save candidate
    candidate = Candidate(
        name=name,
        email=email,
        resume_text=raw_text,
        extracted_skills=", ".join(skills),
        match_score=result.score,
        match_summary=result.summary,
        status=result.status,
        job_id=job_id,
    )
    db.add(candidate)

    # 5. If talent_pool, also save to TalentPool table
    if result.status == "talent_pool":
        talent_entry = TalentPool(
            name=name,
            email=email,
            resume_text=raw_text,
            skills_tags=", ".join(skills),
            best_match_role=job.title,
            match_score=result.score,
        )
        db.add(talent_entry)

    db.commit()
    db.refresh(candidate)
    return candidate


@app.get("/jobs/{job_id}/candidates", response_model=List[CandidateOut], tags=["Candidates"])
def list_candidates(job_id: int, db: Session = Depends(get_db)):
    """Get all candidates for a job, sorted by match score (highest first)."""
    return (
        db.query(Candidate)
        .filter(Candidate.job_id == job_id)
        .order_by(Candidate.match_score.desc())
        .all()
    )


@app.get("/candidates/{candidate_id}", response_model=CandidateOut, tags=["Candidates"])
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


# ── Talent Pool ───────────────────────────────────────────────────────────────

@app.get("/talent-pool", response_model=List[TalentPoolOut], tags=["Talent Pool"])
def list_talent_pool(skill: str = None, db: Session = Depends(get_db)):
    """
    List all candidates in the talent pool.
    Optionally filter by skill keyword: /talent-pool?skill=python
    """
    query = db.query(TalentPool)
    if skill:
        query = query.filter(TalentPool.skills_tags.ilike(f"%{skill}%"))
    return query.order_by(TalentPool.match_score.desc()).all()


@app.get("/talent-pool/search", response_model=List[TalentPoolOut], tags=["Talent Pool"])
def search_talent_pool(role: str, db: Session = Depends(get_db)):
    """
    Search the talent pool by role keyword.
    Example: /talent-pool/search?role=backend+engineer
    """
    return (
        db.query(TalentPool)
        .filter(TalentPool.best_match_role.ilike(f"%{role}%"))
        .order_by(TalentPool.match_score.desc())
        .all()
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/stats", tags=["Stats"])
def get_stats(db: Session = Depends(get_db)):
    """Dashboard summary statistics."""
    total_jobs        = db.query(Job).count()
    total_candidates  = db.query(Candidate).count()
    shortlisted       = db.query(Candidate).filter(Candidate.status == "shortlisted").count()
    talent_pool_count = db.query(TalentPool).count()

    avg_score_row = db.query(Candidate).all()
    avg_score = (
        round(sum(c.match_score for c in avg_score_row) / len(avg_score_row), 1)
        if avg_score_row else 0
    )

    return {
        "total_jobs":        total_jobs,
        "total_candidates":  total_candidates,
        "shortlisted":       shortlisted,
        "talent_pool":       talent_pool_count,
        "avg_match_score":   avg_score,
    }
