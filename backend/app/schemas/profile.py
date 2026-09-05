from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProfileSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(default="", max_length=80)
    grade: str = Field(default="", max_length=80)
    textbook: str = Field(default="", max_length=200)
    learning_goal: str = Field(default="", max_length=1000)
    language: str = Field(default="中文", max_length=80)
    preferred_explanation_modes: list[str] = Field(default_factory=list, max_length=8)
    interests: list[str] = Field(default_factory=list, max_length=12)
    pace: Literal["step-by-step", "balanced", "fast"] = "balanced"
    notes: str = Field(default="", max_length=2000)


class SkillState(BaseModel):
    subject: str
    name: str
    demonstrated_count: int = 0
    needs_support_count: int = 0
    last_evidence: str = ""
    last_seen: str = ""


class FormatFeedback(BaseModel):
    helpful: int = 0
    unhelpful: int = 0


class StudentProfile(ProfileSettings):
    student_id: str
    skills: dict[str, SkillState] = Field(default_factory=dict)
    format_feedback: dict[str, FormatFeedback] = Field(default_factory=dict)

