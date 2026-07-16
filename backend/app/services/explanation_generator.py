from app.services.llm_client import LLMClient


class ExplanationGenerator:
    def __init__(self) -> None:
        self.llm_client = LLMClient()

    def generate_parent_card(
        self,
        style: str,
        diagnosis: str,
        knowledge_points: list[str],
        problem_text: str,
        error_type: str | None,
        is_correct: bool | None,
        question_type: str,
        answer_analysis: str | None,
        parent_note: str | None = None,
    ) -> dict[str, list[str] | str]:
        llm_result = self.llm_client.generate_parent_guidance(
            problem_text=problem_text,
            diagnosis=diagnosis,
            knowledge_points=knowledge_points,
            style=style,
            error_type=error_type,
            question_type=question_type,
            answer_analysis=answer_analysis,
        )
        if llm_result:
            return self._merge_with_fallback(
                llm_result=llm_result,
                style=style,
                diagnosis=diagnosis,
                knowledge_points=knowledge_points,
                problem_text=problem_text,
                error_type=error_type,
                is_correct=is_correct,
                question_type=question_type,
                answer_analysis=answer_analysis,
                parent_note=parent_note,
            )

        return self._build_rule_based_guidance(
            style=style,
            diagnosis=diagnosis,
            knowledge_points=knowledge_points,
            problem_text=problem_text,
            error_type=error_type,
            is_correct=is_correct,
            question_type=question_type,
            answer_analysis=answer_analysis,
            parent_note=parent_note,
        )

    def _build_rule_based_guidance(
        self,
        *,
        style: str,
        diagnosis: str,
        knowledge_points: list[str],
        problem_text: str,
        error_type: str | None,
        is_correct: bool | None,
        question_type: str,
        answer_analysis: str | None,
        parent_note: str | None,
    ) -> dict[str, list[str] | str]:
        focus_text = "、".join(self._display_knowledge_points(knowledge_points))
        method = self._method_by_style(style)
        if question_type == "open-ended":
            parent_card = (
                f"这是一道开放题。诊断判断：{diagnosis}"
                f"建议家长先围绕评分点听孩子表达，再用{method}帮助孩子把观点、依据和表达结构说完整。"
            )
        else:
            parent_card = (
                f"本题重点：{focus_text}。"
                f"诊断判断：{diagnosis}"
                f"建议家长先{method}，再让孩子自己说出每一步为什么这样做。"
            )
        if answer_analysis:
            parent_card += f" 参考解析：{answer_analysis}。"
        if parent_note:
            parent_card += f" 家长补充信息可重点参考：{parent_note}。"

        return {
            "parent_card": parent_card,
            "suggested_questions": self._build_questions(error_type, is_correct, question_type),
            "coaching_steps": self._build_steps(style, error_type, is_correct, problem_text, question_type),
            "materials_needed": self._materials_for_style(style),
        }

    def _merge_with_fallback(
        self,
        *,
        llm_result: dict[str, list[str] | str],
        style: str,
        diagnosis: str,
        knowledge_points: list[str],
        problem_text: str,
        error_type: str | None,
        is_correct: bool | None,
        question_type: str,
        answer_analysis: str | None,
        parent_note: str | None,
    ) -> dict[str, list[str] | str]:
        fallback = self._build_rule_based_guidance(
            style=style,
            diagnosis=diagnosis,
            knowledge_points=knowledge_points,
            problem_text=problem_text,
            error_type=error_type,
            is_correct=is_correct,
            question_type=question_type,
            answer_analysis=answer_analysis,
            parent_note=parent_note,
        )
        merged = dict(fallback)
        for key in ["parent_card", "suggested_questions", "coaching_steps", "materials_needed"]:
            value = llm_result.get(key)
            if value:
                merged[key] = value
        return merged

    def _display_knowledge_points(self, knowledge_points: list[str]) -> list[str]:
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
        return [labels.get(item, item) for item in knowledge_points]

    def _method_by_style(self, style: str) -> str:
        if style == "visual":
            return "先画图或画线段图"
        if style == "hands-on":
            return "先用纸条、小物块等实物演示"
        if style == "story":
            return "先换成孩子熟悉的小故事情境"
        return "先用最短的话把关键步骤拆开"

    def _build_questions(
        self,
        error_type: str | None,
        is_correct: bool | None,
        question_type: str,
    ) -> list[str]:
        if question_type == "open-ended":
            return [
                "你觉得这道题最想让孩子表达什么？",
                "孩子刚才的回答里，有观点、有依据，还是只有结论？",
                "如果让孩子再说一遍，哪一部分最值得补充？",
            ]
        if is_correct is True:
            return [
                "你能不用看答案，再说一遍为什么要这样做吗？",
                "如果把数字换一下，哪一步还是一样的？",
                "你准备怎么快速检查自己做对了没有？",
            ]
        if error_type == "process":
            return [
                "这一步为什么不能直接算？",
                "在真正相加或相减之前，哪一步要先做？",
                "你能自己把中间步骤说出来吗？",
            ]
        if error_type == "calculation":
            return [
                "你的思路和刚才一样时，最容易算错的是哪一小步？",
                "你准备怎么验算这一行？",
                "如果再做一遍，你会先检查哪一个数字？",
            ]
        if error_type == "reading":
            return [
                "题目在问什么，不是在已知什么？",
                "哪些数字是已知条件，哪些是要算出来的？",
                "你能先不算，只把题意说清楚吗？",
            ]
        return [
            "你觉得这题最关键的一步是什么？",
            "哪一步开始变得不确定了？",
            "如果换一种画法或摆法，会不会更容易懂？",
        ]

    def _build_steps(
        self,
        style: str,
        error_type: str | None,
        is_correct: bool | None,
        problem_text: str,
        question_type: str,
    ) -> list[str]:
        opening = "先让孩子复述题目和自己的想法。"
        if question_type == "open-ended":
            return [
                opening,
                "先不要急着判对错，先听孩子把观点、依据和表达顺序说完整。",
                "再按题目要求一起补充遗漏的信息或例子，让孩子重说一遍。",
            ]
        if is_correct is True:
            return [
                opening,
                "让孩子解释每一步为什么成立，不要只报结果。",
                "把题目中的数字稍微换一下，再让孩子独立做一题。",
            ]

        if style == "visual":
            middle = "把题目画出来，尤其把每一步变化标出来，让抽象运算先变成看得见的过程。"
        elif style == "hands-on":
            middle = "先用纸条、方块或小物体摆出题目里的量，再从操作过渡到算式。"
        elif style == "story":
            middle = "把题目换成孩子熟悉的生活情境，再把情境一步步映射回算式。"
        else:
            middle = "把关键步骤拆成两到三句短话，一句只讲一个动作。"

        closing = "最后让孩子自己复述关键步骤，再做一题同类小变式。"
        if error_type == "reading":
            middle = "先圈出题目在问什么和已知什么，确认孩子不是在审题阶段走偏。"
        if "分数" in problem_text or "/" in problem_text:
            closing = "最后让孩子自己说出单位是否一致，再回到算式。"
        return [opening, middle, closing]

    def _materials_for_style(self, style: str) -> list[str]:
        if style == "visual":
            return ["草稿纸", "彩笔"]
        if style == "hands-on":
            return ["纸条", "小物块"]
        if style == "story":
            return ["生活情境示例"]
        return []
