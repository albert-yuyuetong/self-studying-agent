from app.schemas.profile import StudentProfile


class InMemoryProfileRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, StudentProfile] = {}

    def get_or_create(self, student_id: str) -> StudentProfile:
        profile = self._profiles.get(student_id)
        if profile:
            return profile

        profile = StudentProfile(student_id=student_id)
        self._profiles[student_id] = profile
        return profile

    def save(self, profile: StudentProfile) -> StudentProfile:
        self._profiles[profile.student_id] = profile
        return profile
