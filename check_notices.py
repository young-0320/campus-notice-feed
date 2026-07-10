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
import time
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

# seen.json 안에서 게시판별 "마지막으로 성공한 전체 건수(.bbs-total)"를 담는
# 메타 키. 게시판 표시명과 겹치지 않게 밑줄로 감쌌다. .bbs-total 셀렉터가
# 조용히 깨져 total 파싱만 실패한 경우(rows는 여전히 잡혀 비율 검사가 통째로
# 스킵되던 사각지대)를 이전 실행값과 비교해 감지하는 데 쓴다.
TOTALS_KEY = "__totals__"

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


def parse_board(html):
    """게시판 목록 HTML(바이트 또는 문자열)을 파싱해
    (게시글 리스트, 전체 글 수)를 반환.

    전체 글 수(total)는 사이트가 표시하는 "전체 N 건" 값이다(없으면 None).
    이 값과 실제 추출 수를 비교해 마크업 변경으로 인한 조용한 실패를 감지한다.
    HTTP 없는 순수 함수 — tests/fixtures/ 의 mock HTML로 CI에서 검증한다."""
    soup = BeautifulSoup(html, "html.parser")

    # 두 레이아웃 지원: 표형(BMSR00040 → tbody tr)과 썸네일 카드형
    # (BMSR00044 → ul.bbs-thumb > li). 표가 있으면 표를, 없으면 썸네일을 쓴다.
    # TODO(fragility): 셀렉터가 문서 전역이라 페이지에 무관한 <table>이 하나만
    # 생겨도 썸네일 게시판이 표 분기로 새고(단락평가), 표형에선 무관한 행이
    # 섞인다. 현재는 ID_RE 필터 + 건강검사(급감/총계 경고)가 조용한 유실은
    # 막아 실패 모드가 '오탐 경고'에 그친다. 정공법은 리스트 컨테이너로 셀렉터를
    # 좁히는 것(예: .bbs-list tbody tr)이나, 정확한 래퍼 클래스는 라이브 DOM
    # 확인이 필요하고 지금 추측으로 좁히면 검증된 파싱을 깨뜨릴 위험이 있어 보류.
    # 일반화(사이트 어댑터) 리팩터링 때 사이트별 config로 함께 처리.
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


def fetch_board(board: str, menu: str, count: int = PAGE_SIZE):
    """게시판 목록을 HTTP로 받아 parse_board에 넘긴다. 반환은 parse_board와 동일."""
    params = {
        "menuNo": menu,
        "boardType": "",
        "pageIndex": 1,
        "searchCondition": "",
        "searchKeyword": "",
        "userDisplayCount": count,
    }
    # 일회성 타임아웃/5xx 한 번에 실패 이슈가 나가지 않게 2회까지 재시도
    for attempt in range(3):
        try:
            r = requests.get(LIST_URL.format(board=board), params=params,
                             headers=UA, timeout=20)
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(3)
    # r.text가 아니라 r.content(바이트)를 넘긴다. 서버가 Content-Type에서
    # charset을 빼면 requests는 ISO-8859-1로 폴백해 한글이 전부 깨지는데,
    # 개수만 보는 건강검사는 이를 통과시킨다. bs4는 바이트를 받으면
    # <meta charset>으로 직접 판정하므로 헤더 유무와 무관하게 안전.
    return parse_board(r.content)


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


def md_escape(text) -> str:
    """신뢰 불가 텍스트(게시글 제목·날짜, 예외 메시지)가 이슈 본문에서
    마크다운 링크/코드 구문으로 해석돼 링크 목적지 위조 등에 쓰이지 않게
    \\ [ ] ` 를 이스케이프한다."""
    return re.sub(r"([\\\[\]`])", r"\\\1", str(text))


def write_summary(summary):
    """게시판별 추출 현황을 GITHUB_STEP_SUMMARY(Actions 실행 화면)에 숫자 표로
    남긴다. 신규 0건인 평범한 실행에서도 게시판별 '추출/전체' 수를 볼 수 있어,
    건강검사 임계값(PARSE_RATE_MIN)에 다가가는 추출률 드리프트를 경고가 터지기
    전에 관측할 수 있다. 게시판명(코드 상수)과 숫자만 넣고 게시글 제목 등 신뢰
    불가 텍스트는 넣지 않으므로 인젝션 표면이 없다."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = [
        "## KHU EE 공지 감시 — 실행 요약",
        "",
        "| 게시판 | 추출 | 전체 | 신규 | 상태 |",
        "|---|---:|---:|---:|---|",
    ]
    for s in summary:
        lines.append(f"| {s['name']} | {s['extracted']} | {s['total']} "
                     f"| {s['new']} | {s['status']} |")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    seen = load_seen()
    first_run = not seen
    totals = seen.get(TOTALS_KEY, {})  # 게시판별 지난 성공 실행의 "전체 N 건"
    new_items = []
    errors = []
    summary = []  # 게시판별 추출 현황(관측성) — GITHUB_STEP_SUMMARY로 출력

    for name, board, menu in BOARDS:
        try:
            rows, total = fetch_board(board, menu)
        except Exception as e:  # noqa: BLE001
            errors.append(f"- `{name}` 수집 실패: {md_escape(e)}")
            summary.append({"name": name, "extracted": "—", "total": "—",
                            "new": 0, "status": "❌ 수집 실패"})
            continue

        # 파서 건강검사: 사이트의 "전체 N 건"과 실제 추출 수를 비교해
        # 마크업 변경으로 인한 '조용한 실패'(에러 없이 0건처럼 보임)를 감지.
        prev_total = totals.get(name)
        parse_suspect = False  # 건강검사에 걸림 = 이번 추출본을 신뢰할 수 없음
        if total is not None:
            totals[name] = total  # 성공한 전체 건수 기록(다음 실행의 비교 기준)
            expected = min(total, PAGE_SIZE)
            if expected and len(rows) < expected * PARSE_RATE_MIN:
                parse_suspect = True
                errors.append(f"- `{name}` 추출 수 급감 "
                              f"(전체 {total}건인데 이번 페이지 {len(rows)}건만 파싱 — "
                              f"마크업/셀렉터 변경 의심)")
        elif prev_total:
            # 이전 실행에선 전체 건수가 읽혔는데 이번엔 못 읽음(.bbs-total 셀렉터
            # 깨짐). rows가 잡혀도 비율 검사가 통째로 스킵되던 사각지대를 메운다.
            parse_suspect = True
            errors.append(f"- `{name}` 전체 건수(.bbs-total) 파싱 실패 "
                          f"(지난 실행 {prev_total}건 → 이번엔 미확인, 이번 페이지 "
                          f"{len(rows)}건 — 셀렉터 변경 의심)")
        elif not rows:
            # 전체 건수도 글도 못 잡음. 이 게시판을 성공적으로 읽은 이력이 없어
            # 비교 기준이 없으므로 절대값(0건)으로만 판단한다.
            parse_suspect = True
            errors.append(f"- `{name}` 총계·글 모두 파싱 실패 "
                          f"(마크업 변경 의심 — bbs-total / tbody tr / bbs-thumb 점검)")

        known = set(seen.get(name, []))
        fresh = [r for r in rows if r["id"] not in known]
        board_seen = name in seen  # baseline 갱신 전에 캡처(아래에서 seen[name]을 씀)

        # 이 게시판을 이전 실행에서 본 적이 있을 때만 신규 알림.
        # board_seen=False = 첫 실행이거나 새로 추가된 게시판 → baseline만
        # 저장하고 알림은 보내지 않는다. (전역 first_run 대신 게시판 단위로
        # 판정 — 게시판 추가/부분 실패로 일부만 known이 비었을 때 옛 글이
        # 전부 신규로 터지는 것을 방지.)
        if board_seen:
            for r in fresh:
                r["board"] = name
                r["url"] = VIEW_URL.format(board=board, menu=menu, pid=r["id"])
                new_items.append(r)

        # 최근 200개만 유지. 단, 건강검사에 걸린 게시판의 baseline은 새로
        # 만들지 않는다 — 결함 추출본이 baseline으로 굳으면 파서를 고친
        # 시점에 누락됐던 옛 글이 전부 신규로 오알림된다(log.md의 "파서
        # 깨지면 baseline 저장 안 함" 원칙). 이미 baseline이 있는 게시판은
        # known과의 합집합이라 잃을 게 없으므로 그대로 갱신한다.
        if board_seen or not parse_suspect:
            seen[name] = sorted(known | {r["id"] for r in rows}, key=int, reverse=True)[:200]

        summary.append({"name": name, "extracted": len(rows),
                        "total": total if total is not None else "—",
                        "new": len(fresh) if board_seen else 0,
                        "status": "⚠️ 점검 필요" if parse_suspect else "정상"})

    if totals:  # 성공적으로 읽은 total이 하나라도 있을 때만 기록
        seen[TOTALS_KEY] = totals
    save_seen(seen)
    write_summary(summary)

    if first_run:
        if errors:
            write_output(has_new=True,
                         title="[KHU EE] 첫 실행 — 파서 점검 필요",
                         body="\n".join(errors), is_error=True)
        else:
            print("첫 실행: 기존 글을 baseline으로 저장했습니다. 신규 알림 없음.")
            write_output(has_new=False, title="", body="")
        return

    if errors and not new_items:
        write_output(has_new=True,
                     title="[KHU EE] 공지 수집 실패",
                     body="\n".join(errors), is_error=True)
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
            lines.append(f"- **[{r['board']}]** [{md_escape(r['title'])}]({r['url']}) `{md_escape(r['date'])}`")
        lines.append("")

    rest = [r for r in new_items if r not in hot]
    if rest:
        lines.append("## 그 외 신규 공지\n")
        for r in rest:
            lines.append(f"- [{r['board']}] [{md_escape(r['title'])}]({r['url']}) `{md_escape(r['date'])}`")
        lines.append("")

    if errors:
        lines.append("## ⚠️ 수집 실패\n")
        lines.extend(errors)

    body = "\n".join(lines)
    title = f"[KHU EE] 신규 공지 {len(new_items)}건" + (f" (⭐{len(hot)})" if hot else "")

    print(title)
    print(body)
    write_output(has_new=True, title=title, body=body)


def write_output(has_new: bool, title: str, body: str, is_error: bool = False):
    """불리언 플래그만 GITHUB_OUTPUT으로 내보내고,
    제목/본문은 파일로 쓴다. 워크플로는 fs.readFileSync로 파일을 읽으므로
    신뢰 불가한 게시글 텍스트가 ${{ }} 치환·heredoc 파싱을 전혀 거치지 않는다.
    is_error: 수집 실패 등 제목이 고정인 이슈 — 워크플로가 이 플래그를 보고
    동일 제목의 open 이슈가 있으면 새 이슈 대신 댓글을 단다(중복 방지)."""
    if has_new:
        TITLE_PATH.write_text(title + "\n", encoding="utf-8")
        BODY_PATH.write_text(body + "\n", encoding="utf-8")

    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        f.write(f"has_new={'true' if has_new else 'false'}\n")
        f.write(f"is_error={'true' if is_error else 'false'}\n")


if __name__ == "__main__":
    sys.exit(main())
