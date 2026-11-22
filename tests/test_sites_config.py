"""sites.toml 로딩 테스트.

레포의 실제 sites.toml 이 읽히는지(웹에서 잘못 편집하면 CI가 잡는다)와,
잘못된 설정이 조용히 넘어가지 않고 예외로 드러나는지 검증한다.
"""
import pytest

from check_notices import PAGE_SIZE, load_sites

SITE = '''
[[site]]
name = "가"
base = "https://a.example/x"
{extra}
boards = [["공지", "BMSR00040", "1"]]
'''


def write(tmp_path, text):
    p = tmp_path / "sites.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_repo_config_loads():
    sites = load_sites()
    assert sites and all(s["boards"] for s in sites)
    assert all(s["filter"] in ("all", "keywords") for s in sites)
    assert all(len(b) == 3 for s in sites for b in s["boards"])


def test_defaults(tmp_path):
    """filter·page_size 를 생략하면 all / PAGE_SIZE."""
    (site,) = load_sites(write(tmp_path, SITE.format(extra="")))
    assert site["filter"] == "all"
    assert site["page_size"] == PAGE_SIZE


def test_rejects_unknown_filter(tmp_path):
    with pytest.raises(ValueError, match="filter"):
        load_sites(write(tmp_path, SITE.format(extra='filter = "keyword"')))


def test_rejects_duplicate_board_key(tmp_path):
    """seen.json 키(boardId:menuNo)가 겹치면 두 게시판의 이력이 섞인다."""
    twice = SITE.format(extra="") + SITE.format(extra="")
    with pytest.raises(ValueError, match="중복"):
        load_sites(write(tmp_path, twice))
