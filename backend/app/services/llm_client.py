"""A small, typed boundary to an explicitly configured chat-completions provider."""

from collections.abc import Sequence
import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, settings


Output = TypeVar("Output", bound=BaseModel)


class ModelUnavailable(RuntimeError):
    """Configuration or transport prevented a model operation. Messages are public-safe."""


class ModelOutputError(RuntimeError):
    """The provider returned an unusable or contradictory result."""


class LLMClient:
    def __init__(
        self,
        config: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config or settings
        self.transport = transport

    @property
    def enabled(self) -> bool:
        return bool(
            self.config.llm_enabled
            and self.config.llm_api_key.strip()
            and self.config.llm_model.strip()
            and self.config.llm_base_url.strip()
        )

    def generate(
        self,
        *,
        schema: type[Output],
        system_prompt: str,
        context: dict[str, Any],
        images: Sequence[str] = (),
        stage: str,
        model: str | None = None,
    ) -> Output:
        """Validate all fields strictly, allowing one format-only repair attempt.

        Schema validation is a format check, not a claim that the answer is true.
        The tutor's separate verification stage checks the educational content.
        """
        if not self.enabled:
            raise ModelUnavailable("尚未配置模型。请在后端 .env 中启用模型并填写服务地址、模型名和 API 密钥。")
        if images and not self.config.llm_vision_enabled:
            raise ModelUnavailable("当前模型未启用图片理解。请提供完整文字题目，或配置支持图片的模型并启用 LLM_VISION_ENABLED。")

        schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        instructions = (
            system_prompt
            + "\n仅返回一个符合以下 JSON Schema 的 JSON 对象。不要输出代码围栏、额外字段或解释。"
            + "所有字段使用准确的 JSON 类型，confidence 是 0 到 1 的数值。\n"
            + schema_text
        )
        text_input = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        user_content: str | list[dict[str, Any]] = text_input
        if images:
            user_content = [
                {"type": "text", "text": text_input},
                *({"type": "image_url", "image_url": {"url": url}} for url in images),
            ]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_content},
        ]

        for attempt in range(2):
            content = self._complete(messages, model or self.config.llm_model)
            if len(content) > 200_000:
                raise ModelOutputError("模型输出过长，无法可靠处理，请缩小本次辅导范围后重试。")
            try:
                return schema.model_validate_json(content, strict=True)
            except ValidationError as exc:
                if attempt:
                    raise ModelOutputError("模型结果未通过结构校验，请重试；本次结果不会作为学习证据。") from None
                # Never return raw model text, validation inputs, HTTP bodies or keys to callers.
                errors = [
                    {"field": list(error["loc"]), "type": error["type"]}
                    for error in exc.errors(include_url=False, include_input=False)[:20]
                ]
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "format_repair": "仅修复刚才结果的 JSON 语法、字段和类型，使其满足系统 Schema。不要增添题目条件、学生作答、能力判断或新的事实。无法确认的结论应保留不确定状态。只返回完整 JSON 对象。",
                                    "validation_errors": errors,
                                    "stage": stage,
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ]
                )
        raise ModelOutputError("模型结果未通过结构校验。")

    def _complete(self, messages: list[dict[str, Any]], model: str) -> str:
        body = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        try:
            with httpx.Client(
                timeout=self.config.llm_timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    self.config.llm_base_url.rstrip("/") + "/chat/completions",
                    headers={
                        "Authorization": "Bearer " + self.config.llm_api_key,
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
        except httpx.TimeoutException:
            raise ModelUnavailable("模型服务响应超时，请稍后重试；本次不会更新学习画像。") from None
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {401, 403}:
                message = "模型服务拒绝了认证，请检查后端模型密钥和访问权限。"
            elif status == 429:
                message = "模型服务当前请求受限，请稍后重试。"
            else:
                message = "模型服务暂时不可用，请检查模型配置或稍后重试。"
            raise ModelUnavailable(message) from None
        except (httpx.HTTPError, httpx.InvalidURL, ValueError):
            raise ModelUnavailable("无法连接模型服务，请检查后端模型地址和网络后重试。") from None

        try:
            payload = response.json()
            choice = payload["choices"][0]
            if choice.get("finish_reason") in {"length", "content_filter"}:
                raise ModelOutputError("模型未能完整返回结果，请调整题目材料或稍后重试。")
            message = choice["message"]
            if message.get("refusal"):
                raise ModelOutputError("模型未能处理这次辅导请求，请调整题目材料后重试。")
            content = message["content"]
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise ModelOutputError("模型服务返回了无法识别的响应，请检查模型兼容性后重试。") from None
        if not isinstance(content, str) or not content.strip():
            raise ModelOutputError("模型没有返回有效辅导内容，请重试。")
        return content
