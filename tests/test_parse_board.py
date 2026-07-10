"""parse_board 회귀 테스트.

fixtures/ 의 mock HTML은 라이브 사이트(ee.khu.ac.kr)에서 검증된 마크업
구조를 본뜬 것. 실제 운영과 동일하게 바이트로 읽어 넘긴다(fetch_board가
r.content를 넘기는 것과 같은 경로).
"""
from pathlib import Path

from check_notices import PAGE_SIZE, PARSE_RATE_MIN, parse_board

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_table_layout():
    """표형(BMSR00040): tbody tr에서 id/제목/등록일을 추출, thead는 제외."""
    rows, total = parse_board(load("table.html"))
    assert total == 3
    assert [r["id"] for r in rows] == ["123458", "123457", "123456"]
    assert rows[0]["title"] == "2026-2학기 국가장학금 신청 안내"
    assert rows[0]["date"] == "2026-07-03"
    assert all(r["id"] and r["title"] and r["date"] for r in rows)


def test_thumb_layout():
    """썸네일형(BMSR00044): ul.bbs-thumb > li에서 strong.t/span.date를 추출."""
    rows, total = parse_board(load("thumb.html"))
    assert total == 2
    assert [r["id"] for r in rows] == ["99002", "99001"]
    assert rows[0]["title"] == "반도체 공정 실습생 모집"
    assert rows[0]["date"] == "2026.07.05"


def test_empty_board_skips_health_check():
    """빈 게시판: '게시물이 없습니다' 행은 글로 세지 않고, 전체 0건이므로
    건강검사(비율 검사)가 생략되는 조건이어야 한다 → 오탐 경고 없음."""
    rows, total = parse_board(load("empty.html"))
    assert rows == []
    assert total == 0
    # main()의 검사 생략 조건과 동일한 식: expected가 0(falsy)이면 검사 안 함
    assert not min(total, PAGE_SIZE)


def test_broken_selector_triggers_health_check():
    """셀렉터 깨짐(onclick이 view()가 아니게 변경): 사이트는 전체 152건이라
    말하는데 추출은 0건 → main()의 급감 판정 조건에 걸려야 한다."""
    rows, total = parse_board(load("broken.html"))
    assert total == 152
    # main()의 급감 판정과 동일한 식
    expected = min(total, PAGE_SIZE)
    assert len(rows) < expected * PARSE_RATE_MIN
