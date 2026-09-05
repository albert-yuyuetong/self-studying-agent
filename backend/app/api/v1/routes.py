from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.orchestration.tutor_orchestrator import TutorOrchestrator
from app.schemas.diagnosis import FeedbackRequest, TutorRequest, TutorResponse
from app.schemas.profile import ProfileSettings, StudentProfile

router = APIRouter(tags=["tutor"])


def current_tutor(request: Request) -> TutorOrchestrator:
    return request.app.state.tutor


Tutor = Annotated[TutorOrchestrator, Depends(current_tutor)]


@router.get("/health")
def health(tutor: Tutor) -> dict[str, object]:
    return {"status": "ok", "model_configured": tutor.engine.enabled}


@router.post("/tutor", response_model=TutorResponse)
def tutor_turn(req: TutorRequest, tutor: Tutor) -> TutorResponse:
    return tutor.tutor(req)


@router.post("/diagnose", response_model=TutorResponse, deprecated=True)
def diagnose(req: TutorRequest, tutor: Tutor) -> TutorResponse:
    """Compatibility URL; responses use the new tutor contract."""
    return tutor.tutor(req)


@router.get("/profiles/{student_id}", response_model=StudentProfile)
def get_profile(student_id: str, tutor: Tutor) -> StudentProfile:
    return tutor.repo.get_or_create(student_id)


@router.put("/profiles/{student_id}", response_model=StudentProfile)
def update_profile(student_id: str, body: ProfileSettings, tutor: Tutor) -> StudentProfile:
    return tutor.repo.update_profile(student_id, body)


@router.get("/sessions/{session_id}")
def session_history(session_id: str, student_id: str, tutor: Tutor) -> dict:
    return tutor.repo.session_turns(student_id, session_id)


@router.post("/feedback")
def feedback(req: FeedbackRequest, tutor: Tutor) -> dict:
    return tutor.repo.record_feedback(req)

