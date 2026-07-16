from app.services.llm_client import LLMClient


class ProblemAnalysisService:
    def __init__(self) -> None:
        self.llm_client = LLMClient()

    def analyze(
        self,
        *,
        subject: str,
        grade: str | None,
        problem_text: str,
        attachments: list[str],
        parent_note: str | None,
    ) -> dict[str, object]:
        llm_result = self.llm_client.analyze_problem(
            subject=subject,
            grade=grade,
            problem_text=problem_text,
            attachments=attachments,
            parent_note=parent_note,
        )
        if llm_result:
            return llm_result

        return self._rule_based_fallback(subject=subject, problem_text=problem_text, parent_note=parent_note)

    def _rule_based_fallback(
        self,
        *,
        subject: str,
        problem_text: str,
        parent_note: str | None,
    ) -> dict[str, object]:
        normalized_problem = problem_text.strip()
        lowered = f"{subject} {normalized_problem} {parent_note or ''}".lower()
        open_ended_markers = [
            "作文",
            "阅读理解",
            "赏析",
            "谈谈",
            "简述",
            "概括",
            "写一段",
            "write an essay",
            "explain your opinion",
        ]
        if any(marker in lowered for marker in open_ended_markers):
            return {
                "question_type": "open-ended",
                "answer_analysis": {
                    "normalized_problem": normalized_problem or None,
                    "reference_answer": None,
                    "solution_outline": [
                        "先明确题目要求孩子表达什么。",
                        "再围绕观点、依据和表达完整度来辅导。",
                    ],
                    "evaluation_focus": ["是否切题", "是否有依据", "表达是否完整"],
                    "summary": "这更像开放题，没有唯一标准答案，更适合按评分点和表达质量来辅导。",
                    "confidence": 0.6,
                },
                "reference_answer_source": None,
            }

        return {
            "question_type": "standard-answer",
            "answer_analysis": {
                "normalized_problem": normalized_problem or None,
                "reference_answer": None,
                "solution_outline": [
                    "这是有标准答案的题，理论上可以先求出参考解，再判断孩子错在哪一步。",
                ],
                "evaluation_focus": ["答案是否正确", "步骤是否稳定"],
                "summary": "这题更像有标准答案的题。如果没有家长提供的参考答案，可以先由模型或工具推导参考解，再进入错因分析。",
                "confidence": 0.55,
            },
            "reference_answer_source": None,
        }