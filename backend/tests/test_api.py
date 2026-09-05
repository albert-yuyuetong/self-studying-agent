"""Integration tests use a scripted model boundary, never a live paid model.

These assert orchestration/data guarantees, not the model's academic accuracy.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.profile_repository import SQLiteTutorRepository
from app.schemas.diagnosis import (
    Assessment, Lesson, LessonStep, PracticeTask, SkillDescriptor,
    SkillEvidence, TaskAnalysis, TeachingStrategy, Verification,
)
from app.services.tutor_engine import ModelUnavailable


class ScriptedEngine:
    enabled = True

    def __init__(self):
        self.calls = []
        self.missing = []
        self.confidence = 0.95
        self.reliable = True
        self.fail = False
        self.extra_evidence = False

    def analyze(self, req, profile, history):
        self.calls.append(("analyze", req.model_copy(deep=True), profile.model_copy(deep=True), history))
        if self.fail:
            raise ModelUnavailable("模型暂不可用")
        # Deliberately return evidence even without an answer to test the hard gate.
        return TaskAnalysis(
            subject=req.subject, task_summary=req.problem_text, task_type="动态任务描述",
            missing_information=self.missing, learning_objectives=["基于条件解释"],
            skills=[SkillDescriptor(subject=req.subject, name="条件与证据")],
            reference_solution=["可验证的参考步骤"],
            assessment=Assessment(
                verdict="supported", summary=req.student_answer or "不应被保留的无作答评估",
                evidence=[req.student_answer or "不存在的作答"], confidence=self.confidence,
            ),
            skill_evidence=[SkillEvidence(
                subject=req.subject, name="条件与证据", outcome="demonstrated",
                evidence=req.student_answer or "不存在的作答", confidence=self.confidence,
            )],
            confidence=self.confidence,
        )

    def plan(self, req, profile, analysis, history):
        self.calls.append(("plan", req, profile, history))
        return TeachingStrategy(
            approach=req.requested_strategy or "逐步提问",
            rationale=["根据用户目标组织讲解"], profile_used=[profile.learning_goal], pace=profile.pace,
        )

    def teach(self, req, profile, analysis, strategy, history):
        self.calls.append(("teach", req, profile, history))
        return Lesson(
            title="理解任务", goal="说明依据",
            steps=[LessonStep(title="分析", explanation=req.problem_text, question="依据是什么？", checkpoint="能指出具体依据")],
            parent_tips=["先听完整表达"], understanding_checks=["条件变化会怎样？"],
            practice=[PracticeTask(id="p1", prompt="解释两个对照组仅改变一个变量的原因。",
                                   purpose="迁移", hints=["比较结果的归因"], success_criteria=["指出混杂因素"])],
            recap="回到证据",
        )

    def verify(self, req, profile, analysis, lesson, history):
        self.calls.append(("verify", req, profile, history))
        approved = list(analysis.skill_evidence)
        if self.extra_evidence:
            approved.append(SkillEvidence(subject=req.subject, name="凭空出现的技能",
                                          outcome="demonstrated", evidence="无来源", confidence=1))
        return Verification(reliable=self.reliable, approved_evidence=approved,
                            issues=[] if self.reliable else ["参考步骤有矛盾"])


@pytest.fixture
def setup(tmp_path):
    repo = SQLiteTutorRepository(str(tmp_path / "tutor.sqlite3"))
    engine = ScriptedEngine()
    return TestClient(create_app(repo, engine)), repo, engine


def payload(**overrides):
    return {"request_id": "r1", "student_id": "learner", "session_id": "s1",
            "subject": "实验设计", "problem_text": "如何比较两种肥料对幼苗的影响？",
            "student_answer": "只改变肥料，控制光照、水分和幼苗初始条件。", **overrides}


def test_health_and_profile(setup):
    client, _, _ = setup
    assert client.get("/api/v1/health").json()["model_configured"] is True
    assert client.get("/api/v1/profiles/learner").json()["skills"] == {}
    saved = client.put("/api/v1/profiles/learner", json={
        "grade": "初二", "learning_goal": "独立解释依据", "interests": ["园艺"], "pace": "step-by-step",
    })
    assert saved.status_code == 200
    assert saved.json()["interests"] == ["园艺"]


@pytest.mark.parametrize("subject,problem,answer", [
    ("物理实验", "设计测量未知液体密度的方案。", "测量质量和体积，并说明单位及误差来源。"),
    ("历史", "比较两份材料对事件原因的不同解释。材料A强调税收，B强调政治权利。", "A侧重经济，B侧重政治，需核对作者立场。"),
    ("编程", "解释 for i in range(3): print(i) 的输出。", "输出0、1、2，不含终点3。"),
    ("几何证明", "说明同一平面内两条直线都垂直于第三条直线时的关系。", "根据同位角相等可证明它们平行。"),
    ("自定义跨学科任务", "设计一个兼顾隔热与可回收性的包装方案，并说明取舍。", "比较导热、材料来源和回收流程。"),
])
def test_unseen_tasks_use_full_input_and_profile(setup, subject, problem, answer):
    client, _, engine = setup
    client.put("/api/v1/profiles/learner", json={"interests": ["航天"], "notes": "先讲具体例子"})
    response = client.post("/api/v1/tutor", json=payload(subject=subject, problem_text=problem, student_answer=answer))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["analysis"]["assessment"]["summary"] == answer
    assert engine.calls[0][1].student_answer == answer
    assert engine.calls[0][2].interests == ["航天"]
    assert data["lesson"]["practice"][0]["success_criteria"]
    assert len(data["profile"]["skills"]) == 1


@pytest.mark.parametrize("answer", [None, "", "   "])
def test_no_answer_never_penalizes_profile(setup, answer):
    client, _, _ = setup
    data = client.post("/api/v1/tutor", json=payload(student_answer=answer)).json()
    assert data["guidance_mode"] == "pre-answer"
    assert data["analysis"]["assessment"]["verdict"] == "not-submitted"
    assert data["profile"]["skills"] == {}
    assert data["analysis"]["skill_evidence"] == []


def test_missing_problem_does_not_call_model(setup):
    client, _, engine = setup
    data = client.post("/api/v1/tutor", json=payload(problem_text="", student_answer=None)).json()
    assert data["status"] == "need_clarification"
    assert engine.calls == []
    assert data["lesson"] is None


def test_missing_source_requests_clarification(setup):
    client, _, engine = setup
    engine.missing = ["请提供题目引用的两份完整材料。"]
    data = client.post("/api/v1/tutor", json=payload()).json()
    assert data["status"] == "need_clarification"
    assert data["clarifying_questions"] == engine.missing
    assert data["analysis"]["reference_solution"] == []
    assert [call[0] for call in engine.calls] == ["analyze"]
    assert data["profile"]["skills"] == {}


def test_request_id_is_idempotent_and_conflict_checked(setup):
    client, _, engine = setup
    first = client.post("/api/v1/tutor", json=payload())
    count = len(engine.calls)
    again = client.post("/api/v1/tutor", json=payload())
    assert again.json() == first.json()
    assert len(engine.calls) == count
    assert client.post("/api/v1/tutor", json=payload(student_answer="改变了内容")).status_code == 409


def test_regenerating_same_attempt_never_double_counts(setup):
    client, _, _ = setup
    first = client.post("/api/v1/tutor", json=payload(attempt_id="a1")).json()
    again = client.post("/api/v1/tutor", json=payload(
        request_id="r2", attempt_id="a2", requested_strategy="用类比重新解释",
    )).json()
    assert again["profile"]["skills"] == first["profile"]["skills"]
    assert len(again["profile"]["skills"]) == 1
    assert next(iter(again["profile"]["skills"].values()))["demonstrated_count"] == 1


def test_low_confidence_does_not_update_profile(setup):
    client, _, engine = setup
    engine.confidence = 0.7
    data = client.post("/api/v1/tutor", json=payload()).json()
    assert data["status"] == "completed"
    assert data["profile"]["skills"] == {}
    assert data["warnings"]


def test_failed_review_withholds_lesson_and_reference(setup):
    client, _, engine = setup
    engine.reliable = False
    data = client.post("/api/v1/tutor", json=payload()).json()
    assert data["status"] == "degraded"
    assert data["lesson"] is None
    assert data["analysis"]["reference_solution"] == []
    assert data["analysis"]["assessment"]["verdict"] == "uncertain"
    assert data["profile"]["skills"] == {}


def test_reviewer_cannot_invent_profile_evidence(setup):
    client, _, engine = setup
    engine.extra_evidence = True
    data = client.post("/api/v1/tutor", json=payload()).json()
    assert {skill["name"] for skill in data["profile"]["skills"].values()} == {"条件与证据"}


def test_outage_can_retry_same_request_without_polluting_history(setup):
    client, _, engine = setup
    engine.fail = True
    failed = client.post("/api/v1/tutor", json=payload()).json()
    assert failed["status"] == "degraded"
    assert failed["profile"]["skills"] == {}
    engine.fail = False
    assert client.post("/api/v1/tutor", json=payload()).json()["status"] == "completed"


def test_session_cannot_be_read_or_used_by_another_student(setup):
    client, _, _ = setup
    client.post("/api/v1/tutor", json=payload())
    assert client.get("/api/v1/sessions/s1", params={"student_id": "other"}).status_code == 404
    assert client.post("/api/v1/tutor", json=payload(student_id="other")).status_code == 404


def test_followup_and_feedback_reach_next_turn(setup):
    client, _, engine = setup
    first = client.post("/api/v1/tutor", json=payload()).json()
    feedback = {
        "feedback_id": "f1", "student_id": "learner", "session_id": "s1",
        "turn_id": first["turn_id"], "useful": False, "child_understood": False,
        "comment": "仍不理解为什么只能改变一个条件",
    }
    saved = client.post("/api/v1/feedback", json=feedback)
    assert saved.status_code == 200
    assert saved.json()["profile"]["skills"] == first["profile"]["skills"]
    assert client.post("/api/v1/feedback", json=feedback).json()["duplicate"] is True
    followup = client.post("/api/v1/tutor", json=payload(
        request_id="r2", problem_text="", student_answer=None, follow_up="请解释控制变量的作用",
    ))
    assert followup.status_code == 200
    analyze_call = [item for item in engine.calls if item[0] == "analyze"][-1]
    assert analyze_call[1].problem_text == payload()["problem_text"]
    assert analyze_call[1].follow_up == "请解释控制变量的作用"
    assert "仍不理解" in str(analyze_call[3])


def test_profile_observations_cannot_be_overwritten_by_profile_form(setup):
    client, _, _ = setup
    first = client.post("/api/v1/tutor", json=payload()).json()
    updated = client.put("/api/v1/profiles/learner", json={"display_name": "小明"}).json()
    assert updated["skills"] == first["profile"]["skills"]
    assert client.put("/api/v1/profiles/learner", json={"skills": {}}).status_code == 422


def test_invalid_inputs_rejected(setup):
    client, _, _ = setup
    assert client.post("/api/v1/tutor", json=payload(student_id=" ")).status_code == 422
    assert client.post("/api/v1/tutor", json=payload(attachments=["file:///secret"])).status_code == 422
    assert client.post("/api/v1/tutor", json=payload(attachments=["data:image/png;base64,invalid"])).status_code == 422
    assert client.post("/api/v1/tutor", json=payload(unexpected="field")).status_code == 422


def test_legacy_url_uses_new_workflow(setup):
    client, _, _ = setup
    assert client.post("/api/v1/diagnose", json=payload()).json()["lesson"]["steps"]


def test_image_and_text_followup_requires_original_material(setup):
    client, _, engine = setup
    first = client.post("/api/v1/tutor", json=payload(attachments=["https://example.test/diagram.png"]))
    assert first.json()["status"] == "completed"
    calls = len(engine.calls)
    for i in range(8):
        data = client.post("/api/v1/tutor", json=payload(
            request_id=f"follow-{i}", problem_text="", student_answer=None, follow_up="图中的条件怎么用？",
        )).json()
        assert data["status"] == "need_clarification"
        assert data["lesson"] is None
    assert len(engine.calls) == calls


def test_answer_only_continues_after_empty_clarification_turn(setup):
    client, _, engine = setup
    client.post("/api/v1/tutor", json=payload(student_answer=None))
    empty = client.post("/api/v1/tutor", json=payload(
        request_id="r2", problem_text="", student_answer=None,
    )).json()
    assert empty["status"] == "need_clarification"
    reply = client.post("/api/v1/tutor", json=payload(
        request_id="r3", problem_text="", student_answer="我会控制光照和水分，仅改变肥料。",
    )).json()
    assert reply["status"] == "completed"
    assert [call for call in engine.calls if call[0] == "analyze"][-1][1].problem_text == payload()["problem_text"]


def test_understanding_check_answers_are_scoped_and_counted_once(setup):
    client, _, engine = setup
    client.post("/api/v1/tutor", json=payload(student_answer=None))
    answer = payload(request_id="check-1", student_answer="避免其他因素干扰结果。",
                     answer_to="为什么两组幼苗要使用相同的光照？")
    result = client.post("/api/v1/tutor", json=answer).json()
    analyzed = [call for call in engine.calls if call[0] == "analyze"][-1][1]
    assert analyzed.answer_to == answer["answer_to"]
    assert analyzed.student_answer == answer["student_answer"]
    assert result["guidance_mode"] == "post-answer"
    assert next(iter(result["profile"]["skills"].values()))["demonstrated_count"] == 1
    repeat = client.post("/api/v1/tutor", json={**answer, "request_id": "check-2"}).json()
    assert repeat["profile"]["skills"] == result["profile"]["skills"]
    assert client.post("/api/v1/tutor", json=payload(
        answer_to="检查问题", student_answer=None,
    )).status_code == 422

