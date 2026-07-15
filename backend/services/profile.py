from backend.models import DiagnoseRequest, StudentProfile


class ProfileService:
    def get_profile(self, request: DiagnoseRequest) -> StudentProfile:
        learning_style = self._infer_learning_style(request)
        support_hint = {
            "visual": "优先用图示、线段图或示意图帮助家长讲解。",
            "auditory": "优先给家长可复述的话术与口头追问方式。",
            "hands_on": "优先建议家长借助实物演示和动手操作。",
            "reading": "优先给家长结构化文字拆解步骤。",
        }[learning_style]

        return StudentProfile(
            student_id=request.student_id,
            grade=request.grade,
            learning_style=learning_style,
            focus_knowledge_points=[],
            parent_support_hint=support_hint,
        )

    def _infer_learning_style(self, request: DiagnoseRequest) -> str:
        feedback = request.parent_context.feedback or ""
        if "听" in feedback:
            return "auditory"
        if "动手" in feedback or "实物" in feedback:
            return "hands_on"
        if "读" in feedback or "文字" in feedback:
            return "reading"
        return "visual"
