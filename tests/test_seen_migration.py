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


def test_old_key_dropped_when_new_key_exists():
    """새 키가 이미 있으면 새 키의 이력을 유지하고 옛 키(찌꺼기)만 제거."""
    seen = migrate_seen({NAME: ["1"], KEY: ["100"]})
    assert seen[KEY] == ["100"]
    assert NAME not in seen


def test_empty_seen():
    """첫 실행(빈 파일)에서도 안전 — first_run 판정을 깨지 않는다."""
    assert migrate_seen({}) == {}
