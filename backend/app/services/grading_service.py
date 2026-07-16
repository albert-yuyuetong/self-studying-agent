import re
from fractions import Fraction


class GradingService:
    def grade(
        self,
        problem_text: str,
        student_answer: str,
        expected_answer: str,
        knowledge_points: list[str],
    ) -> dict[str, str | bool | float]:
        normalized_student = self._normalize_answer(student_answer)
        normalized_expected = self._normalize_answer(expected_answer)
        student_value = self._parse_numeric(normalized_student)
        expected_value = self._parse_numeric(normalized_expected)

        is_correct = False
        if student_value is not None and expected_value is not None:
            is_correct = student_value == expected_value
        else:
            is_correct = normalized_student == normalized_expected

        if is_correct:
            return {
                "is_correct": True,
                "error_type": "none",
                "diagnosis": "孩子这题答对了。下一步重点不是重复答案，而是让孩子说清楚为什么这样做，再做一道变式题确认真正理解。",
                "confidence": 0.92,
            }

        error_type = self._infer_error_type(
            problem_text=problem_text,
            knowledge_points=knowledge_points,
            student_answer=normalized_student,
            student_value=student_value,
            expected_value=expected_value,
        )
        diagnosis = self._build_diagnosis(error_type, knowledge_points)
        confidence = 0.82 if error_type in {"process", "calculation"} else 0.68

        return {
            "is_correct": False,
            "error_type": error_type,
            "diagnosis": diagnosis,
            "confidence": confidence,
        }

    def _normalize_answer(self, answer: str) -> str:
        return re.sub(r"\s+", "", answer).replace("＝", "=").strip()

    def _parse_numeric(self, answer: str) -> Fraction | None:
        if not answer:
            return None
        match = re.search(r"-?\d+\s*/\s*-?\d+|-?\d+(?:\.\d+)?", answer)
        if not match:
            return None
        token = match.group(0).replace(" ", "")
        try:
            if "/" in token:
                numerator, denominator = token.split("/", 1)
                if denominator == "0":
                    return None
                return Fraction(int(numerator), int(denominator))
            return Fraction(token)
        except (ValueError, ZeroDivisionError):
            return None

    def _infer_error_type(
        self,
        *,
        problem_text: str,
        knowledge_points: list[str],
        student_answer: str,
        student_value: Fraction | None,
        expected_value: Fraction | None,
    ) -> str:
        if not student_answer:
            return "no-answer"

        if "fraction-addition-unlike-denominator" in knowledge_points and self._looks_like_fraction_addition_shortcut(
            problem_text, student_value
        ):
            return "process"

        if "fraction-subtraction-unlike-denominator" in knowledge_points and self._looks_like_fraction_subtraction_shortcut(
            problem_text, student_value
        ):
            return "process"

        if student_value is not None and expected_value is not None:
            if abs(float(student_value - expected_value)) <= 1:
                return "calculation"
            return "concept"

        if any(keyword in problem_text for keyword in ["多少", "一共", "还剩", "至少"]):
            return "reading"
        return "concept"

    def _looks_like_fraction_addition_shortcut(self, problem_text: str, student_value: Fraction | None) -> bool:
        fractions = self._extract_problem_fractions(problem_text)
        if len(fractions) < 2 or student_value is None:
            return False
        shortcut = Fraction(fractions[0].numerator + fractions[1].numerator, fractions[0].denominator + fractions[1].denominator)
        return student_value == shortcut

    def _looks_like_fraction_subtraction_shortcut(self, problem_text: str, student_value: Fraction | None) -> bool:
        fractions = self._extract_problem_fractions(problem_text)
        if len(fractions) < 2 or student_value is None:
            return False
        denominator = fractions[0].denominator - fractions[1].denominator
        if denominator == 0:
            return False
        shortcut = Fraction(fractions[0].numerator - fractions[1].numerator, denominator)
        return student_value == shortcut

    def _extract_problem_fractions(self, problem_text: str) -> list[Fraction]:
        fractions: list[Fraction] = []
        for numerator, denominator in re.findall(r"(\d+)\s*/\s*(\d+)", problem_text):
            if denominator != "0":
                fractions.append(Fraction(int(numerator), int(denominator)))
        return fractions

    def _build_diagnosis(self, error_type: str, knowledge_points: list[str]) -> str:
        kp_text = "、".join(knowledge_points) if knowledge_points else "当前知识点"
        if error_type == "process":
            return f"这题更像是步骤没有站稳，尤其是 {kp_text} 里的关键中间步骤。建议先讲为什么要这样做，再让孩子自己复述步骤。"
        if error_type == "calculation":
            return f"这题更像是计算执行不稳定，不一定是概念不会。可以先保留原思路，再单独检查 {kp_text} 相关计算步骤。"
        if error_type == "reading":
            return "这题可能不只是算错，更像是审题信息没有抓准。建议家长先让孩子用自己的话重述题意。"
        if error_type == "no-answer":
            return "孩子还没有给出明确答案，先不要急着讲解，先问清楚卡在读题、列式，还是计算。"
        return f"这题更像是 {kp_text} 的概念理解还不稳定。建议先用图示或实物把抽象步骤讲具体。"
