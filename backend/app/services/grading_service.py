class GradingService:
    def grade(self, student_answer: str, expected_answer: str) -> dict[str, str | bool]:
        is_correct = student_answer.strip() == expected_answer.strip()
        if is_correct:
            error_type = "none"
            diagnosis = "Answer is correct. Reinforce reasoning and transfer to a similar problem."
        else:
            error_type = "concept-or-process"
            diagnosis = "Answer is incorrect. Likely misunderstanding in concept or process steps."

        return {
            "is_correct": is_correct,
            "error_type": error_type,
            "diagnosis": diagnosis,
        }
