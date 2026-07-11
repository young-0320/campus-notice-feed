"""migrate_seen 회귀 테스트.

seen.json 키가 표시명이던 구버전 파일이 불변 키(boardId:menuNo)로
이관되는지, 이관 후 재실행이 no-op인지 검증한다.
"""
from check_notices import BOARDS, TOTALS_KEY, board_key, migrate_seen

# BOARDS의 첫 항목을 그대로 사용해 코드 상수와 어긋나지 않게 한다
NAME, BOARD, MENU = BOARDS[0]
KEY = board_key(BOARD, MENU)


def test_migrates_old_name_keys():
    """표시명 키 → 불변 키로 이동, 값(알림 이력)은 보존, 옛 키는 제거."""
    old = {NAME: ["100", "99"], TOTALS_KEY: {NAME: 42}}
    seen = migrate_seen(old)
    assert seen[KEY] == ["100", "99"]
    assert NAME not in seen
    assert seen[TOTALS_KEY] == {KEY: 42}


def test_new_format_is_noop():
    """이미 불변 키인 파일은 그대로 통과(이관 멱등성)."""
    cur = {KEY: ["100"], TOTALS_KEY: {KEY: 42}}
    assert migrate_seen(dict(cur)) == cur


def test_conflict_merges_history():
    """두 형식 공존(이관 후 revert→재이관): 어느 쪽 이력도 버리지 않고
    합집합으로 병합 — 버리면 그 기간에 알림된 글이 known에서 빠져
    중복 알림이 난다. totals는 최신값(새 키) 유지."""
    seen = migrate_seen({NAME: ["1", "50"], KEY: ["100", "50"],
                         TOTALS_KEY: {NAME: 10, KEY: 42}})
    assert seen[KEY] == ["100", "50", "1"]  # 합집합, int 내림차순
    assert NAME not in seen
    assert seen[TOTALS_KEY] == {KEY: 42}


def test_empty_seen():
    """첫 실행(빈 파일)에서도 안전 — first_run 판정을 깨지 않는다."""
    assert migrate_seen({}) == {}
