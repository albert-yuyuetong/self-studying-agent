class PracticeGenerator:
    def generate(self, knowledge_points: list[str], is_correct: bool) -> str:
        target = knowledge_points[0] if knowledge_points else "general-arithmetic"
        if is_correct:
            return f"Give one transfer problem on {target} with slightly changed context."
        return f"Give two scaffolded drills on {target}: one guided, one independent."
