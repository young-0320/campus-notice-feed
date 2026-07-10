#!/usr/bin/env python3
"""
경희대 전자공학과(ee.khu.ac.kr) 공지 게시판 신규 글 감시.

- 5개 게시판을 순회하며 게시글 고유 ID를 수집
- seen.json에 없는 ID = 신규 글
- 신규 글이 있으면 GitHub Issue 본문용 마크다운을 만들어 stdout + $GITHUB_OUTPUT 으로 내보냄
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://ee.khu.ac.kr"

# (표시명, boardId, menuNo)
BOARDS = [
    ("소식",            "BMSR00044", "21700021"),
    ("학사/장학",        "BMSR00040", "21700019"),
    ("취업정보/대외활동", "BMSR00040", "21700020"),
    ("행사",            "BMSR00044", "21700046"),
    ("기타공지",         "BMSR00040", "21700022"),
]

# 제목에 이 단어가 있으면 ⭐ 표시.
# keywords.txt(스크립트와 같은 폴더)가 있으면 그 파일을 우선 사용한다.
# 파일이 없거나 비어 있으면 아래 기본값으로 폴백한다.
KEYWORDS_PATH = Path(__file__).with_name("keywords.txt")

DEFAULT_KEYWORDS = [
    "반도체", "공정", "FAB", "팹", "소자", "실습", "인턴", "탐방",
    "설계", "경진", "챌린지", "공모", "채용", "교육", "수료",
    "종합설계", "졸업", "장학", "IDEC", "삼성", "하이닉스",
]


def load_keywords():
    """keywords.txt 를 읽어 키워드 리스트를 만든다.
    - 한 줄에 키워드 하나
    - '#' 로 시작하는 줄과 빈 줄은 무시
    파일이 없거나 유효 키워드가 하나도 없으면 DEFAULT_KEYWORDS 반환."""
    if KEYWORDS_PATH.exists():
        words = []
        for line in KEYWORDS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            words.append(line)
        if words:
            return words
    return DEFAULT_KEYWORDS


KEYWORDS = load_keywords()

LIST_URL = BASE + "/ee25/user/bbs/{board}/list.do"
VIEW_URL = BASE + "/ee25/user/bbs/{board}/view.do?menuNo={menu}&boardId={pid}"

SEEN_PATH = Path(__file__).with_name("seen.json")

# 이슈 제목/본문은 GITHUB_OUTPUT(heredoc)이나 ${{ }} 치환을 거치지 않고
# 파일로 넘긴다. 게시글 텍스트가 신뢰 불가 입력이라 스크립트 인젝션을 막기 위함.
TITLE_PATH = Path(__file__).with_name("issue_title.txt")
BODY_PATH = Path(__file__).with_name("issue_body.md")

UA = {"User-Agent": "Mozilla/5.0 (khu-notice-watcher)"}

# onclick / href 어디에 있든 view('123456') 형태의 ID를 뽑는다
ID_RE = re.compile(r"view\s*\(\s*['\"](\d{4,})['\"]")

# 기대 추출 수(전체 N 건과 페이지 크기 중 작은 값)의 이 비율 미만만
# 실제로 추출되면 마크업 변경으로 간주한다
PARSE_RATE_MIN = 0.7

# list.do 에 요청하는 페이지당 글 수(userDisplayCount)
PAGE_SIZE = 30


def fetch_board(board: str, menu: str, count: int = PAGE_SIZE):
    """게시판 목록을 파싱해 (게시글 리스트, 전체 글 수)를 반환.

    전체 글 수(total)는 사이트가 표시하는 "전체 N 건" 값이다(없으면 None).
    이 값과 실제 추출 수를 비교해 마크업 변경으로 인한 조용한 실패를 감지한다."""
    params = {
        "menuNo": menu,
        "boardType": "",
        "pageIndex": 1,
        "searchCondition": "",
        "searchKeyword": "",
        "userDisplayCount": count,
    }
    r = requests.get(LIST_URL.format(board=board), params=params,
                     headers=UA, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # 두 레이아웃 지원: 표형(BMSR00040 → tbody tr)과 썸네일 카드형
    # (BMSR00044 → ul.bbs-thumb > li). 표가 있으면 표를, 없으면 썸네일을 쓴다.
    row_els = soup.select("tbody tr") or soup.select("ul.bbs-thumb > li")

    rows = []
    for el in row_els:
        m = ID_RE.search(str(el))
        if not m:
            continue
        pid = m.group(1)

        if el.name == "tr":
            cells = [td.get_text(" ", strip=True) for td in el.find_all("td")]
            a = el.find("a")
            title = a.get_text(" ", strip=True) if a else (cells[1] if len(cells) > 1 else "")
            # 등록일: 셀 중 날짜 형태(yyyy-mm-dd / yyyy.mm.dd)를 찾는다
            date = next((c for c in cells
                         if re.fullmatch(r"\d{4}[-.]\d{2}[-.]\d{2}", c)), "")
        else:
            # 썸네일 카드: 제목 strong.t, 날짜 span.date
            head = el.select_one("strong.t") or el.find("a")
            title = head.get_text(" ", strip=True) if head else ""
            d = el.select_one("span.date")
            date = d.get_text(strip=True) if d else ""

        title = re.sub(r"\s+", " ", title).strip()
        rows.append({"id": pid, "title": title, "date": date})

    # 사이트가 알려주는 전체 글 수("전체 N 건") — 건강검사의 기준값.
    # 빈 게시판(0건)과 파서 고장(글 있는데 0건 추출)을 구분하는 데 쓴다.
    total = None
    tot_el = soup.select_one(".bbs-total")
    if tot_el:
        mt = re.search(r"([\d,]+)\s*건", tot_el.get_text(" ", strip=True))
        if mt:
            total = int(mt.group(1).replace(",", ""))

    return rows, total


def load_seen():
    if SEEN_PATH.exists():
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    return {}


def save_seen(seen):
    SEEN_PATH.write_text(
        json.dumps(seen, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def is_hot(title: str) -> bool:
    return any(k.lower() in title.lower() for k in KEYWORDS)


def main():
    seen = load_seen()
    first_run = not seen
    new_items = []
    errors = []

    for name, board, menu in BOARDS:
        try:
            rows, total = fetch_board(board, menu)
        except Exception as e:  # noqa: BLE001
            errors.append(f"- `{name}` 수집 실패: {e}")
            continue

        # 파서 건강검사: 사이트의 "전체 N 건"과 실제 추출 수를 비교해
        # 마크업 변경으로 인한 '조용한 실패'(에러 없이 0건처럼 보임)를 감지.
        expected = min(total, PAGE_SIZE) if total is not None else None
        if expected:  # 0(빈 게시판)·None(총계 미확인)이면 비율 검사 생략
            if len(rows) < expected * PARSE_RATE_MIN:
                errors.append(f"- `{name}` 추출 수 급감 "
                              f"(전체 {total}건인데 이번 페이지 {len(rows)}건만 파싱 — "
                              f"마크업/셀렉터 변경 의심)")
        elif total is None and not rows:
            errors.append(f"- `{name}` 총계·글 모두 파싱 실패 "
                          f"(마크업 변경 의심 — bbs-total / tbody tr / bbs-thumb 점검)")

        known = set(seen.get(name, []))
        fresh = [r for r in rows if r["id"] not in known]

        if not first_run:
            for r in fresh:
                r["board"] = name
                r["url"] = VIEW_URL.format(board=board, menu=menu, pid=r["id"])
                new_items.append(r)

        # 최근 200개만 유지
        seen[name] = sorted(known | {r["id"] for r in rows}, reverse=True)[:200]

    save_seen(seen)

    if first_run:
        if errors:
            write_output(has_new=True,
                         title="[KHU EE] 첫 실행 — 파서 점검 필요",
                         body="\n".join(errors))
        else:
            print("첫 실행: 기존 글을 baseline으로 저장했습니다. 신규 알림 없음.")
            write_output(has_new=False, title="", body="")
        return

    if errors and not new_items:
        write_output(has_new=True,
                     title="[KHU EE] 공지 수집 실패",
                     body="\n".join(errors))
        return

    if not new_items:
        print("신규 공지 없음.")
        write_output(has_new=False, title="", body="")
        return

    hot = [r for r in new_items if is_hot(r["title"])]

    lines = []
    if hot:
        lines.append("## ⭐ 관심 키워드 매칭\n")
        for r in hot:
            lines.append(f"- **[{r['board']}]** [{r['title']}]({r['url']}) `{r['date']}`")
        lines.append("")

    rest = [r for r in new_items if r not in hot]
    if rest:
        lines.append("## 그 외 신규 공지\n")
        for r in rest:
            lines.append(f"- [{r['board']}] [{r['title']}]({r['url']}) `{r['date']}`")
        lines.append("")

    if errors:
        lines.append("## ⚠️ 수집 실패\n")
        lines.extend(errors)

    body = "\n".join(lines)
    title = f"[KHU EE] 신규 공지 {len(new_items)}건" + (f" (⭐{len(hot)})" if hot else "")

    print(title)
    print(body)
    write_output(has_new=True, title=title, body=body)


def write_output(has_new: bool, title: str, body: str):
    """신규 여부(불리언)만 GITHUB_OUTPUT으로 내보내고,
    제목/본문은 파일로 쓴다. 워크플로는 fs.readFileSync로 파일을 읽으므로
    신뢰 불가한 게시글 텍스트가 ${{ }} 치환·heredoc 파싱을 전혀 거치지 않는다."""
    if has_new:
        TITLE_PATH.write_text(title + "\n", encoding="utf-8")
        BODY_PATH.write_text(body + "\n", encoding="utf-8")

    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        f.write(f"has_new={'true' if has_new else 'false'}\n")


if __name__ == "__main__":
    sys.exit(main())
