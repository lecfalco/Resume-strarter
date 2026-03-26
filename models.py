from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class JobCreate(BaseModel):
    title: str
    description: str
    required_skills: str          # Comma-separated, e.g. "Python, FastAPI, SQL"
    experience_level: str         # "Junior" | "Mid" | "Senior"
    department: Optional[str] = None


class JobOut(JobCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateOut(BaseModel):
    id: int
    name: str
    email: Optional[str]
    extracted_skills: str
    match_score: float            # 0 – 100
    match_summary: str
    status: str                   # "shortlisted" | "talent_pool" | "rejected"
    job_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TalentPoolOut(BaseModel):
    id: int
    name: str
    email: Optional[str]
    skills_tags: str
    best_match_role: str
    match_score: float
    created_at: datetime

    class Config:
        from_attributes = True
