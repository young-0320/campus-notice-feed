"""장애·한도 대응 테스트: 사이트 접속 불가 시 건너뛰기, 이슈 본문 한도."""
import json

import requests

import check_notices as cn

SITES = [
    {"name": "가", "college": "가대", "base": "https://a.example/x", "filter": "all",
     "page_size": 30, "boards": [["공지1", "BMSR00040", "1"], ["공지2", "BMSR00040", "2"]]},
    {"name": "나", "college": "나대", "base": "https://b.example/y", "filter": "all",
     "page_size": 30, "boards": [["공지", "BMSR00040", "3"], ["자료", "BMSR00040", "4"]]},
]


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(cn, "SEEN_PATH", tmp_path / "seen.json")
    monkeypatch.setattr(cn, "TITLE_PATH", tmp_path / "issue_title.txt")
    monkeypatch.setattr(cn, "BODY_PATH", tmp_path / "issue_body.md")
    for env in ("DISCORD_WEBHOOK", "SMTP_USER", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(cn, "load_sites", lambda: SITES)
    (tmp_path / "seen.json").write_text(
        json.dumps({f"BMSR00040:{m}": ["1"] for m in "1234"}), encoding="utf-8")


def test_unreachable_site_is_skipped_once(tmp_path, monkeypatch):
    """접속이 안 되는 사이트는 첫 게시판에서만 시도하고 나머지는 건너뛴다.
    다른 사이트는 정상 수집하고, 건너뛴 게시판의 seen 은 그대로 둔다."""
    setup(tmp_path, monkeypatch)
    calls = []

    def fetch(base, board, menu, count=30):
        calls.append(menu)
        if base == "https://a.example/x":
            raise requests.ConnectionError("down")
        return [{"id": "9", "title": "새 글", "date": "2026-11-20", "tag": ""}], 1
    monkeypatch.setattr(cn, "fetch_board", fetch)
    cn.main()

    assert calls == ["1", "3", "4"]          # 가 사이트의 공지2(2)는 시도하지 않음
    body = (tmp_path / "issue_body.md").read_text(encoding="utf-8")
    assert "새 글" in body and body.count("수집 실패") == 2  # 섹션 제목 + 오류 1줄
    assert "건너뜀" in body
    seen = json.loads((tmp_path / "seen.json").read_text(encoding="utf-8"))
    assert seen["BMSR00040:1"] == ["1"] and seen["BMSR00040:2"] == ["1"]


def test_http_error_affects_only_that_board(tmp_path, monkeypatch):
    """404 같은 HTTP 오류는 그 게시판만의 문제일 수 있으므로 같은 사이트의
    다른 게시판은 계속 수집한다."""
    setup(tmp_path, monkeypatch)
    calls = []

    def fetch(base, board, menu, count=30):
        calls.append(menu)
        if menu == "1":
            raise requests.HTTPError("404")
        return [], 0
    monkeypatch.setattr(cn, "fetch_board", fetch)
    cn.main()
    assert calls == ["1", "2", "3", "4"]


def test_issue_body_is_capped(tmp_path, monkeypatch):
    """GitHub 이슈 본문 한도를 넘는 본문은 줄 경계에서 자르고 생략을 표시한다."""
    setup(tmp_path, monkeypatch)
    body = "\n".join(f"- 공지 {i} " + "가" * 80 for i in range(1000))
    assert len(body) > cn.ISSUE_BODY_MAX
    cn.write_output(True, "제목", body)
    written = (tmp_path / "issue_body.md").read_text(encoding="utf-8")
    assert len(written) <= cn.ISSUE_BODY_MAX + 1
    assert "일부 생략" in written
    assert written.splitlines()[-3].endswith("가" * 80)   # 줄 중간에서 끊기지 않음
