from backend.models import DiagnoseRequest, DiagnosisResult


class DiagnosisService:
    def analyze(self, request: DiagnoseRequest) -> DiagnosisResult:
        knowledge_points = self._extract_knowledge_points(request)
        error_type = self._classify_error(request)

        observations = {
            "concept_gap": "当前更像是知识点未建立稳固理解，需要先回到概念解释。",
            "calculation_mistake": "孩子可能理解了题型，但在运算步骤上出现了偏差。",
            "reading_issue": "这次错误更像是审题或条件提取不到位。",
            "unknown": "当前信息不足，建议先用追问确认孩子卡住的位置。",
        }

        return DiagnosisResult(
            error_type=error_type,
            knowledge_points=knowledge_points,
            observation=observations[error_type],
        )

    def _extract_knowledge_points(self, request: DiagnoseRequest) -> list[str]:
        subject = request.subject.strip().lower()
        text = request.problem_text

        if "分数" in text:
            return ["分数运算"]
        if "应用题" in text or "路程" in text:
            return ["应用题建模"]
        if subject in {"math", "数学"}:
            return ["基础数学运算"]
        if subject in {"chinese", "语文"}:
            return ["阅读理解"]
        return [request.subject]

    def _classify_error(self, request: DiagnoseRequest) -> str:
        feedback = request.parent_context.feedback or ""
        goal = request.parent_context.parent_goal

        if "审题" in feedback or "读题" in feedback:
            return "reading_issue"

        if (
            request.expected_answer
            and request.student_answer
            and request.expected_answer.strip() != request.student_answer.strip()
        ):
            return "calculation_mistake"

        if "概念" in feedback or "为什么" in goal:
            return "concept_gap"

        return "unknown"
