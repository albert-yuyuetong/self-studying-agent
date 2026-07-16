import re
from fractions import Fraction


class ProblemParser:
    def parse(self, problem_text: str, knowledge_points: list[str]) -> dict[str, list[str] | str | float]:
        normalized_text = self._normalize(problem_text)
        inferred_knowledge_points = knowledge_points or self._infer_knowledge_points(normalized_text)
        return {
            "problem_text": normalized_text,
            "knowledge_points": inferred_knowledge_points,
            "problem_type": self._infer_problem_type(normalized_text),
            "concept_dependencies": self._infer_dependencies(inferred_knowledge_points),
            "confidence": 0.9 if knowledge_points else 0.68,
        }

    def _normalize(self, problem_text: str) -> str:
        return re.sub(r"\s+", " ", problem_text).strip()

    def _infer_knowledge_points(self, problem_text: str) -> list[str]:
        fractions = self._extract_fractions(problem_text)
        if len(fractions) >= 2 and "+" in problem_text:
            if fractions[0].denominator != fractions[1].denominator:
                return ["fraction-addition-unlike-denominator", "common-denominator"]
            return ["fraction-addition-like-denominator"]
        if len(fractions) >= 2 and "-" in problem_text:
            if fractions[0].denominator != fractions[1].denominator:
                return ["fraction-subtraction-unlike-denominator", "common-denominator"]
            return ["fraction-subtraction-like-denominator"]
        if any(symbol in problem_text for symbol in ["×", "*", "x"]):
            return ["multiplication"]
        if any(symbol in problem_text for symbol in ["÷", "/"]):
            return ["division"]
        if any(keyword in problem_text for keyword in ["多少", "一共", "还剩", "平均"]):
            return ["word-problem-arithmetic"]
        return ["general-arithmetic"]

    def _infer_problem_type(self, problem_text: str) -> str:
        if any(char in problem_text for char in ["+", "-", "×", "*", "÷"]):
            return "equation"
        if any(keyword in problem_text for keyword in ["多少", "一共", "还剩", "平均"]):
            return "word-problem"
        return "short-answer"

    def _infer_dependencies(self, knowledge_points: list[str]) -> list[str]:
        dependencies: list[str] = []
        if "fraction-addition-unlike-denominator" in knowledge_points:
            dependencies.extend(["fraction-concept", "common-denominator"])
        if "fraction-subtraction-unlike-denominator" in knowledge_points:
            dependencies.extend(["fraction-concept", "common-denominator"])
        if "multiplication" in knowledge_points:
            dependencies.append("repeated-addition")
        if "division" in knowledge_points:
            dependencies.append("equal-sharing")
        return dependencies

    def _extract_fractions(self, problem_text: str) -> list[Fraction]:
        fractions: list[Fraction] = []
        for numerator, denominator in re.findall(r"(\d+)\s*/\s*(\d+)", problem_text):
            if denominator != "0":
                fractions.append(Fraction(int(numerator), int(denominator)))
        return fractions
