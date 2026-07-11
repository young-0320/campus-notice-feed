"""반복 오류의 Discord dedup 통합 테스트 — main()을 실제로 실행.

GitHub 쪽은 동일 제목 open 이슈에 댓글로 합쳐 반복 이슈를 막는데,
Discord는 dedup이 없으면 파서가 고장 난 동안 3일마다 같은 알림이
반복된다. 같은 오류가 연속되면 Discord 전송만 생략되는지,
오류가 해소되면 마커가 지워져 다음 오류는 다시 알리는지 검증한다.
"""
import json

import requests

import check_notices as cn

FAKE_URL = "https://discord.com/api/webhooks/123/SECRET-TOKEN"


class OkResp:
    def raise_for_status(self):
        pass


def test_repeated_error_notifies_discord_once(tmp_path, monkeypatch):
    monkeypatch.setattr(cn, "SEEN_PATH", tmp_path / "seen.json")
    monkeypatch.setattr(cn, "TITLE_PATH", tmp_path / "issue_title.txt")
    monkeypatch.setattr(cn, "BODY_PATH", tmp_path / "issue_body.md")
    monkeypatch.setenv("DISCORD_WEBHOOK", FAKE_URL)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    # 첫 실행이 아니도록 전 게시판 baseline을 심는다(불변 키 형식)
    (tmp_path / "seen.json").write_text(
        json.dumps({cn.board_key(b, m): ["1"] for _, b, m in cn.BOARDS}),
        encoding="utf-8")

    posted = []
    monkeypatch.setattr(cn.requests, "post",
                        lambda url, json=None, timeout=None: (posted.append(json), OkResp())[1])

    def fail(board, menu, count=cn.PAGE_SIZE):
        raise requests.ConnectionError("down")

    def healthy(board, menu, count=cn.PAGE_SIZE):
        return [], 0  # 빈 게시판(전체 0건) — 오류·신규 없음

    # 1·2회차: 같은 수집 실패 → Discord는 1회만
    monkeypatch.setattr(cn, "fetch_board", fail)
    cn.main()
    cn.main()
    assert len(posted) == 1
    assert "수집 실패" in posted[0]["embeds"][0]["title"]

    # 3회차: 정상 실행 → 오류 마커 해제 (알림 없음)
    monkeypatch.setattr(cn, "fetch_board", healthy)
    cn.main()
    assert len(posted) == 1
    assert cn.LAST_ERROR_KEY not in json.loads(
        (tmp_path / "seen.json").read_text(encoding="utf-8"))

    # 4회차: 다시 실패 → 새 오류로 간주해 다시 알림
    monkeypatch.setattr(cn, "fetch_board", fail)
    cn.main()
    assert len(posted) == 2
