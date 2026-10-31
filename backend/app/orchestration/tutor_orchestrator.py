"""Evidence-aware orchestration for arbitrary learning tasks.

Teaching is a model responsibility; identities, state, validation and evidence
admission are application responsibilities. No subject-specific routing lives here.
"""

import hashlib
import json
from uuid import uuid4

from app.repositories.profile_repository import SQLiteTutorRepository
from app.schemas.diagnosis import (
    Assessment, SkillEvidence, TaskAnalysis, TutorRequest, TutorResponse, Verification,
)
from app.services.tutor_engine import ModelOutputError, ModelUnavailable, TutorEngine


def payload_fingerprint(req: TutorRequest) -> str:
    data = req.model_dump(exclude={"request_id"})
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class TutorOrchestrator:
    def __init__(self, repo: SQLiteTutorRepository, engine: TutorEngine | None = None) -> None:
        self.repo = repo
        self.engine = engine or TutorEngine()

    def diagnose(self, req: TutorRequest) -> TutorResponse:
        return self.tutor(req)

    def tutor(self, req: TutorRequest) -> TutorResponse:
        fingerprint = payload_fingerprint(req)
        request_id = req.request_id or f"req-{uuid4().hex}"
        cached = self.repo.get_cached(req.student_id, request_id, fingerprint)
        if cached is not None:
            return cached

        session_id = req.session_id or f"session-{uuid4().hex}"
        self.repo.ensure_session(req.student_id, session_id)
        profile = self.repo.get_or_create(req.student_id)
        history = self.repo.history(req.student_id, session_id)
        resolved = req.model_copy(update={"request_id": request_id, "session_id": session_id})
        response = TutorResponse(
            request_id=request_id,
            turn_id=f"turn-{uuid4().hex}",
            session_id=session_id,
            student_id=req.student_id,
            status="need_clarification",
            guidance_mode="post-answer" if req.student_answer else "pre-answer",
            profile=profile,
        )

        original_images_missing = history and not resolved.attachments and any(
            turn.get("request", {}).get("attachments")
            or turn.get("response", {}).get("warnings") == ["本题仍需原始图片材料。"]
            for turn in history
        )
        if original_images_missing:
            response.warnings = ["本题仍需原始图片材料。"]
            response.clarifying_questions = ["这道题之前包含图片，请在本轮保留原图；若已完整转写为文字，请作为新题开始。"]
            return self.repo.commit_turn(resolved, response, fingerprint, None, [])

        if not resolved.problem_text and not resolved.attachments and (resolved.follow_up or resolved.student_answer):
            # An empty clarification turn must not hide the most recent actual task.
            for turn in reversed(history):
                previous_text = turn.get("request", {}).get("problem_text", "")
                if previous_text:
                    resolved = resolved.model_copy(update={"problem_text": previous_text})
                    break

        if not resolved.problem_text and not resolved.attachments:
            response.clarifying_questions = ["请提供完整题目、材料或图片；续问图片题时请保留原图。"]
            return self.repo.commit_turn(resolved, response, fingerprint, None, [])

        review_issues: list[str] = []
        try:
            analysis = self.engine.analyze(resolved, profile, history)
            self._normalize_analysis(resolved, analysis)
            response.analysis = analysis
            if analysis.missing_information:
                response.clarifying_questions = analysis.missing_information
                return self.repo.commit_turn(resolved, response, fingerprint, None, [])

            response.strategy = self.engine.plan(resolved, profile, analysis, history)
            lesson = self.engine.teach(resolved, profile, analysis, response.strategy, history)
            review = self.engine.verify(resolved, profile, analysis, lesson, history)
            review_issues = review.issues
            if not review.reliable or review.issues:
                review = review.model_copy(update={"approved_evidence": []})
            response.verification = review

            # One bounded semantic repair, only when the review gives an actionable issue.
            # Low confidence alone is not a reason to spend more calls or invent a fix.
            if any(issue.strip() for issue in review.issues):
                revision = self.engine.revise(
                    resolved, profile, analysis, lesson, response.strategy, review, history,
                )
                analysis = revision.analysis
                self._normalize_analysis(resolved, analysis)
                response.analysis = analysis
                if analysis.missing_information:
                    response.clarifying_questions = analysis.missing_information
                    response.verification = None
                    # No revised teaching or evidence is stored before independent approval.
                    return response
                lesson = revision.lesson
                if lesson is None:
                    raise ModelOutputError("修订未提供可复核的讲解，本次结果已拦截。")
                review = self.engine.verify(resolved, profile, analysis, lesson, history)
                review_issues = review.issues
                if not review.reliable or review.issues:
                    review = review.model_copy(update={"approved_evidence": []})
                response.verification = review

            # Fail closed: do not display a lesson the second pass could not verify.
            if not review.reliable or review.issues or analysis.confidence < 0.6:
                response.status = "degraded"
                response.warnings = review.issues or review_issues or ["当前内容尚未通过可靠性检查，请补充题目条件或重新尝试。"]
                response.verification = review.model_copy(update={"approved_evidence": []})
                analysis.skill_evidence = []
                analysis.assessment = Assessment(
                    verdict="uncertain" if resolved.student_answer else "not-submitted",
                    summary="当前分析尚未可靠验证，暂不判断作答或更新学习记录。",
                    evidence=[], confidence=0,
                )
                # Unverified reference answers should not masquerade as trustworthy help.
                analysis.reference_solution = []
                return response

            response.lesson = lesson
            response.status = "completed"
            evidence = self._admit_evidence(resolved, analysis, review)
            analysis.skill_evidence = evidence
            response.verification.approved_evidence = evidence
            if resolved.student_answer and not evidence:
                response.warnings.append("本轮没有足够可靠且具体的知识点证据，学习观察未更新。")
            response.warnings.append("讲解与复核由模型完成；复核通过不等于外部权威认证。")
            attempt_key = self._attempt_key(resolved) if evidence else None
            return self.repo.commit_turn(resolved, response, fingerprint, attempt_key, evidence)
        except (ModelUnavailable, ModelOutputError) as exc:
            response.status = "degraded"
            response.lesson = None
            response.analysis = None
            issues = list(dict.fromkeys([*review_issues, str(exc)]))
            response.verification = Verification(reliable=False, issues=issues)
            response.warnings = [*issues, "本次未生成可验证讲解，也未更新学习观察。"]
            # Transient failures are not cached, so retrying the same request can recover.
            return response

    @staticmethod
    def _normalize_analysis(req: TutorRequest, analysis: TaskAnalysis) -> None:
        """Keep the admission boundary even for substituted engines or test doubles."""
        if not req.student_answer:
            analysis.assessment = Assessment(
                verdict="not-submitted", summary="本轮尚未提交作答，先提供理解与思路引导。",
                evidence=[], confidence=1,
            )
            analysis.skill_evidence = []
        if analysis.missing_information:
            analysis.skill_evidence = []
            analysis.reference_solution = []
            analysis.assessment = Assessment(
                verdict="uncertain" if req.student_answer else "not-submitted",
                summary="题目材料不足，补充后再评估当前作答。",
                evidence=[], confidence=0,
            )

    @staticmethod
    def _attempt_key(req: TutorRequest) -> str:
        # Identical submissions in one session are one observation, even after a
        # regenerated lesson or a client-created new attempt id.
        source = {
            "session": req.session_id, "student": req.student_id,
            "problem": req.problem_text,
            "images": req.attachments, "answer": req.student_answer, "answer_to": req.answer_to,
        }
        return hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    @staticmethod
    def _admit_evidence(req: TutorRequest, analysis: TaskAnalysis, review: Verification) -> list[SkillEvidence]:
        if (
            not req.student_answer or not review.reliable or review.issues
            or analysis.confidence < 0.8 or analysis.assessment.confidence < 0.8
            or analysis.assessment.verdict in {"uncertain", "not-submitted"}
        ):
            return []
        skills = {(item.subject.casefold(), item.name.casefold()) for item in analysis.skills}
        proposed = {
            (item.subject.casefold(), item.name.casefold(), item.outcome, item.evidence): item
            for item in analysis.skill_evidence if item.confidence >= 0.8
        }
        accepted = []
        for item in review.approved_evidence:
            key = (item.subject.casefold(), item.name.casefold(), item.outcome, item.evidence)
            original = proposed.get(key)
            if original and key[:2] in skills and item.confidence >= 0.8:
                accepted.append(item.model_copy(update={"confidence": min(item.confidence, original.confidence)}))
        return accepted

