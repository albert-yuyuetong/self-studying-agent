"""Exercise personalization and evidence boundaries without claiming model accuracy."""

import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.diagnosis import (
    CompactLesson,
    CompactLessonRevision,
    Assessment,
    Lesson,
    LessonRevision,
    LessonStep,
    SkillDescriptor,
    SkillEvidence,
    TaskAnalysis,
    TutorRequest,
    Verification,
)
from app.schemas.profile import FormatFeedback, SkillState, StudentProfile
from app.services.llm_client import LLMClient, ModelUnavailable
from app.services.tutor_engine import ModelOutputError, TutorEngine, _compact_history


class RecordingClient:
    enabled = True
    config = SimpleNamespace(llm_verify_model="independent-reviewer")

    def __init__(self, outputs=()):
        self.outputs = list(outputs)
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        result = self.outputs.pop(0)
        assert isinstance(result, kwargs["schema"])
        return result


def analysis(*, answered=True):
    evidence = SkillEvidence(
        subject="计算机科学", name="不变量与边界分析", outcome="demonstrated",
        evidence="学生明确说明空输入需要单独返回，并以循环不变量说明已处理前缀。", confidence=0.91,
    )
    return TaskAnalysis(
        subject="计算机科学", task_summary="检查函数在空输入和循环边界上的正确性，并提出有依据的修改。",
        task_type="程序行为解释与正确性论证", skills=[SkillDescriptor(subject=evidence.subject, name=evidence.name)],
        learning_objectives=["用具体边界及不变量说明正确性"], reference_solution=["核对空输入分支和循环开始/结束条件。"],
        assessment=Assessment(
            verdict="supported" if answered else "not-submitted", summary="作答给出了边界依据" if answered else "先进行答前引导",
            evidence=[evidence.evidence] if answered else [], confidence=0.91,
        ),
        skill_evidence=[evidence] if answered else [], confidence=0.91,
    )


def lesson():
    return Lesson(
        title="检查空输入和循环边界", goal="为每个边界给出可验证依据",
        steps=[LessonStep(title="定位空输入", explanation="空数组不会进入循环，检查函数此时的返回路径。",
                          question="数组为空时经过哪些语句？", checkpoint="能指出实际返回路径")],
        understanding_checks=["单元素输入如何与空输入区别处理？"], recap="将边界情况与循环不变量分别检查。",
    )


def test_full_profile_real_answer_history_and_images_reach_all_model_stages():
    task = analysis()
    teaching = lesson()
    reviewer = Verification(reliable=True, approved_evidence=task.skill_evidence)
    client = RecordingClient([task, teaching, reviewer])
    engine = TutorEngine(client)
    profile = StudentProfile(
        student_id="learner", grade="大学一年级", textbook="算法课程讲义", interests=["棋类"],
        learning_goal="能够解释边界条件", language="中文", pace="step-by-step", notes="希望先说依据",
        preferred_explanation_modes=["用例对照"],
        skills={"a": SkillState(subject="计算机科学", name="不变量与边界分析", needs_support_count=1)},
        format_feedback={"用例对照": FormatFeedback(helpful=2)},
    )
    req = TutorRequest(
        student_id=profile.student_id, subject="计算机科学", problem_text="解释图片中函数并讨论所有边界。",
        student_answer="空输入需要单独返回；循环不变量描述已处理前缀。这是完整回答，不能只取第 1 个数字。",
        follow_up="请展开不变量在终止时的用途。", parent_note="保留原来的变量名",
        attachments=["https://example.org/function.png"],
    )
    history = [{"request": {"problem_text": "上一轮原题", "student_answer": "上一轮完整回答", "attachments": ["data:image/png;base64,aGVsbG8="]},
                "feedback": {"comment": "仍不清楚循环结束时的位置"}}]
    result = engine.analyze(req, profile, history)
    strategy = engine.plan(req, profile, result, history)
    actual_lesson = engine.teach(req, profile, result, strategy, history)
    engine.verify(req, profile, result, actual_lesson, history)

    assert [call["stage"] for call in client.calls] == ["analyze", "teach", "verify"]
    for call in client.calls:
        assert call["context"]["profile"] == profile.model_dump(mode="json")
        assert call["context"]["request"]["student_answer"] == req.student_answer
        assert call["context"]["request"]["follow_up"] == req.follow_up
        assert call["images"] == req.attachments
        assert "attachments" not in call["context"]["request"]
        assert call["context"]["request"]["image_count"] == 1
        assert call["context"]["history"][0]["request"]["student_answer"] == "上一轮完整回答"
        assert "attachments" not in call["context"]["history"][0]["request"]
        assert call["context"]["history"][0]["feedback"]["comment"] == "仍不清楚循环结束时的位置"
    assert client.calls[-1]["model"] == "independent-reviewer"
    assert {"grade", "textbook", "interests", "learning_goal", "skills", "format_feedback", "pace"} <= set(strategy.profile_used)


def test_feedback_changes_preference_and_explicit_request_takes_priority():
    client = RecordingClient()
    engine = TutorEngine(client)
    profile = StudentProfile(
        student_id="learner", pace="fast", preferred_explanation_modes=["文字说明", "用例对照"],
        format_feedback={"文字说明": FormatFeedback(helpful=0, unhelpful=3), "用例对照": FormatFeedback(helpful=3)},
    )
    req = TutorRequest(student_id="learner", problem_text="一个未登记的任务")
    assert engine.plan(req, profile, analysis(), []).approach == "用例对照"
    explicit = req.model_copy(update={"requested_strategy": "先让我自己说出依据"})
    strategy = engine.plan(explicit, profile, analysis(), [])
    assert strategy.approach == "先让我自己说出依据"
    assert strategy.pace == "fast"
    assert not client.calls


def test_no_student_answer_must_not_create_assessment_or_skill_evidence():
    engine = TutorEngine(RecordingClient([analysis()]))
    with pytest.raises(ModelOutputError, match="尚未收到学生作答"):
        engine.analyze(TutorRequest(student_id="learner", problem_text="解释一个实验结果"), StudentProfile(student_id="learner"), [])


def test_answer_before_submission_remains_ungraded():
    engine = TutorEngine(RecordingClient([analysis(answered=False)]))
    actual = engine.analyze(TutorRequest(student_id="learner", problem_text="请解释这段函数"), StudentProfile(student_id="learner"), [])
    assert actual.assessment.verdict == "not-submitted"
    assert actual.skill_evidence == []


def test_review_cannot_invent_or_rewrite_skill_evidence():
    task = analysis()
    invented = task.skill_evidence[0].model_copy(update={"confidence": 1.0})
    engine = TutorEngine(RecordingClient([Verification(reliable=True, approved_evidence=[invented])]))
    result = engine.verify(TutorRequest(student_id="learner", problem_text="解释函数", student_answer="我的完整作答"),
                           StudentProfile(student_id="learner"), task, lesson(), [])
    assert not result.reliable
    assert result.approved_evidence == []


def test_failed_review_removes_even_existing_evidence():
    task = analysis()
    engine = TutorEngine(RecordingClient([Verification(reliable=False, issues=["参考解未覆盖空输入"], approved_evidence=task.skill_evidence)]))
    result = engine.verify(TutorRequest(student_id="learner", problem_text="解释函数", student_answer="我的完整作答"),
                           StudentProfile(student_id="learner"), task, lesson(), [])
    assert not result.reliable
    assert result.approved_evidence == []


def test_skills_must_have_corresponding_task_descriptors():
    task = analysis()
    task.skills = []
    engine = TutorEngine(RecordingClient([task]))
    with pytest.raises(ModelOutputError, match="技能证据与题目分析不一致"):
        engine.analyze(TutorRequest(student_id="learner", problem_text="解释函数", student_answer="我的完整作答"),
                       StudentProfile(student_id="learner"), [])


def test_history_compaction_drops_duplicate_profiles_but_keeps_materials_and_feedback():
    profile = StudentProfile(student_id="learner", notes="当前完整画像")
    req = TutorRequest(student_id="learner", problem_text="当前完整原题", student_answer="当前完整作答")
    history = [{
        "request": {"problem_text": "历史原题全文", "student_answer": "历史作答全文"},
        "response": {
            "profile": {"notes": "重复历史画像" * 10_000},
            "profile_updates": ["重复派生字段"],
            "verification": {"approved_evidence": ["重复回执"]},
            "analysis": {
                "task_summary": "完整历史题意", "reference_solution": ["历史参考依据"],
                "assessment": {"summary": "历史判断"}, "skill_evidence": ["重复技能证据"],
            },
            "lesson": {"steps": [{"question": "上次留下的具体问题"}]},
        },
        "feedback": {"child_understood": False, "comment": "希望展开边界情况"},
    }]
    context = TutorEngine._context(req, profile, history)
    assert context["profile"] == profile.model_dump(mode="json")
    assert context["request"]["student_answer"] == req.student_answer
    assert len(context["history"]) == 1
    previous = context["history"][0]
    assert previous["request"]["student_answer"] == "历史作答全文"
    assert previous["response"]["analysis"]["reference_solution"] == ["历史参考依据"]
    assert previous["response"]["lesson"]["steps"][0]["question"] == "上次留下的具体问题"
    assert previous["feedback"]["comment"] == "希望展开边界情况"
    assert "profile" not in previous["response"]
    assert "verification" not in previous["response"]
    assert "skill_evidence" not in previous["response"]["analysis"]
    assert "历史画像副本" in context["history_notice"]


def test_history_budget_keeps_complete_recent_turns_and_explicit_omission_notice():
    history = [{"request": {"problem_text": f"原题 {index}:" + "条件" * 80, "student_answer": "完整答案" * 20},
                "feedback": {"comment": f"第 {index} 轮反馈"}} for index in range(4)]
    budget = len(json.dumps([history[-1]], ensure_ascii=False, separators=(",", ":"))) + 5
    retained, notice = _compact_history(history, budget)
    assert len(retained) == 1
    assert retained[0] == history[-1]
    assert len(json.dumps(retained, ensure_ascii=False, separators=(",", ":"))) <= budget
    assert "3 轮已省略" in notice
    assert "重传具体材料" in notice
    assert "未截断" in notice
    # If even the latest complete turn does not fit, do not silently substitute older context.
    assert _compact_history(history, 20)[0] == []


@pytest.mark.parametrize("port", ["invalid", "0", "65536", "-1"])
def test_invalid_model_service_port_has_safe_configuration_error(port):
    with pytest.raises(ValueError, match="LLM_BASE_URL") as captured:
        Settings(llm_base_url=f"https://private-service.example:{port}")
    assert "private-service" not in str(captured.value)


def test_invalid_url_transport_exception_becomes_public_safe_unavailable():
    def invalid_transport(request):
        raise httpx.InvalidURL("private internal URL detail")

    client = LLMClient(Settings(llm_enabled=True, llm_model="configured-model", llm_api_key="private-key"),
                       transport=httpx.MockTransport(invalid_transport))
    with pytest.raises(ModelUnavailable) as captured:
        client.generate(schema=Verification, system_prompt="Return JSON", context={}, stage="verify")
    assert "private" not in str(captured.value)


def test_check_question_scope_is_preserved_across_all_stages_and_history():
    task = analysis()
    teaching = lesson()
    client = RecordingClient([task, teaching, Verification(reliable=True, approved_evidence=task.skill_evidence)])
    engine = TutorEngine(client)
    req = TutorRequest(student_id="learner", problem_text="分析整个函数。",
                       answer_to="数组为空时经过哪些语句？", student_answer="直接返回，不进入循环。")
    profile = StudentProfile(student_id="learner")
    history = [{"request": {"problem_text": req.problem_text, "answer_to": "循环何时停止？",
                            "student_answer": "下标达到长度时。"}}]
    result = engine.analyze(req, profile, history)
    strategy = engine.plan(req, profile, result, history)
    generated = engine.teach(req, profile, result, strategy, history)
    engine.verify(req, profile, result, generated, history)
    for call in client.calls:
        assert call["context"]["request"]["answer_to"] == req.answer_to
        assert call["context"]["history"][0]["request"]["answer_to"] == "循环何时停止？"
        assert "answer_to" in call["system_prompt"]


@pytest.mark.parametrize("field", ["step_question", "understanding_check", "practice_prompt", "practice_purpose"])
def test_generated_questions_fit_the_followup_request_contract(field):
    data = lesson().model_dump()
    if field == "step_question":
        data["steps"][0]["question"] = "问" * 4001
    elif field == "understanding_check":
        data["understanding_checks"] = ["问" * 4001]
    else:
        data["practice"] = [{"id": "p1", "prompt": "完整题干", "purpose": "检查迁移",
                             "success_criteria": ["说明依据"]}]
        key, size = ("prompt", 24001) if field == "practice_prompt" else ("purpose", 2001)
        data["practice"][0][key] = "长" * size
    with pytest.raises(ValidationError):
        Lesson.model_validate(data)


def test_fast_profile_constrains_real_client_output_and_repairs_overlong_lesson():
    """Reproduce the live finding: a fast learner received the same seven steps."""
    overlong = lesson().model_dump()
    overlong["steps"] = overlong["steps"] * 7
    repaired = {**overlong, "steps": overlong["steps"][:3]}
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        content = overlong if len(bodies) == 1 else repaired
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    client = LLMClient(Settings(llm_enabled=True, llm_model="test", llm_api_key="test"),
                       httpx.MockTransport(handler))
    engine = TutorEngine(client)
    req = TutorRequest(student_id="learner", problem_text="分析函数", student_answer="完整作答")
    profile = StudentProfile(student_id="learner", pace="fast")
    strategy = engine.plan(req, profile, analysis(), [])
    result = engine.teach(req, profile, analysis(), strategy, [])
    assert isinstance(result, CompactLesson)
    assert len(result.steps) == 3
    assert len(bodies) == 2
    assert "steps" in bodies[1]["messages"][-1]["content"]


def test_balanced_profile_allows_a_detailed_seven_step_lesson():
    detailed = lesson().model_copy(update={"steps": lesson().steps * 7})
    engine = TutorEngine(RecordingClient([detailed]))
    req = TutorRequest(student_id="learner", problem_text="分析函数")
    profile = StudentProfile(student_id="learner", pace="balanced")
    result = engine.teach(req, profile, analysis(), engine.plan(req, profile, analysis(), []), [])
    assert len(result.steps) == 7


def test_revision_preserves_original_material_profile_and_concrete_review_issues():
    task, teaching = analysis(), lesson()
    revised = LessonRevision(analysis=task.model_copy(deep=True), lesson=teaching.model_copy(deep=True))
    client = RecordingClient([revised])
    engine = TutorEngine(client)
    req = TutorRequest(student_id="learner", problem_text="原函数和完整材料", student_answer="空输入直接返回。",
                       answer_to="空输入走哪条路径？", follow_up="只解释这个边界", attachments=["https://example.org/code.png"])
    profile = StudentProfile(student_id="learner", notes="希望核对具体语句", interests=["棋类"])
    history = [{"request": {"problem_text": "前轮原题"}, "feedback": {"comment": "这一步没理解"}}]
    review = Verification(reliable=False, issues=["检查题在空输入时也允许另一个答案。"])
    strategy = engine.plan(req, profile, task, history)
    result = engine.revise(req, profile, task, teaching, strategy, review, history)
    assert result == revised
    call = client.calls[0]
    assert call["stage"] == "revise"
    assert call["images"] == req.attachments
    assert call["context"]["request"]["student_answer"] == req.student_answer
    assert call["context"]["request"]["answer_to"] == req.answer_to
    assert call["context"]["profile"] == profile.model_dump(mode="json")
    assert call["context"]["history"][0]["feedback"]["comment"] == "这一步没理解"
    assert call["context"]["analysis"] == task.model_dump(mode="json")
    assert call["context"]["lesson"] == teaching.model_dump(mode="json")
    assert call["context"]["review"] == review.model_dump(mode="json")


@pytest.mark.parametrize("change", ["confidence", "new_skill", "no_descriptor"])
def test_revision_cannot_invent_or_rewrite_observation_evidence(change):
    original = analysis()
    candidate = original.model_copy(deep=True)
    if change == "confidence":
        candidate.skill_evidence[0].confidence = 1
    elif change == "new_skill":
        candidate.skill_evidence[0].name = "新编出的能力"
        candidate.skills[0].name = "新编出的能力"
    else:
        candidate.skills = []
    client = RecordingClient([LessonRevision(analysis=candidate, lesson=lesson())])
    engine = TutorEngine(client)
    req = TutorRequest(student_id="learner", problem_text="检查函数", student_answer="空输入直接返回")
    profile = StudentProfile(student_id="learner")
    with pytest.raises(ModelOutputError):
        engine.revise(req, profile, original, lesson(), engine.plan(req, profile, original, []),
                      Verification(reliable=False, issues=["解释有歧义"]), [])


def test_revision_reuses_no_answer_evidence_gate():
    candidate = LessonRevision(analysis=analysis(), lesson=lesson())
    engine = TutorEngine(RecordingClient([candidate]))
    req = TutorRequest(student_id="learner", problem_text="检查函数", follow_up="还没理解")
    profile = StudentProfile(student_id="learner")
    original = analysis(answered=False)
    with pytest.raises(ModelOutputError, match="尚未收到学生作答"):
        engine.revise(req, profile, original, lesson(), engine.plan(req, profile, original, []),
                      Verification(reliable=False, issues=["解释有歧义"]), [])


def test_fast_revision_repairs_overlong_candidate_before_independent_review():
    original = analysis()
    overlong = LessonRevision(analysis=original, lesson=lesson()).model_dump()
    overlong["lesson"]["steps"] *= 5
    repaired = json.loads(json.dumps(overlong))
    repaired["lesson"]["steps"] = repaired["lesson"]["steps"][:3]
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        content = overlong if len(bodies) == 1 else repaired
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    client = LLMClient(Settings(llm_enabled=True, llm_model="test", llm_api_key="test"), httpx.MockTransport(handler))
    engine = TutorEngine(client)
    req = TutorRequest(student_id="learner", problem_text="检查函数", student_answer="空输入直接返回")
    profile = StudentProfile(student_id="learner", pace="fast")
    result = engine.revise(req, profile, original, lesson(), engine.plan(req, profile, original, []),
                           Verification(reliable=False, issues=["检查题有歧义"]), [])
    assert isinstance(result, CompactLessonRevision)
    assert len(result.lesson.steps) == 3
    assert len(bodies) == 2
    assert '"lesson", "steps"' in bodies[1]["messages"][-1]["content"]


def test_reliable_review_with_issues_still_withholds_approved_evidence():
    task = analysis()
    engine = TutorEngine(RecordingClient([Verification(reliable=True, issues=["评分遗漏另一种答案"],
                                                       approved_evidence=task.skill_evidence)]))
    result = engine.verify(TutorRequest(student_id="learner", problem_text="解释函数", student_answer="完整作答"),
                           StudentProfile(student_id="learner"), task, lesson(), [])
    assert result.issues
    assert result.approved_evidence == []
