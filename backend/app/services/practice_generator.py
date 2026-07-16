class PracticeGenerator:
    def generate(self, knowledge_points: list[str], is_correct: bool | None, question_type: str) -> str:
        if question_type == "open-ended":
            return "围绕同一题目要求，让孩子按“观点-依据-表达”三个槽位再重说或重写一版。"
        target = self._label(knowledge_points[0] if knowledge_points else "general-arithmetic")
        if is_correct:
            return f"围绕“{target}”再给 1 题轻微变式题，重点检查孩子能不能独立复述关键步骤。"
        return f"围绕“{target}”先给 1 题带提示练习，再给 1 题独立完成练习，先稳住步骤再迁移。"

    def _label(self, knowledge_point: str) -> str:
        labels = {
            "fraction-addition-unlike-denominator": "异分母分数加法",
            "fraction-addition-like-denominator": "同分母分数加法",
            "fraction-subtraction-unlike-denominator": "异分母分数减法",
            "common-denominator": "通分",
            "multiplication": "乘法",
            "division": "除法",
            "word-problem-arithmetic": "应用题理解",
            "general-arithmetic": "基础运算",
        }
        return labels.get(knowledge_point, knowledge_point)
