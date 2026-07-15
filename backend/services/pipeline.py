from backend.models import DiagnoseRequest, DiagnoseResponse
from backend.services.diagnosis import DiagnosisService
from backend.services.profile import ProfileService
from backend.services.tutoring import TutoringService


class TutorWorkflow:
    def __init__(
        self,
        profile_service: ProfileService | None = None,
        diagnosis_service: DiagnosisService | None = None,
        tutoring_service: TutoringService | None = None,
    ) -> None:
        self.profile_service = profile_service or ProfileService()
        self.diagnosis_service = diagnosis_service or DiagnosisService()
        self.tutoring_service = tutoring_service or TutoringService()

    def run(self, request: DiagnoseRequest) -> DiagnoseResponse:
        profile = self.profile_service.get_profile(request)
        diagnosis = self.diagnosis_service.analyze(request)
        guidance = self.tutoring_service.build_parent_guidance(profile, diagnosis)

        return DiagnoseResponse(
            profile=profile,
            diagnosis=diagnosis,
            parent_guidance=guidance,
            architecture_path=[
                "interaction",
                "orchestration",
                "domain_services",
                "data_and_profile",
            ],
        )
