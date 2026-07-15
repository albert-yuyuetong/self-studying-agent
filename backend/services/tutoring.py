from backend.models import DiagnosisResult, ParentGuidanceCard, StudentProfile


class TutoringService:
    def build_parent_guidance(
        self,
        profile: StudentProfile,
        diagnosis: DiagnosisResult,
    ) -> ParentGuidanceCard:
        style_step = {
            "visual": "先画图或列出示意关系，再带着孩子口头复述。",
            "auditory": "先用生活化语言复述题意，再让孩子跟着说一遍。",
            "hands_on": "先拿实物演示数量或关系，再回到纸面表达。",
            "reading": "先把题目拆成已知、未知、关系三部分再讲。",
        }[profile.learning_style]

        return ParentGuidanceCard(
            summary=f"优先围绕“{diagnosis.knowledge_points[0]}”进行家长视角讲解。",
            coaching_steps=[
                "先确认孩子卡住的是概念、步骤还是审题。",
                style_step,
                "最后让孩子自己复述思路，而不是直接记答案。",
            ],
            key_questions=[
                "你觉得这道题第一步应该先看什么？",
                "如果换一种画图或举例方式，会不会更容易理解？",
            ],
            suggested_props=["草稿纸", "铅笔", "可视化示意图"],
            next_action="如果孩子仍然不懂，生成一道更小一步的同类练习继续验证。",
        )
