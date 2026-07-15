from typing import Literal

from pydantic import BaseModel, Field


class ParentContext(BaseModel):
    parent_goal: str = Field(default="帮助家长理解怎么讲这道题")
    feedback: str | None = None


class DiagnoseRequest(BaseModel):
    student_id: str
    grade: str
    subject: str
    problem_text: str
    expected_answer: str | None = None
    student_answer: str | None = None
    parent_context: ParentContext = Field(default_factory=ParentContext)


class StudentProfile(BaseModel):
    student_id: str
    grade: str
    learning_style: Literal["visual", "auditory", "hands_on", "reading"]
    focus_knowledge_points: list[str] = Field(default_factory=list)
    parent_support_hint: str


class DiagnosisResult(BaseModel):
    error_type: Literal["concept_gap", "calculation_mistake", "reading_issue", "unknown"]
    knowledge_points: list[str]
    observation: str


class ParentGuidanceCard(BaseModel):
    summary: str
    coaching_steps: list[str]
    key_questions: list[str]
    suggested_props: list[str]
    next_action: str


class DiagnoseResponse(BaseModel):
    profile: StudentProfile
    diagnosis: DiagnosisResult
    parent_guidance: ParentGuidanceCard
    architecture_path: list[str]
