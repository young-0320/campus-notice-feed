"""notify_discord 테스트 (HTTP 없이 requests.post를 mock).

보안 요구사항 검증이 핵심: URL이 로그/예외 출력에 새지 않고,
전송 실패가 주 채널(GitHub Issue) 경로를 죽이지 않아야 한다.
"""
import requests

import check_notices
from check_notices import notify_discord

FAKE_URL = "https://discord.com/api/webhooks/123/SECRET-TOKEN"


def test_skips_without_env(monkeypatch):
    """DISCORD_WEBHOOK 미설정이면 전송 시도 자체가 없어야 한다."""
    monkeypatch.delenv("DISCORD_WEBHOOK", raising=False)
    monkeypatch.setattr(check_notices.requests, "post",
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("호출되면 안 됨")))
    notify_discord("제목", "본문")


def test_sends_embed_payload(monkeypatch):
    """json= 으로 embed 페이로드를 보내고, 길이 제한을 지킨다."""
    monkeypatch.setenv("DISCORD_WEBHOOK", FAKE_URL)
    calls = []

    class OkResp:
        def raise_for_status(self):
            pass

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json, timeout))
        return OkResp()

    monkeypatch.setattr(check_notices.requests, "post", fake_post)
    notify_discord("T" * 300, "B" * 5000)

    (url, payload, timeout), = calls
    assert url == FAKE_URL
    embed = payload["embeds"][0]
    assert embed["title"] == "T" * 256
    assert embed["description"] == "B" * 4096
    assert timeout


def test_failure_swallowed_and_url_not_leaked(monkeypatch, capsys):
    """전송 실패 시: 예외를 밖으로 던지지 않고, 출력에 URL이 없어야 한다.
    (requests 예외 메시지에는 URL이 포함되므로 그대로 찍으면 유출.)"""
    monkeypatch.setenv("DISCORD_WEBHOOK", FAKE_URL)

    def fake_post(url, json=None, timeout=None):
        raise requests.ConnectionError(f"Failed to connect to {url}")

    monkeypatch.setattr(check_notices.requests, "post", fake_post)
    notify_discord("제목", "본문")  # 예외가 새면 여기서 테스트 실패

    out = capsys.readouterr()
    combined = out.out + out.err
    assert FAKE_URL not in combined
    assert "SECRET-TOKEN" not in combined
    assert "ConnectionError" in combined
