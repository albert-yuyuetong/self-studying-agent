from pydantic import BaseModel, Field


class FeedbackSchema(BaseModel):
    useful: bool
    child_understood: bool | None = None
    follow_up_needed: bool = False
    selected_style: str | None = None
    most_useful_step: str | None = None
    still_confusing_point: str | None = None
    parent_note: str | None = None


class CardSchema(BaseModel):
    card_title: str
    diagnosis_summary: str
    likely_cause: str
    coaching_steps: list[str]
    suggested_questions: list[str]
    materials_needed: list[str] = Field(default_factory=list)
    do_not_say: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    fallback_plan: str | None = None
    tone: str | None = None
    style: str | None = None


class AnswerAnalysisSchema(BaseModel):
    normalized_problem: str | None = None
    reference_answer: str | None = None
    solution_outline: list[str] = Field(default_factory=list)
    evaluation_focus: list[str] = Field(default_factory=list)
    summary: str
    confidence: float | None = None


class DiagnoseRequest(BaseModel):
    request_id: str | None = None
    session_id: str | None = None
    parent_id: str | None = None
    student_id: str
    subject: str = "math"
    grade: str | None = None
    textbook_version: str | None = None
    input_mode: str = "text"
    problem_text: str = ""
    student_answer: str | None = None
    knowledge_points: list[str] = Field(default_factory=list)
    parent_goal: str = "diagnose-and-coach"
    parent_note: str | None = None
    attachments: list[str] = Field(default_factory=list)
    feedback_context: FeedbackSchema | None = None


class DiagnoseResponse(BaseModel):
    request_id: str
    session_id: str | None = None
    student_id: str
    intent: str
    status: str
    confidence: str
    diagnosis: str
    question_type: str
    answer_analysis: AnswerAnalysisSchema | None = None
    reference_answer_source: str | None = None
    error_type: str | None = None
    knowledge_points: list[str]
    card: CardSchema
    practice_suggestion: str | None = None
    suggested_questions: list[str] = Field(default_factory=list)
    updated_mastery: dict[str, float] = Field(default_factory=dict)
    next_action: str | None = None
    clarifying_question: str | None = None
