"""키워드 매칭·사이트별 필터·교차 게시 병합 테스트."""
import json

import check_notices as cn

SITES = [
    {"name": "전자", "base": "https://a.example/ee", "filter": "all",
     "page_size": 30, "boards": [["공지", "BMSR00040", "1"]]},
    {"name": "기계", "base": "https://b.example/me", "filter": "keywords",
     "page_size": 30, "boards": [["광장", "BMSR00040", "2"]]},
]


def test_ascii_keyword_needs_word_boundary():
    """영문 키워드는 다른 영단어 속에 들어 있으면 매칭하지 않는다."""
    p = cn.keyword_pattern("AI")
    assert p.search("AI 홍보영상 공모전")
    assert p.search("생성형 ai 활용 특강")
    assert p.search("AI융합학부 세미나")        # 한글이 붙는 건 허용
    assert not p.search("Samsung Career Fair")
    assert not p.search("email 주소 변경 안내")


def test_korean_keyword_is_substring():
    """한글 키워드는 부분일치 유지('공모' → '공모전')."""
    assert cn.keyword_pattern("공모").search("제3회 공모전 안내")


def run_main(tmp_path, monkeypatch, boards):
    """boards: {menuNo: rows} 를 돌려주는 가짜 사이트로 main() 실행,
    (이슈 본문, seen) 반환. 두 게시판 모두 baseline("1")이 있는 상태에서 시작."""
    monkeypatch.setattr(cn, "SEEN_PATH", tmp_path / "seen.json")
    monkeypatch.setattr(cn, "TITLE_PATH", tmp_path / "issue_title.txt")
    monkeypatch.setattr(cn, "BODY_PATH", tmp_path / "issue_body.md")
    for env in ("DISCORD_WEBHOOK", "SMTP_USER", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(cn, "load_sites", lambda: SITES)
    monkeypatch.setattr(cn, "KEYWORD_PATTERNS", [cn.keyword_pattern("공모")])
    monkeypatch.setattr(cn, "fetch_board",
                        lambda base, board, menu, count=30: (boards[menu], len(boards[menu])))
    (tmp_path / "seen.json").write_text(
        json.dumps({"BMSR00040:1": ["1"], "BMSR00040:2": ["1"]}), encoding="utf-8")
    cn.main()
    body = (tmp_path / "issue_body.md")
    return (body.read_text(encoding="utf-8") if body.exists() else "",
            json.loads((tmp_path / "seen.json").read_text(encoding="utf-8")))


def row(pid, title, tag=""):
    return {"id": pid, "title": f"{tag} {title}".strip(), "date": "2026-11-20", "tag": tag}


def test_filter_keywords_only_on_that_site(tmp_path, monkeypatch):
    """filter=all 사이트는 전부, filter=keywords 사이트는 키워드 글만 알린다.
    걸러진 글도 seen 에는 기록돼 다음 실행에 다시 나오지 않는다."""
    body, seen = run_main(tmp_path, monkeypatch, {
        "1": [row("10", "수강신청 안내")],
        "2": [row("20", "설계 공모전 안내"), row("21", "주차장 공사 안내")],
    })
    assert "수강신청 안내" in body          # all 사이트: 키워드 없어도 알림
    assert "설계 공모전 안내" in body        # keywords 사이트: 키워드 글
    assert "주차장 공사 안내" not in body    # keywords 사이트: 걸러짐
    assert "21" in seen["BMSR00040:2"]


def test_cross_posts_merged_across_sites(tmp_path, monkeypatch):
    """같은 공지가 두 사이트에 캠퍼스 태그만 달리(공통 ↔ All) 올라오면
    위쪽 사이트의 것 하나만 남기고 '외 N곳'으로 표시한다."""
    body, _ = run_main(tmp_path, monkeypatch, {
        "1": [row("10", "AI 공모전 안내", tag="공통")],
        "2": [row("20", "AI 공모전 안내", tag="All")],
    })
    assert body.count("AI 공모전 안내") == 1
    assert "[전자 공지]" in body and "기계 광장" not in body
    assert "외 1곳" in body
