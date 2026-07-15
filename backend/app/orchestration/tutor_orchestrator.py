from uuid import uuid4

from app.profile.bkt import update_mastery
from app.repositories.profile_repository import InMemoryProfileRepository
from app.schemas.diagnosis import CardSchema, DiagnoseRequest, DiagnoseResponse
from app.services.explanation_generator import ExplanationGenerator
from app.services.grading_service import GradingService
from app.services.practice_generator import PracticeGenerator
from app.services.problem_parser import ProblemParser
from app.services.style_adapter import StyleAdapter


class TutorOrchestrator:
    def __init__(self, repo: InMemoryProfileRepository) -> None:
        self.repo = repo
        self.parser = ProblemParser()
        self.grader = GradingService()
        self.style_adapter = StyleAdapter()
        self.explainer = ExplanationGenerator()
        self.practice = PracticeGenerator()

    def diagnose(self, req: DiagnoseRequest) -> DiagnoseResponse:
        request_id = req.request_id or f"req-{uuid4().hex[:12]}"

        problem_text = req.problem_text.strip()
        if not problem_text:
            return DiagnoseResponse(
                request_id=request_id,
                session_id=req.session_id,
                student_id=req.student_id,
                intent=req.parent_goal,
                status="need_clarification",
                confidence="low",
                diagnosis="信息不足，暂时无法判断具体错因。",
                error_type=None,
                knowledge_points=[],
                card=self._build_clarification_card(),
                practice_suggestion=None,
                suggested_questions=["请先补充题目内容或上传更清晰的题目图片。"],
                updated_mastery={},
                next_action="ask_clarifying_question",
                clarifying_question="请先补充完整题目，或上传一张更清晰的题目图片。",
            )

        profile = self.repo.get_or_create(req.student_id)
        if req.grade:
            profile.grade = req.grade
        if req.textbook_version:
            profile.textbook = req.textbook_version

        parsed = self.parser.parse(problem_text, req.knowledge_points)

        if req.student_answer is None or req.expected_answer is None:
            diagnosis = "题目已收到，但缺少学生答案或参考答案，先进入保守辅导模式。"
            selected_style = self._select_style(profile.preferred_style, req.feedback_context)
            profile.preferred_style = selected_style
            parent_guidance = self.explainer.generate_parent_card(
                style=selected_style,
                diagnosis=diagnosis,
                knowledge_points=list(parsed["knowledge_points"]),
            )
            card = self._build_card(
                parent_guidance=parent_guidance,
                diagnosis=diagnosis,
                selected_style=selected_style,
                is_correct=None,
                error_type=None,
            )
            self.repo.save(profile)
            return DiagnoseResponse(
                request_id=request_id,
                session_id=req.session_id,
                student_id=req.student_id,
                intent=req.parent_goal,
                status="degraded",
                confidence="low",
                diagnosis=diagnosis,
                error_type=None,
                knowledge_points=list(parsed["knowledge_points"]),
                card=card,
                practice_suggestion=None,
                suggested_questions=card.suggested_questions,
                updated_mastery=profile.mastery,
                next_action="ask_clarifying_question",
                clarifying_question="如果你方便，请补充孩子的答案或参考答案，我可以更准确判断错因。",
            )

        grade_result = self.grader.grade(req.student_answer, req.expected_answer)
        is_correct = bool(grade_result["is_correct"])

        selected_style = self._select_style(profile.preferred_style, req.feedback_context)
        profile.preferred_style = selected_style

        for kp in parsed["knowledge_points"]:
            prior = profile.mastery.get(kp, 0.6)
            posterior = update_mastery(prior=prior, correct=is_correct)
            profile.mastery[kp] = posterior

            if not is_correct:
                profile.error_tags[grade_result["error_type"]] = profile.error_tags.get(
                    grade_result["error_type"], 0
                ) + 1

        self.repo.save(profile)

        parent_guidance = self.explainer.generate_parent_card(
            style=selected_style,
            diagnosis=str(grade_result["diagnosis"]),
            knowledge_points=list(parsed["knowledge_points"]),
        )

        practice_suggestion = self.practice.generate(
            knowledge_points=list(parsed["knowledge_points"]),
            is_correct=is_correct,
        )

        card = self._build_card(
            parent_guidance=parent_guidance,
            diagnosis=str(grade_result["diagnosis"]),
            selected_style=selected_style,
            is_correct=is_correct,
            error_type=str(grade_result["error_type"]),
        )

        confidence = "high" if is_correct else "medium"
        next_action = "show_card_and_collect_feedback"

        return DiagnoseResponse(
            request_id=request_id,
            session_id=req.session_id,
            student_id=req.student_id,
            intent=req.parent_goal,
            status="completed",
            confidence=confidence,
            diagnosis=str(grade_result["diagnosis"]),
            error_type=str(grade_result["error_type"]),
            knowledge_points=list(parsed["knowledge_points"]),
            card=card,
            practice_suggestion=practice_suggestion,
            suggested_questions=card.suggested_questions,
            updated_mastery=profile.mastery,
            next_action=next_action,
            clarifying_question=None,
        )

    def _select_style(self, preferred_style: str, feedback_context: object | None) -> str:
        feedback_useful = getattr(feedback_context, "useful", None)
        return self.style_adapter.choose_style(preferred_style, feedback_useful)

    def _build_card(
        self,
        parent_guidance: dict[str, list[str] | str],
        diagnosis: str,
        selected_style: str,
        is_correct: bool | None,
        error_type: str | None,
    ) -> CardSchema:
        if is_correct is True:
            likely_cause = "这题目前已经答对，接下来更适合做迁移和巩固。"
            do_not_say = ["这题会了就不用再想了"]
            red_flags: list[str] = []
            fallback_plan = "让孩子换一个相近情境再做一题，确认不是只记住了答案。"
        elif is_correct is False:
            likely_cause = self._likely_cause_from_error_type(error_type)
            do_not_say = ["你怎么又错了", "直接记住答案就行"]
            red_flags = ["如果同类题连续出错，先退回前置知识点。"]
            fallback_plan = "如果孩子仍不懂，先退回到更基础的一步做一题，再回到当前题。"
        else:
            likely_cause = "目前信息不足，更适合先确认孩子卡在哪一步。"
            do_not_say = ["你先把答案背下来"]
            red_flags = ["缺少学生答案或参考答案时，不要过早下结论。"]
            fallback_plan = "先补充孩子答案或口头思路，再决定是否需要改换讲法。"

        return CardSchema(
            card_title=self._build_card_title(is_correct, selected_style),
            diagnosis_summary=diagnosis,
            likely_cause=likely_cause,
            coaching_steps=self._build_coaching_steps(str(parent_guidance["parent_card"])),
            suggested_questions=list(parent_guidance["suggested_questions"]),
            materials_needed=self._materials_for_style(selected_style),
            do_not_say=do_not_say,
            red_flags=red_flags,
            fallback_plan=fallback_plan,
            tone="encouraging",
            style=selected_style,
        )

    def _build_clarification_card(self) -> CardSchema:
        return CardSchema(
            card_title="先补充题目信息",
            diagnosis_summary="题目内容不足，暂时无法进入准确诊断。",
            likely_cause="当前更像是输入信息不完整，而不是孩子能力问题。",
            coaching_steps=[
                "先补充完整题干或上传更清晰的图片。",
                "如果方便，再补充孩子的答案或解题过程。",
            ],
            suggested_questions=["能补一张更清晰的题目图片吗？"],
            materials_needed=[],
            do_not_say=["先别急着直接告诉孩子答案。"],
            red_flags=["信息不完整时不要强行判断错因。"],
            fallback_plan="拿到完整题目和孩子答案后，再进入诊断和讲解。",
            tone="calm",
            style="direct",
        )

    def _build_card_title(self, is_correct: bool | None, selected_style: str) -> str:
        if is_correct is True:
            return "这题会了，下一步做迁移巩固"
        if is_correct is False:
            return f"先稳住关键步骤，再用{selected_style}方式讲一遍"
        return "先确认卡点，再决定怎么讲"

    def _build_coaching_steps(self, parent_card_text: str) -> list[str]:
        focus_text = parent_card_text.strip()
        return [
            "先让孩子复述题目和当前思路。",
            focus_text,
            "最后让孩子自己用一句话总结这题最关键的一步。",
        ]

    def _materials_for_style(self, selected_style: str) -> list[str]:
        if selected_style == "visual":
            return ["草稿纸", "彩笔"]
        if selected_style == "hands-on":
            return ["纸条", "小物块"]
        if selected_style == "story":
            return ["口头情境示例"]
        return []

    def _likely_cause_from_error_type(self, error_type: str | None) -> str:
        if error_type == "calculation":
            return "更像是计算执行不稳定，而不是概念完全不懂。"
        if error_type == "none":
            return "这题已经答对，可以转向迁移应用。"
        return "更像是概念或步骤理解还不稳定，不建议简单归因为粗心。"
