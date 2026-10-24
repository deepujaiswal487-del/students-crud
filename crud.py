"""Database operations. All SQL is parameterized (no string-built queries)."""
import sqlite3
from datetime import date
from typing import Optional

COLUMNS = ["name", "date_of_birth", "email", "phone", "course", "address", "enrollment_date"]


def _row(r: sqlite3.Row) -> dict:
    return dict(r)


def _values(data: dict) -> list:
    out = []
    for c in COLUMNS:
        v = data.get(c)
        out.append(v.isoformat() if isinstance(v, date) else (str(v) if v is not None else None))
    return out


def create_student(conn: sqlite3.Connection, data: dict) -> dict:
    cur = conn.execute(
        f"INSERT INTO students ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
        _values(data),
    )
    conn.commit()
    return get_student(conn, cur.lastrowid)


def get_student(conn: sqlite3.Connection, student_id: int) -> Optional[dict]:
    r = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    return _row(r) if r else None


def list_students(
    conn: sqlite3.Connection,
    name: Optional[str] = None,
    course: Optional[str] = None,
    email: Optional[str] = None,
    born_after: Optional[date] = None,
    born_before: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[dict]:
    sql, params = "SELECT * FROM students WHERE 1=1", []
    if name:
        sql += " AND name LIKE ?"; params.append(f"%{name}%")
    if course:
        sql += " AND course LIKE ?"; params.append(f"%{course}%")
    if email:
        sql += " AND email = ?"; params.append(email)
    if born_after:
        sql += " AND date_of_birth > ?"; params.append(born_after.isoformat())
    if born_before:
        sql += " AND date_of_birth < ?"; params.append(born_before.isoformat())
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    params += [limit, skip]
    return [_row(r) for r in conn.execute(sql, params).fetchall()]


def count_students(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]


def update_student(conn: sqlite3.Connection, student_id: int, data: dict) -> Optional[dict]:
    if get_student(conn, student_id) is None:
        return None
    sets = ", ".join(f"{c} = ?" for c in COLUMNS)
    conn.execute(f"UPDATE students SET {sets} WHERE id = ?", _values(data) + [student_id])
    conn.commit()
    return get_student(conn, student_id)


def delete_student(conn: sqlite3.Connection, student_id: int) -> bool:
    cur = conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    return cur.rowcount > 0
