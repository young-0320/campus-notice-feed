"""sitecheck(형식 검사기·검증기) 테스트 — 네트워크 없이 fixtures 와 mock 으로."""
from pathlib import Path

import requests

import check_notices as cn
import sitecheck
from sitecheck import FAIL, OK, WARN, diagnose, discover_boards

FIXTURES = Path(__file__).parent / "fixtures"

HOME = """
<a href="/eng_kor/user/bbs/BMSR00040/list.do?menuNo=17100020">커뮤니티</a>
<a href="/eng_kor/user/bbs/BMSR00040/list.do?menuNo=17100020">공대마당</a>
<a href="/eng_kor/user/bbs/BMSR00040/list.do?menuNo=17100020"><img src="x.png"></a>
<a href="/eng_kor/user/bbs/BMSR00040/list.do?menuNo=17100020">더보기</a>
<a href="https://eng.khu.ac.kr/eng_kor/user/bbs/BMSR00059/list.do?menuNo=17100027&amp;x=1">연구실</a>
<a href="https://www.khu.ac.kr/kor/user/bbs/BMSR00040/list.do?menuNo=200316">본부 공지</a>
<a href="/eng_kor/user/contents/view.do?menuNo=17100001">학장 인사말</a>
"""


def parsed(name):
    return cn.parse_board((FIXTURES / name).read_bytes())


def test_discover_boards():
    """같은 호스트의 게시판만, 중복 없이, 가장 구체적인 이름으로
    (이름 없는 링크·'더보기' 링크는 이름으로 쓰지 않는다)."""
    boards = discover_boards(HOME, "https://eng.khu.ac.kr/eng_kor/user/main/view.do")
    assert boards == [
        ("공대마당", "https://eng.khu.ac.kr/eng_kor", "BMSR00040", "17100020"),
        ("연구실", "https://eng.khu.ac.kr/eng_kor", "BMSR00059", "17100027"),
    ]


def test_discover_boards_other_cms():
    """이 CMS의 게시판 링크가 없는 사이트는 빈 목록."""
    assert discover_boards('<a href="/02/01_01.php">공지</a>', "http://x.example/") == []


def test_diagnose_supported_layouts():
    assert diagnose(*parsed("table.html"))[0] == OK
    assert diagnose(*parsed("thumb.html"))[0] == OK
    assert diagnose(*parsed("table_tagged.html"))[0] == OK


def test_diagnose_empty_board_is_ok():
    grade, detail = diagnose(*parsed("empty.html"))
    assert grade == OK and "빈 게시판" in detail


def test_diagnose_unsupported_layout():
    """전체 152건인데 0건 추출 → FAIL."""
    assert diagnose(*parsed("broken.html"))[0] == FAIL
    assert diagnose([], None)[0] == FAIL


def test_diagnose_page_size_hint():
    """사이트가 30건 요청을 무시하고 10건만 주면 page_size 를 제안하고,
    그 값으로 맞추면 통과한다."""
    rows = [{"id": str(i), "title": "글", "date": "2026-11-20", "tag": ""} for i in range(10)]
    grade, detail = diagnose(rows, 17567)
    assert grade == FAIL and "page_size = 10" in detail
    assert diagnose(rows, 17567, page_size=10)[0] == OK


def test_diagnose_field_checks():
    """개수는 맞아도 제목이 대부분 비면 FAIL(한두 건이면 WARN),
    날짜가 전부 없으면 WARN."""
    ok = {"id": "2", "title": "글", "date": "2026-11-20", "tag": ""}
    rows = [{"id": "1", "title": "", "date": "2026-11-20", "tag": ""}]
    assert diagnose(rows, 1)[0] == FAIL
    assert diagnose(rows + [ok] * 9, 10)[0] == WARN
    rows = [{"id": "1", "title": "연구실", "date": "", "tag": ""}]
    assert diagnose(rows, 1)[0] == WARN
    assert diagnose(rows, None)[0] == WARN


def test_validate_exit_code(monkeypatch, capsys):
    """모든 게시판이 읽히면 0, 하나라도 FAIL 이면 1. 수집 실패도 FAIL."""
    sites = [{"name": "가", "base": "https://a.example/x", "filter": "all",
              "page_size": 30, "boards": [["공지", "BMSR00040", "1"]]}]
    monkeypatch.setattr(cn, "load_sites", lambda: sites)

    monkeypatch.setattr(cn, "fetch_board", lambda *a: parsed("table.html"))
    assert sitecheck.main(["validate"]) == 0

    monkeypatch.setattr(cn, "fetch_board", lambda *a: parsed("broken.html"))
    assert sitecheck.main(["validate"]) == 1

    def down(*a):
        raise requests.ConnectionError("https://a.example/x 접속 불가")
    monkeypatch.setattr(cn, "fetch_board", down)
    assert sitecheck.main(["validate", "가"]) == 1
    assert "ConnectionError" in capsys.readouterr().out

    assert sitecheck.main(["validate", "없는사이트"]) == 1
