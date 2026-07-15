from pydantic import BaseModel, Field


class StudentProfile(BaseModel):
    student_id: str
    grade: str = "grade-4"
    textbook: str = "default"
    preferred_style: str = "visual"
    mastery: dict[str, float] = Field(default_factory=dict)
    error_tags: dict[str, int] = Field(default_factory=dict)
