import json

import httpx

from app.core.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.enabled = settings.llm_enabled and bool(settings.llm_api_key)

    def generate_parent_guidance(
        self,
        *,
        problem_text: str,
        diagnosis: str,
        knowledge_points: list[str],
        style: str,
        error_type: str | None,
        question_type: str,
        answer_analysis: str | None,
    ) -> dict[str, list[str] | str] | None:
        if not self.enabled:
            return None

        system_prompt = (
            "你是一名面向家长的学科辅导助手。"
            "输出必须是 JSON 对象，不要输出 markdown。"
            "不要直接给最终答案，要突出家长如何讲、先问什么、需要什么道具。"
        )
        user_prompt = {
            "problem_text": problem_text,
            "diagnosis": diagnosis,
            "knowledge_points": knowledge_points,
            "style": style,
            "error_type": error_type,
            "question_type": question_type,
            "answer_analysis": answer_analysis,
            "required_fields": [
                "parent_card",
                "suggested_questions",
                "coaching_steps",
                "materials_needed",
            ],
        }

        try:
            response = httpx.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
                    ],
                },
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        try:
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError):
            return None

        if not isinstance(parsed, dict):
            return None

        return parsed

    def analyze_problem(
        self,
        *,
        subject: str,
        grade: str | None,
        problem_text: str,
        attachments: list[str],
        parent_note: str | None,
    ) -> dict[str, object] | None:
        if not self.enabled:
            return None

        system_prompt = (
            "你是一名题目识别与辅导前置分析助手。"
            "你只做两件事："
            "第一，判断题目属于 standard-answer 还是 open-ended；"
            "第二，输出 answer_analysis。"
            "standard-answer 表示有标准答案但需要推导或判定；"
            "open-ended 表示没有唯一标准答案，更适合按评分点辅导。"
            "如果题目属于 standard-answer，你必须优先尝试产出 reference_answer 和最短可验证解题步骤；"
            "只有在题目信息严重缺失、歧义过大或根本无法可靠推导时，才允许把 reference_answer 设为 null。"
            "如果题目属于 open-ended，reference_answer 必须为 null，并给出 evaluation_focus。"
            "normalized_problem 要尽量把题目整理成可读文本。"
            "solution_outline 必须简短、可执行、可用于后续辅导。"
            "confidence 反映你对题型判断和解析可靠性的综合信心。"
            "输出必须是 JSON 对象，不要输出 markdown，不要输出额外解释。"
        )

        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "subject": subject,
                        "grade": grade,
                        "problem_text": problem_text,
                        "parent_note": parent_note,
                        "attachments": attachments,
                        "decision_rules": [
                            "standard-answer 题必须尽量产出 reference_answer",
                            "open-ended 题不得伪造唯一标准答案",
                            "如果能从题干直接推导，就不要因为缺少家长参考答案而返回 null",
                            "如果 reference_answer 为 null，summary 必须明确说明为什么当前无法可靠推导",
                        ],
                        "examples": {
                            "standard-answer": [
                                "数学应用题",
                                "语法改错",
                                "公式题",
                                "填空题",
                                "选择题"
                            ],
                            "open-ended": [
                                "作文题",
                                "阅读理解开放问答",
                                "主观看法题"
                            ]
                        },
                        "output_schema": {
                            "question_type": "standard-answer | open-ended",
                            "answer_analysis": {
                                "normalized_problem": "string | null",
                                "reference_answer": "string | null",
                                "solution_outline": ["string"],
                                "evaluation_focus": ["string"],
                                "summary": "string",
                                "confidence": "number 0-1",
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
            }
        ]

        for attachment in attachments:
            if attachment.startswith("http://") or attachment.startswith("https://") or attachment.startswith("data:image"):
                content.append({"type": "image_url", "image_url": {"url": attachment}})
            else:
                content.append({"type": "text", "text": f"attachment_ref: {attachment}"})

        try:
            response = httpx.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content},
                    ],
                },
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        try:
            content_text = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content_text)
        except (KeyError, IndexError, TypeError, ValueError):
            return None

        if not isinstance(parsed, dict):
            return None

        question_type = parsed.get("question_type")
        answer_analysis = parsed.get("answer_analysis")
        if question_type not in {"standard-answer", "open-ended"}:
            return None
        if not isinstance(answer_analysis, dict):
            return None

        reference_answer = answer_analysis.get("reference_answer")
        if isinstance(reference_answer, str):
            answer_analysis["reference_answer"] = reference_answer.strip() or None

        return {
            "question_type": question_type,
            "answer_analysis": answer_analysis,
            "reference_answer_source": "llm-derived" if answer_analysis.get("reference_answer") else None,
        }