from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_diagnose() -> None:
    payload = {
        "request_id": "req-test-001",
        "session_id": "sess-test-001",
        "student_id": "stu-001",
        "subject": "math",
        "input_mode": "text",
        "problem_text": "1/2 + 1/3 = ?",
        "student_answer": "5/6",
        "expected_answer": "5/6",
        "knowledge_points": ["fraction-addition-unlike-denominator"],
    }

    resp = client.post("/api/v1/diagnose", json=payload)
    data = resp.json()

    assert resp.status_code == 200
    assert data["intent"] == "diagnose-and-coach"
    assert data["request_id"] == "req-test-001"
    assert data["status"] == "completed"
    assert data["confidence"] == "high"
    assert data["card"]["style"] == "visual"
    assert data["card"]["suggested_questions"]
    assert "fraction-addition-unlike-denominator" in data["updated_mastery"]
