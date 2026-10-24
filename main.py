"""Students Database CRUD API (FastAPI + SQLite) with an optional Ollama endpoint."""
import sqlite3
import sys
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status

from . import ai, crud
from .database import get_db, init_db
from .schemas import (AskRequest, AskResponse, Student, StudentBase,
                      StudentCreate, StudentUpdate)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Students Database API",
    description="CRUD API for student records, with an optional local-AI (Ollama) endpoint.",
    version="1.0.0",
    lifespan=lifespan,
)

NOT_FOUND = "Student with id {} not found"
DUPLICATE = "A student with this email already exists"


@app.get("/", tags=["health"])
def root():
    return {"message": "Students API is running", "docs": "/docs"}


@app.post("/students", response_model=Student, status_code=status.HTTP_201_CREATED, tags=["students"])
def create_student(student: StudentCreate, db: sqlite3.Connection = Depends(get_db)):
    try:
        return crud.create_student(db, student.model_dump())
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE)


@app.get("/students", response_model=list[Student], tags=["students"])
def list_students(
    name: Optional[str] = Query(None, description="Partial name match"),
    course: Optional[str] = Query(None, description="Partial course match"),
    email: Optional[str] = Query(None, description="Exact email match"),
    born_after: Optional[date] = Query(None, description="DOB strictly after (YYYY-MM-DD)"),
    born_before: Optional[date] = Query(None, description="DOB strictly before (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: sqlite3.Connection = Depends(get_db),
):
    return crud.list_students(db, name, course, email, born_after, born_before, skip, limit)


@app.get("/students/{student_id}", response_model=Student, tags=["students"])
def get_student(student_id: int, db: sqlite3.Connection = Depends(get_db)):
    s = crud.get_student(db, student_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND.format(student_id))
    return s


@app.put("/students/{student_id}", response_model=Student, tags=["students"])
def replace_student(student_id: int, student: StudentCreate, db: sqlite3.Connection = Depends(get_db)):
    """Full update: every field is replaced by the request body."""
    try:
        s = crud.update_student(db, student_id, student.model_dump())
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND.format(student_id))
    return s


@app.patch("/students/{student_id}", response_model=Student, tags=["students"])
def patch_student(student_id: int, changes: StudentUpdate, db: sqlite3.Connection = Depends(get_db)):
    """Partial update: only the fields you send are changed."""
    existing = crud.get_student(db, student_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND.format(student_id))
    merged = {**existing, **changes.model_dump(exclude_unset=True)}
    merged.pop("id", None)
    try:
        validated = StudentBase(**merged)  # re-run all validation rules on the merged record
    except ValueError as exc:
        from fastapi.exceptions import RequestValidationError
        raise RequestValidationError(exc.errors())
    try:
        return crud.update_student(db, student_id, validated.model_dump())
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE)


@app.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["students"])
def delete_student(student_id: int, db: sqlite3.Connection = Depends(get_db)):
    if not crud.delete_student(db, student_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND.format(student_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- Optional AI
@app.post("/ai/ask", response_model=AskResponse, tags=["ai (optional)"])
def ask(req: AskRequest, db: sqlite3.Connection = Depends(get_db)):
    """Ask a natural-language question. Backend retrieves records; model only summarizes them."""
    context, n = ai.retrieve_context(db, req.question)
    try:
        answer = ai.ask_ollama(req.question, context)
    except ai.OllamaUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Ollama is not reachable or the model '{ai.OLLAMA_MODEL}' is not pulled. "
            f"Start it with 'ollama serve' and run 'ollama pull {ai.OLLAMA_MODEL}'. ({exc})",
        )
    return AskResponse(question=req.question, answer=answer, model=ai.OLLAMA_MODEL, records_used=n)
