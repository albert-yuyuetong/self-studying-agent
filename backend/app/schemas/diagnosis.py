"""Open task descriptions; fixed enums describe workflow states, never school question types."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.profile import StudentProfile


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TutorRequest(Contract):
    request_id: str | None = Field(default=None, min_length=1, max_length=100)
    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    student_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(default="auto", min_length=1, max_length=100)
    problem_text: str = Field(default="", max_length=24000)
    student_answer: str | None = Field(default=None, max_length=24000)
    answer_to: str | None = Field(default=None, max_length=4000)
    parent_goal: str = Field(default="帮助理解并能独立完成", max_length=2000)
    parent_note: str | None = Field(default=None, max_length=4000)
    attachments: list[str] = Field(default_factory=list, max_length=4)
    follow_up: str | None = Field(default=None, max_length=4000)
    requested_strategy: str | None = Field(default=None, max_length=300)
    attempt_id: str | None = Field(default=None, min_length=1, max_length=100)
    # Legacy input metadata remains context, never a routing switch.
    grade: str | None = Field(default=None, max_length=80)
    textbook_version: str | None = Field(default=None, max_length=200)
    input_mode: str = Field(default="text", max_length=40)

    @field_validator("student_answer", "answer_to", "follow_up", "parent_note", "requested_strategy", mode="before")
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        return (value.strip() or None) if isinstance(value, str) else value

    @model_validator(mode="after")
    def check_answer_scope(self):
        if self.answer_to and not self.student_answer:
            raise ValueError("提交理解检查时，请同时提供对应的作答。")
        return self

    @field_validator("attachments")
    @classmethod
    def valid_images(cls, values: list[str]) -> list[str]:
        import base64
        import binascii
        from urllib.parse import urlsplit

        for value in values:
            if value.startswith("data:image/"):
                header, sep, payload = value.partition(",")
                if not sep or header not in {"data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64", "data:image/gif;base64"}:
                    raise ValueError("图片须为 PNG/JPEG/WebP/GIF 的 base64 数据")
                if len(payload) > 8_000_000:
                    raise ValueError("每张图片不能超过约 6 MB")
                try:
                    if not base64.b64decode(payload, validate=True):
                        raise ValueError("图片内容为空")
                except binascii.Error as exc:
                    raise ValueError("图片编码无效") from exc
            elif len(value) > 4000 or urlsplit(value).scheme != "https" or not urlsplit(value).netloc:
                raise ValueError("附件须为 HTTPS 图片链接或图片数据")
        return values


class SkillDescriptor(Contract):
    name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=100)


class SkillEvidence(SkillDescriptor):
    outcome: Literal["demonstrated", "needs-support"]
    evidence: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)


class Assessment(Contract):
    verdict: Literal["not-submitted", "supported", "partially-supported", "needs-revision", "uncertain"]
    summary: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class TaskAnalysis(Contract):
    subject: str = Field(min_length=1)
    task_summary: str = Field(min_length=1)
    task_type: str = Field(min_length=1, description="Free description, never a predefined taxonomy")
    missing_information: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    skills: list[SkillDescriptor] = Field(default_factory=list, max_length=12)
    reference_solution: list[str] = Field(default_factory=list)
    assessment: Assessment
    skill_evidence: list[SkillEvidence] = Field(default_factory=list, max_length=12)
    confidence: float = Field(ge=0, le=1)


class TeachingStrategy(Contract):
    approach: str
    rationale: list[str]
    profile_used: list[str]
    pace: str


class LessonStep(Contract):
    title: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    question: str = Field(min_length=1)
    checkpoint: str = Field(min_length=1)


class PracticeTask(Contract):
    id: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    hints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(min_length=1)


class Lesson(Contract):
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    steps: list[LessonStep] = Field(min_length=1, max_length=8)
    parent_tips: list[str] = Field(default_factory=list)
    understanding_checks: list[str] = Field(min_length=1)
    practice: list[PracticeTask] = Field(default_factory=list, max_length=3)
    recap: str = Field(min_length=1)


class Verification(Contract):
    reliable: bool
    issues: list[str] = Field(default_factory=list)
    approved_evidence: list[SkillEvidence] = Field(default_factory=list, max_length=12)


class TutorResponse(Contract):
    request_id: str
    turn_id: str
    session_id: str
    student_id: str
    status: Literal["completed", "need_clarification", "degraded"]
    guidance_mode: Literal["pre-answer", "post-answer"]
    analysis: TaskAnalysis | None = None
    strategy: TeachingStrategy | None = None
    lesson: Lesson | None = None
    verification: Verification | None = None
    clarifying_questions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    profile: StudentProfile
    profile_updates: list[str] = Field(default_factory=list)


class FeedbackRequest(Contract):
    feedback_id: str = Field(min_length=1, max_length=100)
    student_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    turn_id: str = Field(min_length=1, max_length=100)
    useful: bool
    child_understood: bool | None = None
    comment: str = Field(default="", max_length=4000)


DiagnoseRequest = TutorRequest
DiagnoseResponse = TutorResponse

