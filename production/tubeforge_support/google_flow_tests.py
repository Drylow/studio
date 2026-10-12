"""Provider contracts: exact references, no duplicate paid request, secret isolation."""
import asyncio
import base64
import io
import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

VENDOR = Path(__file__).parent.parent if Path(__file__).parent.name == "tests" else Path(__file__).parents[2] / "work/TubeForge"
sys.path.insert(0, str(VENDOR))
from app import google_flow as flow, config, llm


def picture(color="white"):
    stream = io.BytesIO()
    Image.new("RGB", (32, 18), color).save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def provider(monkeypatch):
    values = {"USEAPI_API_KEY": "private-test-key", "USEAPI_IMAGE_MODEL": "fixture-image",
              "USEAPI_IMAGE_CONCURRENCY": "3"}
    monkeypatch.setattr(config, "get", lambda key: values.get(key, ""))
    flow.reset()
    calls = []
    def handle(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer private-test-key"
        if request.url.path.endswith("/accounts"):
            return httpx.Response(200, json={f"account{i}@example.invalid": {
                "health": "OK", "backend": "flow", "cookie": "private-cookie"} for i in range(3)})
        if "/assets/" in request.url.path:
            return httpx.Response(200, json={"mediaGenerationId": {"mediaGenerationId": "ref-" + str(len(calls))}})
        assert request.url.path.endswith("/images")
        return httpx.Response(200, json={"jobId": "test-job", "media": [{"image": {"generatedImage": {
            "encodedImage": base64.b64encode(picture()).decode()}}}]})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(flow, "client", lambda: client)
    yield calls, client
    asyncio.run(client.aclose())
    flow.reset()


def test_exact_prompt_reference_order_and_account_rotation(provider):
    calls, _ = provider
    async def run():
        state = await flow.status()
        assert "private-cookie" not in str(state) and "private-test-key" not in str(state)
        receipt = {}
        assert await flow.generate("Exact prompt", "fixture-image", "16:9", [picture("red"), picture("blue")], receipt) == picture()
        assert receipt["dimensions"] == [32, 18] and receipt["count"] == 1
        await flow.generate("Next", "fixture-image", "16:9")
        await flow.generate("Next", "fixture-image", "16:9")
        await flow.generate("Again", "fixture-image", "16:9", [picture("red"), picture("blue")])
    asyncio.run(run())
    uploads = [r for r in calls if "/assets/" in r.url.path]
    assert [r.content for r in uploads] == [picture("red"), picture("blue")]
    bodies = [json.loads(r.content) for r in calls if r.url.path.endswith("/images")]
    assert [b["email"] for b in bodies] == [f"account{i}@example.invalid" for i in (0, 1, 2, 0)]
    assert bodies[0] == {"email": "account0@example.invalid", "prompt": "Exact prompt", "model": "fixture-image",
                          "aspectRatio": "16:9", "count": 1, "reference_1": "ref-2", "reference_2": "ref-3"}


@pytest.mark.parametrize("failure", ["timeout", "quota", "denied", "captcha", "captcha-missing"])
def test_failure_does_not_replay_or_expose_credentials(provider, monkeypatch, failure):
    calls, client = provider
    async def post(*args, **kwargs):
        calls.append((args, kwargs))
        if failure == "timeout":
            raise httpx.ReadTimeout("private-test-key")
        status = 429 if failure == "quota" else 400 if failure == "captcha-missing" else 403
        body = ("No captcha provider API keys configured. Add at least one at "
                "https://example.invalid/private-cookie?key=private-test-key&email=account0@example.invalid"
                if failure == "captcha-missing" else "MODEL_ACCESS_DENIED" if failure == "denied"
                else "ZERO_BALANCE" if failure == "captcha" else "private-cookie")
        return httpx.Response(status, json={"error": body, "session": "private-test-key"}, headers={"Retry-After": "45"})
    monkeypatch.setattr(client, "post", post)
    with pytest.raises(flow.FlowError) as error:
        asyncio.run(flow.generate("Exact", "fixture-image", "16:9"))
    assert len([c for c in calls if isinstance(c, tuple)]) == 1
    assert "private-test-key" not in str(error.value) and "private-cookie" not in str(error.value)
    if failure == "quota":
        assert "account0@example.invalid" in flow._cooldowns
    assert error.value.global_configuration_error is (failure == "captcha-missing")
    if failure == "captcha-missing":
        assert error.value.status == 400
        assert "fournisseur captcha" in str(error.value) and "crédits" in str(error.value)
        assert "account0@example.invalid" not in str(error.value) and "example.invalid" not in str(error.value)


def test_isolated_captcha_refusal_is_not_a_global_configuration_error():
    error = flow._error(httpx.Response(400, json={
        "error": "Captcha verification failed for private-account@example.invalid",
        "key": "private-provider-key"}))
    assert error.global_configuration_error is False
    assert str(error) == "Google Flow is unavailable or refused the request (HTTP 400)."
    assert "private-" not in str(error)


def test_reference_limit_rejects_before_network(provider):
    calls, _ = provider
    with pytest.raises(flow.FlowError, match="10 references"):
        asyncio.run(flow.generate("Exact", "fixture-image", "16:9", [picture()] * 11))
    assert calls == []


def test_download_does_not_receive_api_key(provider, monkeypatch):
    _, client = provider
    original_post = client.post
    async def post(url, **kwargs):
        if url.endswith("/images"):
            return httpx.Response(200, json={"media": [{"image": {"generatedImage": {"fifeUrl": "https://media.example.invalid/generated"}}}]})
        return await original_post(url, **kwargs)
    monkeypatch.setattr(client, "post", post)
    def download(request):
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=picture())
    real_client = httpx.AsyncClient
    monkeypatch.setattr(flow.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(download), **kwargs))
    assert asyncio.run(flow.generate("Exact", "fixture-image", "16:9")) == picture()


def test_llm_dispatch_bypasses_proxy_and_preserves_stats(provider, monkeypatch):
    request = AsyncMock(return_value=picture())
    monkeypatch.setattr(flow, "generate", request)
    monkeypatch.setattr(llm, "client", lambda: pytest.fail("Proxy must not be used"))
    before = dict(llm.STATS["image"])
    receipt = {}
    assert asyncio.run(llm.generate_image("Exact", model="fixture-image", refs=[picture()], provider="google_flow", receipt=receipt)) == picture()
    request.assert_awaited_once_with("Exact", "fixture-image", "16:9", [picture()], receipt)
    assert llm.STATS["image"]["done"] == before["done"] + 1
    assert llm.STATS["image"]["active"] == before["active"]


def test_portrait_output_rejected_without_paid_retry(provider, monkeypatch):
    calls, client = provider
    original_post = client.post
    async def post(url, **kwargs):
        if url.endswith("/images"):
            calls.append("paid image request")
            stream = io.BytesIO()
            Image.new("RGB", (18, 32), "white").save(stream, format="PNG")
            return httpx.Response(200, json={"jobId": "wrong-shape", "media": [{"image": {"generatedImage": {
                "encodedImage": base64.b64encode(stream.getvalue()).decode()}}}]})
        return await original_post(url, **kwargs)
    monkeypatch.setattr(client, "post", post)
    receipt = {}
    with pytest.raises(flow.FlowError, match="format"):
        asyncio.run(flow.generate("Exact landscape prompt", "fixture-image", "16:9", receipt=receipt))
    assert calls.count("paid image request") == 1
    assert receipt["dimensions"] == [18, 32]
    assert receipt["job_id"] == "wrong-shape"
