"""notify_email / md_to_html 테스트 (SMTP 없이 smtplib.SMTP_SSL 을 mock).

Discord 와 같은 요구사항: Secret 이 없으면 아무것도 하지 않고, 실패가 주 채널
(GitHub Issue)을 죽이지 않으며, 주소·비밀번호가 출력에 새지 않는다.
"""
import smtplib

import check_notices as cn

USER = "sender@example.com"
PASSWORD = "app-password-SECRET"
TO = "a@example.com, b@example.com"


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        self.auth = (user, password)

    def send_message(self, msg, from_addr=None, to_addrs=None):
        FakeSMTP.sent.append((msg, from_addr, to_addrs))


def set_env(monkeypatch):
    monkeypatch.setenv("SMTP_USER", USER)
    monkeypatch.setenv("SMTP_PASSWORD", PASSWORD)
    monkeypatch.setenv("MAIL_TO", TO)


def test_md_to_html_renders_and_escapes():
    """main() 이 만드는 구문만 변환하고, 게시글 제목의 HTML 은 이스케이프한다."""
    body = ("## ⭐ 관심 키워드 매칭\n\n"
            "- **[전자 공지]** [<b>공모전</b> \\[1차\\]](https://a.example/v?x=1&y=2) `2026-11-20`\n"
            "- [전자 공지] [둘째](https://a.example/v2) `2026-11-19` · 외 1곳\n")
    out = cn.md_to_html(body)
    assert "<h3>⭐ 관심 키워드 매칭</h3>" in out
    assert out.count("<ul>") == 1 and out.count("<li>") == 2
    assert '<a href="https://a.example/v?x=1&amp;y=2">&lt;b&gt;공모전&lt;/b&gt; [1차]</a>' in out
    assert "<b>[전자 공지]</b>" in out
    assert "<code>2026-11-20</code>" in out


def test_md_to_html_ignores_non_http_links():
    """http(s) 가 아닌 링크는 링크로 만들지 않는다."""
    assert "<a " not in cn.md_to_html("- [x](javascript:alert(1))")


def test_skips_without_env(monkeypatch):
    """Secret 이 하나라도 없으면 SMTP 접속 자체가 없어야 한다."""
    set_env(monkeypatch)
    monkeypatch.delenv("MAIL_TO")

    def boom(*a, **kw):
        raise AssertionError("호출되면 안 됨")
    monkeypatch.setattr(cn.smtplib, "SMTP_SSL", boom)
    cn.notify_email("제목", "본문")


def test_sends_bcc(monkeypatch):
    """수신자는 봉투로만 전달하고 헤더에는 발신자만 적는다(서로 주소 비노출)."""
    set_env(monkeypatch)
    FakeSMTP.sent = []
    monkeypatch.setattr(cn.smtplib, "SMTP_SSL", FakeSMTP)
    cn.notify_email("[KHU] 신규 공지 1건", "- [전자 공지] [글](https://a.example/v) `2026-11-20`")
    (msg, from_addr, to_addrs), = FakeSMTP.sent
    assert from_addr == USER
    assert to_addrs == ["a@example.com", "b@example.com"]
    assert msg["To"] == USER and "a@example.com" not in msg.as_string()
    assert msg["Subject"] == "[KHU] 신규 공지 1건"
    assert msg.get_body(("html",)) is not None


def test_failure_is_swallowed_without_leaking(monkeypatch, capsys):
    """인증 실패 등은 삼키고, 출력에는 예외 타입만 남긴다."""
    set_env(monkeypatch)

    class Refuse(FakeSMTP):
        def login(self, user, password):
            raise smtplib.SMTPAuthenticationError(535, f"bad credentials for {user} {password}".encode())
    monkeypatch.setattr(cn.smtplib, "SMTP_SSL", Refuse)
    cn.notify_email("제목", "본문")
    out = "".join(capsys.readouterr())
    assert "SMTPAuthenticationError" in out
    assert USER not in out and PASSWORD not in out and "a@example.com" not in out
