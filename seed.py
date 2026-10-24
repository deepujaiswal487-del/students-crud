"""Load dummy (fake) sample data. Usage: python seed.py"""
from app.database import init_db, connect
from app import crud

SAMPLE = [
    dict(name="Aarav Sharma", date_of_birth="2004-03-12", email="aarav.sharma@example.com", phone="+91 98765 43210", course="Python Backend", enrollment_date="2024-07-01"),
    dict(name="Diya Patel", date_of_birth="2005-11-25", email="diya.patel@example.com", course="Data Science", address="12 Sample Street, Ahmedabad", enrollment_date="2024-07-01"),
    dict(name="Rohan Mehta", date_of_birth="2006-02-08", email="rohan.mehta@example.com", phone="9123456780", course="Python Backend", enrollment_date="2025-01-10"),
    dict(name="Ananya Iyer", date_of_birth="2003-09-30", phone="+91 99887 76655", course="Web Development", enrollment_date="2023-07-15"),
    dict(name="Kabir Singh", date_of_birth="2007-06-18", email="kabir.singh@example.com", course="Data Science", enrollment_date="2025-07-01"),
    dict(name="Meera Nair", date_of_birth="2005-01-05", email="meera.nair@example.com", phone="+91 90000 11122", course="Web Development"),
]

if __name__ == "__main__":
    init_db()
    conn = connect()
    if crud.count_students(conn):
        print("Database already has data; skipping seed.")
    else:
        for s in SAMPLE:
            crud.create_student(conn, {k: __import__("datetime").date.fromisoformat(v) if k in ("date_of_birth", "enrollment_date") else v for k, v in s.items()})
        print(f"Inserted {len(SAMPLE)} dummy students.")
