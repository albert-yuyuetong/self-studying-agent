class ExplanationGenerator:
    def generate_parent_card(
        self,
        style: str,
        diagnosis: str,
        knowledge_points: list[str],
    ) -> dict[str, list[str] | str]:
        kp_text = ", ".join(knowledge_points)
        if style == "visual":
            method = "Draw a simple diagram and mark each computation step with colors."
        elif style == "hands-on":
            method = "Use tangible objects to model each step before writing symbols."
        else:
            method = "Tell a short story scenario and map each sentence to one equation step."

        return {
            "parent_card": f"Diagnosis: {diagnosis} Focus points: {kp_text}. Coaching method: {method}",
            "suggested_questions": [
                "Can you explain why this step is needed?",
                "Which number changed and why?",
                "How would you check your answer in one quick way?",
            ],
        }
