import pytest
from fastapi.testclient import TestClient

from app import ai
from app.database import connect, get_db, init_db
from app.main import app


@pytest.fixture()
def client(tmp_path):
    db_file = str(tmp_path / "test.db")
    init_db(db_file)

    def override():
        conn = connect(db_file)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def make(**kw):
    base = {"name": "Test User", "date_of_birth": "2004-05-01", "email": "t@example.com"}
    base.update(kw)
    return base


def test_create_and_get(client):
    r = client.post("/students", json=make(course="Python"))
    assert r.status_code == 201
    sid = r.json()["id"]
    g = client.get(f"/students/{sid}")
    assert g.status_code == 200 and g.json()["course"] == "Python"


def test_list_and_filters(client):
    client.post("/students", json=make(name="Ann", email="a@x.com", date_of_birth="2003-01-01", course="Web"))
    client.post("/students", json=make(name="Bob", email="b@x.com", date_of_birth="2006-01-01", course="Data"))
    assert len(client.get("/students").json()) == 2
    assert [s["name"] for s in client.get("/students?born_after=2005-01-01").json()] == ["Bob"]
    assert [s["name"] for s in client.get("/students?course=web").json()] == ["Ann"]
    assert [s["name"] for s in client.get("/students?name=bo").json()] == ["Bob"]
    assert len(client.get("/students?limit=1").json()) == 1


def test_put_replaces(client):
    sid = client.post("/students", json=make(course="Old")).json()["id"]
    r = client.put(f"/students/{sid}", json=make(name="New Name"))
    assert r.status_code == 200
    assert r.json()["name"] == "New Name" and r.json()["course"] is None


def test_patch_partial(client):
    sid = client.post("/students", json=make(course="Old")).json()["id"]
    r = client.patch(f"/students/{sid}", json={"course": "New"})
    assert r.status_code == 200
    assert r.json()["course"] == "New" and r.json()["name"] == "Test User"


def test_patch_validation(client):
    sid = client.post("/students", json=make()).json()["id"]
    assert client.patch(f"/students/{sid}", json={"date_of_birth": "2999-01-01"}).status_code == 422
    assert client.patch(f"/students/{sid}", json={"email": "not-an-email"}).status_code == 422


def test_delete(client):
    sid = client.post("/students", json=make()).json()["id"]
    assert client.delete(f"/students/{sid}").status_code == 204
    assert client.get(f"/students/{sid}").status_code == 404


def test_missing_records_404(client):
    assert client.get("/students/999").status_code == 404
    assert client.put("/students/999", json=make()).status_code == 404
    assert client.patch("/students/999", json={"name": "x"}).status_code == 404
    assert client.delete("/students/999").status_code == 404


def test_validation_errors(client):
    assert client.post("/students", json=make(name="   ")).status_code == 422
    assert client.post("/students", json=make(email="bad")).status_code == 422
    assert client.post("/students", json=make(date_of_birth="2999-01-01")).status_code == 422
    assert client.post("/students", json=make(phone="abc")).status_code == 422
    assert client.post("/students", json={"name": "No Contact", "date_of_birth": "2004-01-01"}).status_code == 422
    assert client.post("/students", json=make(enrollment_date="2000-01-01")).status_code == 422
    assert client.post("/students", json={"name": "x"}).status_code == 422


def test_phone_only_is_valid(client):
    r = client.post("/students", json={"name": "P", "date_of_birth": "2004-01-01", "phone": "+91 98765 43210"})
    assert r.status_code == 201


def test_duplicate_email_409(client):
    client.post("/students", json=make())
    assert client.post("/students", json=make(name="Other")).status_code == 409


def test_persistence(tmp_path):
    f = str(tmp_path / "p.db")
    init_db(f)
    c1 = connect(f)
    from app import crud
    from datetime import date
    crud.create_student(c1, {"name": "Z", "date_of_birth": date(2004, 1, 1), "email": "z@x.com"})
    c1.close()
    c2 = connect(f)  # new connection simulates a restart
    assert crud.count_students(c2) == 1


# ---------------------------------------------------------- optional AI tests
def test_ai_context_grounding(client, monkeypatch):
    client.post("/students", json=make(name="Old", email="o@x.com", date_of_birth="2003-01-01"))
    client.post("/students", json=make(name="Young1", email="y1@x.com", date_of_birth="2006-03-01"))
    client.post("/students", json=make(name="Young2", email="y2@x.com", date_of_birth="2007-03-01"))
    seen = {}

    def fake(question, context):
        seen["ctx"] = context
        return "stub answer"

    monkeypatch.setattr(ai, "ask_ollama", fake)
    r = client.post("/ai/ask", json={"question": "List students born after 2005"})
    assert r.status_code == 200 and r.json()["records_used"] == 2
    assert "Young1" in seen["ctx"] and "Young2" in seen["ctx"] and "Old" not in seen["ctx"]

    r = client.post("/ai/ask", json={"question": "How many students are there?"})
    assert "Total number of students in the database: 3." in seen["ctx"]


def test_ai_unavailable_returns_503(client, monkeypatch):
    def boom(q, c):
        raise ai.OllamaUnavailable("down")
    monkeypatch.setattr(ai, "ask_ollama", boom)
    assert client.post("/ai/ask", json={"question": "How many students?"}).status_code == 503
