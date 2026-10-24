"""Optional bonus: natural-language questions answered by a local Ollama model.

Safety design:
  * The model NEVER writes or runs SQL.
  * Backend code decides what to retrieve using fixed, parameterized queries
    (count, born after/before/in a year, course, name match).
  * Retrieved records are given to the model as context, and the prompt tells
    it to answer only from that context.
"""
import os
import re
import sqlite3
from datetime import date

import httpx

from . import crud

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
MAX_RECORDS = 50

SYSTEM_PROMPT = (
    "You answer questions about a student database. Use ONLY the facts and "
    "records in the CONTEXT. If the context does not contain the answer, say "
    "you don't have that information. Never invent students or numbers. "
    "Be concise and use the exact numbers given in the context."
)


class OllamaUnavailable(Exception):
    pass


def retrieve_context(conn: sqlite3.Connection, question: str) -> tuple[str, int]:
    """Build a text context from the DB using safe, predefined queries."""
    q = question.lower()
    total = crud.count_students(conn)
    facts = [f"Total number of students in the database: {total}."]
    filters: dict = {}

    m = re.search(r"born\s+after\s+(?:the\s+year\s+)?(\d{4})", q)
    if m:
        filters["born_after"] = date(int(m.group(1)), 12, 31)
        facts.append(f"Filter applied: born after the year {m.group(1)} (i.e. from {int(m.group(1)) + 1} onward).")
    m = re.search(r"born\s+before\s+(?:the\s+year\s+)?(\d{4})", q)
    if m:
        filters["born_before"] = date(int(m.group(1)), 1, 1)
        facts.append(f"Filter applied: born before the year {m.group(1)}.")
    m = re.search(r"born\s+in\s+(\d{4})", q)
    if m:
        y = int(m.group(1))
        filters["born_after"], filters["born_before"] = date(y - 1, 12, 31), date(y + 1, 1, 1)
        facts.append(f"Filter applied: born in {y}.")

    all_rows = crud.list_students(conn, limit=10_000)
    for c in sorted({r["course"] for r in all_rows if r["course"]}):
        if c.lower() in q:
            filters["course"] = c
            facts.append(f"Filter applied: course = {c}.")
            break

    if not filters:  # maybe the question names a student
        for r in all_rows:
            if r["name"].lower() in q or r["name"].split()[0].lower() in re.findall(r"[a-z]+", q):
                filters["name"] = r["name"]
                break

    rows = crud.list_students(conn, limit=MAX_RECORDS, **filters) if filters else all_rows[:MAX_RECORDS]
    if filters:
        full = crud.list_students(conn, limit=10_000, **filters)
        facts.append(f"Number of students matching the filter: {len(full)}.")
    lines = [
        f"- id={r['id']}, name={r['name']}, dob={r['date_of_birth']}, course={r['course'] or 'n/a'}, "
        f"email={r['email'] or 'n/a'}, phone={r['phone'] or 'n/a'}, enrolled={r['enrollment_date'] or 'n/a'}"
        for r in rows
    ]
    context = "\n".join(facts) + "\nRecords:\n" + ("\n".join(lines) if lines else "(none)")
    return context, len(rows)


def ask_ollama(question: str, context: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
        ],
    }
    try:
        r = httpx.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except (httpx.HTTPError, KeyError) as exc:
        raise OllamaUnavailable(str(exc)) from exc
