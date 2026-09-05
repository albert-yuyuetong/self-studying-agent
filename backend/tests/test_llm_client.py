import json

import httpx
import pytest

from app.core.config import Settings
from app.schemas.diagnosis import Assessment
from app.services.llm_client import LLMClient, ModelOutputError, ModelUnavailable


def config(**kwargs):
    return Settings(llm_enabled=True, llm_api_key="test-secret",
                    llm_model="configured-model", **kwargs)


def completion(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})


def assessment(**changes):
    return {"verdict": "supported", "summary": "依据充分", "evidence": ["学生给出了依据"],
            "confidence": 0.9, **changes}


def generate(client, **kwargs):
    return client.generate(schema=Assessment, system_prompt="test", context={"student_answer": "完整作答"},
                           stage="assessment", **kwargs)


def test_complete_answer_is_forwarded_without_numeric_extraction():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return completion(json.dumps(assessment()))

    client = LLMClient(config(), httpx.MockTransport(handler))
    generate(client)
    assert json.loads(seen[0]["messages"][1]["content"])["student_answer"] == "完整作答"
    assert seen[0]["model"] == "configured-model"


def test_invalid_output_gets_one_repair_only():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return completion(json.dumps(assessment(confidence=1.8)))

    with pytest.raises(ModelOutputError):
        generate(LLMClient(config(), httpx.MockTransport(handler)))
    assert len(calls) == 2
    assert len(calls[1]["messages"]) == 4


def test_successful_format_repair_and_strict_validation():
    calls = []

    def handler(request):
        calls.append(request)
        content = assessment(confidence="0.9") if len(calls) == 1 else assessment()
        return completion(json.dumps(content))

    result = generate(LLMClient(config(), httpx.MockTransport(handler)))
    assert result.confidence == 0.9
    assert len(calls) == 2


@pytest.mark.parametrize("body", [None, {}, {"choices": []}, {"choices": [{"message": {"content": None}}]}])
def test_malformed_provider_envelope_is_controlled(body):
    with pytest.raises(ModelOutputError):
        generate(LLMClient(config(), httpx.MockTransport(lambda _: httpx.Response(200, json=body))))


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_transport_errors_do_not_expose_response_secrets(status):
    with pytest.raises(ModelUnavailable) as caught:
        generate(LLMClient(config(), httpx.MockTransport(
            lambda _: httpx.Response(status, text="test-secret and private child answer"))))
    assert "test-secret" not in str(caught.value)
    assert "private child" not in str(caught.value)


def test_disabled_provider_never_sends_request():
    def handler(_):
        raise AssertionError("must not call model")

    with pytest.raises(ModelUnavailable):
        generate(LLMClient(Settings(llm_enabled=False), httpx.MockTransport(handler)))


def test_images_require_explicit_vision_capability():
    with pytest.raises(ModelUnavailable):
        generate(LLMClient(config(), httpx.MockTransport(lambda _: None)),
                 images=["https://example.test/image.png"])


def test_image_is_sent_as_multimodal_content():
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return completion(json.dumps(assessment()))

    generate(LLMClient(config(llm_vision_enabled=True), httpx.MockTransport(handler)),
             images=["https://example.test/image.png"])
    content = captured[0]["messages"][1]["content"]
    assert content[1] == {"type": "image_url", "image_url": {"url": "https://example.test/image.png"}}
