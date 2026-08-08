"""test_credentials.py: 加密往返、API 不泄露明文、脱敏格式 (SPEC §11)."""
from app.core.security import (decrypt_secret, encrypt_secret, mask_secret,
                               redact)


def test_encrypt_decrypt_roundtrip():
    secret = "sk-abc123def456"
    token = encrypt_secret(secret)
    assert token != secret
    assert decrypt_secret(token) == secret


def test_mask_format():
    assert mask_secret("sk-abcdef12") == "****ef12"
    assert mask_secret("") == "****"


def test_redact_logs():
    assert redact("key is sk-abcdefgh1234 ok") == "key is sk-****1234 ok"


async def test_api_never_leaks_plaintext(client):
    secret = "sk-supersecretvalue99"
    resp = await client.post("/api/credentials", json={
        "name": "test-key", "kind": "video", "provider": "minimax",
        "api_key": secret, "is_default": True,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["masked_secret"] == "****ue99"
    assert secret not in resp.text
    assert "api_key" not in body
    assert "secret_encrypted" not in body

    cred_id = body["id"]
    list_resp = await client.get("/api/credentials?kind=video")
    assert list_resp.status_code == 200
    assert secret not in list_resp.text
    assert list_resp.json()[0]["masked_secret"] == "****ue99"

    # 编辑时空白 api_key = 不变
    put = await client.put(f"/api/credentials/{cred_id}", json={"name": "renamed"})
    assert put.status_code == 200
    assert put.json()["name"] == "renamed"
    assert put.json()["masked_secret"] == "****ue99"  # secret 未变


async def test_test_connection_failure_not_crash(client, mocker):
    """假 key 调 test_connection 应返回失败但不崩溃。"""
    resp = await client.post("/api/credentials", json={
        "name": "fake", "kind": "video", "provider": "minimax", "api_key": "sk-fakekey0000",
    })
    cred_id = resp.json()["id"]

    fake_provider = mocker.Mock()
    fake_provider.test_connection = mocker.AsyncMock(return_value=(False, "认证失败（401）：请检查 API Key"))
    mocker.patch("app.api.credentials.get_video_provider", return_value=fake_provider)

    test_resp = await client.post(f"/api/credentials/{cred_id}/test")
    assert test_resp.status_code == 200
    assert test_resp.json() == {"ok": False, "message": "认证失败（401）：请检查 API Key"}
