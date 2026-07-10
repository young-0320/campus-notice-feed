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

# 제목에 이 단어가 있으면 ⭐ 표시
KEYWORDS = [
    "반도체", "공정", "FAB", "팹", "소자", "실습", "인턴", "탐방",
    "설계", "경진", "챌린지", "공모", "채용", "교육", "수료",
    "종합설계", "졸업", "장학", "IDEC", "삼성", "하이닉스",
]

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


def fetch_board(board: str, menu: str, count: int = 30):
    """게시판 목록에서 (게시글ID, 제목, 등록일) 리스트를 반환."""
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

    rows = []
    for tr in soup.select("tbody tr"):
        raw = str(tr)
        m = ID_RE.search(raw)
        if not m:
            continue
        pid = m.group(1)

        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not cells:
            continue

        # 제목은 링크 텍스트가 가장 안전
        a = tr.find("a")
        title = a.get_text(" ", strip=True) if a else (cells[1] if len(cells) > 1 else "")
        title = re.sub(r"\s+", " ", title).strip()

        # 등록일: yyyy-mm-dd 또는 yyyy.mm.dd 패턴을 셀에서 찾는다
        date = ""
        for c in cells:
            if re.fullmatch(r"\d{4}[-.]\d{2}[-.]\d{2}", c):
                date = c
                break

        rows.append({"id": pid, "title": title, "date": date})
    return rows


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
            rows = fetch_board(board, menu)
        except Exception as e:  # noqa: BLE001
            errors.append(f"- `{name}` 수집 실패: {e}")
            continue

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
