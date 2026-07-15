from fastapi import APIRouter

from app.orchestration.tutor_orchestrator import TutorOrchestrator
from app.repositories.profile_repository import InMemoryProfileRepository
from app.schemas.diagnosis import DiagnoseRequest, DiagnoseResponse

router = APIRouter(tags=["v1"])
repo = InMemoryProfileRepository()
orchestrator = TutorOrchestrator(repo=repo)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/diagnose", response_model=DiagnoseResponse)
def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    return orchestrator.diagnose(req)
