"""
Database setup using SQLite (easy local dev) via SQLAlchemy.
To switch to PostgreSQL, change DATABASE_URL and install psycopg2-binary.
"""
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./smarthire.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM Models ───────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id               = Column(Integer, primary_key=True, index=True)
    title            = Column(String, nullable=False)
    description      = Column(Text, nullable=False)
    required_skills  = Column(String, nullable=False)   # comma-separated
    experience_level = Column(String, nullable=False)
    department       = Column(String, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)


class Candidate(Base):
    __tablename__ = "candidates"

    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String, nullable=False)
    email            = Column(String, nullable=True)
    resume_text      = Column(Text, nullable=False)
    extracted_skills = Column(Text, nullable=False)
    match_score      = Column(Float, nullable=False)     # 0–100
    match_summary    = Column(Text, nullable=False)
    status           = Column(String, nullable=False)    # shortlisted | talent_pool | rejected
    job_id           = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    created_at       = Column(DateTime, default=datetime.utcnow)


class TalentPool(Base):
    __tablename__ = "talent_pool"

    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String, nullable=False)
    email            = Column(String, nullable=True)
    resume_text      = Column(Text, nullable=False)
    skills_tags      = Column(Text, nullable=False)      # comma-separated
    best_match_role  = Column(String, nullable=False)
    match_score      = Column(Float, nullable=False)
    created_at       = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Create all tables. Call once at startup."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
