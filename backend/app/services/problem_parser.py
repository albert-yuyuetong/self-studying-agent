class ProblemParser:
    def parse(self, problem_text: str, knowledge_points: list[str]) -> dict[str, list[str] | str]:
        return {
            "problem_text": problem_text.strip(),
            "knowledge_points": knowledge_points or ["general-arithmetic"],
        }
