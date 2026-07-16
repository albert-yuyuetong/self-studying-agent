from fastapi.testclient import TestClient

from app.api.v1.routes import orchestrator
from app.main import app


client = TestClient(app)


def _mock_standard_answer_analysis(reference_answer: str = "5/6") -> dict[str, object]:
    return {
        "question_type": "standard-answer",
        "answer_analysis": {
            "normalized_problem": "1/2 + 1/3 = ?",
            "reference_answer": reference_answer,
            "solution_outline": ["先通分，再相加。"],
            "evaluation_focus": ["答案是否正确", "是否先通分"],
            "summary": "这题有标准答案，可以先按分数加法判断孩子是否漏掉通分。",
            "confidence": 0.91,
        },
        "reference_answer_source": "llm-derived" if reference_answer else None,
    }


def test_health() -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_diagnose(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator.analyzer, "analyze", lambda **_: _mock_standard_answer_analysis())

    payload = {
        "request_id": "req-test-001",
        "session_id": "sess-test-001",
        "student_id": "stu-001",
        "subject": "math",
        "input_mode": "text",
        "problem_text": "1/2 + 1/3 = ?",
        "student_answer": "5/6",
        "knowledge_points": ["fraction-addition-unlike-denominator"],
    }

    resp = client.post("/api/v1/diagnose", json=payload)
    data = resp.json()

    assert resp.status_code == 200
    assert data["intent"] == "diagnose-and-coach"
    assert data["request_id"] == "req-test-001"
    assert data["status"] == "completed"
    assert data["confidence"] == "high"
    assert data["question_type"] == "standard-answer"
    assert data["reference_answer_source"] == "llm-derived"
    assert data["card"]["style"] == "visual"
    assert data["card"]["suggested_questions"]
    assert "答对了" in data["diagnosis"]
    assert "fraction-addition-unlike-denominator" in data["updated_mastery"]


def test_diagnose_infers_fraction_process_error(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator.analyzer, "analyze", lambda **_: _mock_standard_answer_analysis())

    payload = {
        "request_id": "req-test-002",
        "student_id": "stu-002",
        "subject": "math",
        "input_mode": "text",
        "problem_text": "1/2 + 1/3 = ?",
        "student_answer": "2/5",
    }

    resp = client.post("/api/v1/diagnose", json=payload)
    data = resp.json()

    assert resp.status_code == 200
    assert data["error_type"] == "process"
    assert data["confidence"] == "medium"
    assert data["question_type"] == "standard-answer"
    assert data["reference_answer_source"] == "llm-derived"
    assert "common-denominator" in data["knowledge_points"]
    assert any("为什么" in question for question in data["card"]["suggested_questions"])


def test_diagnose_uses_llm_reference_answer(monkeypatch) -> None:
    def fake_analyze(**_: object) -> dict[str, object]:
        return _mock_standard_answer_analysis()

    monkeypatch.setattr(orchestrator.analyzer, "analyze", fake_analyze)

    payload = {
        "request_id": "req-test-003",
        "student_id": "stu-003",
        "subject": "math",
        "input_mode": "photo",
        "problem_text": "",
        "student_answer": "2/5",
        "attachments": ["https://example.com/problem.png"],
    }

    resp = client.post("/api/v1/diagnose", json=payload)
    data = resp.json()

    assert resp.status_code == 200
    assert data["question_type"] == "standard-answer"
    assert data["reference_answer_source"] == "llm-derived"
    assert data["error_type"] == "process"
    assert data["answer_analysis"]["reference_answer"] == "5/6"


def test_diagnose_standard_answer_degrades_without_llm_reference(monkeypatch) -> None:
    monkeypatch.setattr(
        orchestrator.analyzer,
        "analyze",
        lambda **_: _mock_standard_answer_analysis(reference_answer=""),
    )

    payload = {
        "request_id": "req-test-005",
        "student_id": "stu-005",
        "subject": "math",
        "input_mode": "text",
        "problem_text": "1/2 + 1/3 = ?",
        "student_answer": "2/5",
    }

    resp = client.post("/api/v1/diagnose", json=payload)
    data = resp.json()

    assert resp.status_code == 200
    assert data["question_type"] == "standard-answer"
    assert data["status"] == "degraded"
    assert data["error_type"] is None
    assert "模型生成参考答案" in data["clarifying_question"]


def test_diagnose_open_ended_skips_grading(monkeypatch) -> None:
    def fake_analyze(**_: object) -> dict[str, object]:
        return {
            "question_type": "open-ended",
            "answer_analysis": {
                "normalized_problem": "请结合文章内容谈谈你的感受。",
                "reference_answer": None,
                "solution_outline": ["先说观点，再给依据。"],
                "evaluation_focus": ["是否切题", "是否有依据", "表达是否完整"],
                "summary": "这是一道开放题，没有唯一标准答案，更适合按观点、依据和表达完整度辅导。",
                "confidence": 0.88,
            },
            "reference_answer_source": None,
        }

    monkeypatch.setattr(orchestrator.analyzer, "analyze", fake_analyze)

    payload = {
        "request_id": "req-test-004",
        "student_id": "stu-004",
        "subject": "chinese",
        "input_mode": "photo",
        "problem_text": "",
        "student_answer": "我觉得主人公很勇敢，因为他在困难面前没有退缩。",
        "attachments": ["https://example.com/reading.png"],
    }

    resp = client.post("/api/v1/diagnose", json=payload)
    data = resp.json()

    assert resp.status_code == 200
    assert data["question_type"] == "open-ended"
    assert data["error_type"] is None
    assert data["status"] == "completed"
    assert data["answer_analysis"]["evaluation_focus"]
    assert any("观点" in step for step in data["card"]["coaching_steps"])
