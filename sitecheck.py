#!/usr/bin/env python3
"""
사이트 형식 검사기 + 등록 사이트 검증기.

  python sitecheck.py inspect https://eng.khu.ac.kr
      새 사이트를 sites.toml 에 넣기 전에 쓴다. 홈페이지에서 게시판 링크를
      찾아 하나씩 받아 보고, 지금 파서로 읽히는지 판정한 뒤 sites.toml 에
      붙여 넣을 초안을 출력한다. 게시판 링크가 하나도 없으면 다른 CMS다
      (파서를 새로 써야 한다는 뜻).

  python sitecheck.py validate [사이트명 ...]
      sites.toml 에 이미 등록된 게시판을 실제로 받아 보고 제대로 읽히는지
      확인한다. 사이트명을 주면 그 사이트만. seen.json 을 건드리지 않고
      알림도 보내지 않으므로 언제든 돌려도 된다.

두 명령 모두 판정은 diagnose() 하나로 한다. 종료 코드: validate 는 FAIL 이
하나라도 있으면 1, inspect 는 쓸 수 있는(OK) 게시판이 하나도 없으면 1.
"""

import argparse
import re
import sys
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

import check_notices as cn

# 게시판 목록 주소: <base>/user/bbs/<boardId>/list.do?...menuNo=<menuNo>
BBS_RE = re.compile(
    r"^(https?://[^/]+/[^/]+)/user/bbs/(BMSR\d+)/list\.do\?.*?\bmenuNo=(\d+)")

DATE_RE = re.compile(r"\d{4}[-.]\d{2}[-.]\d{2}")

OK, WARN, FAIL = "OK", "WARN", "FAIL"


def discover_boards(html, page_url):
    """홈페이지 HTML에서 같은 호스트의 게시판 링크를 찾아
    [(표시명, base, boardId, menuNo)] 로 반환한다(등장 순서, 중복 제거).
    다른 호스트로 나가는 링크(본부 공지 바로가기 등)는 그 사이트의 게시판이
    아니므로 뺀다."""
    soup = BeautifulSoup(html, "html.parser")
    host = urlsplit(page_url).hostname
    found = {}
    for a in soup.find_all("a", href=True):
        m = BBS_RE.match(urljoin(page_url, a["href"]))
        if not m or urlsplit(m.group(1)).hostname != host:
            continue
        name = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        if re.search(r"(더보기|more|바로가기)$", name, re.I):
            name = ""  # 본문의 '더보기' 링크는 게시판 이름이 아니다
        key = m.groups()
        # 같은 주소가 상위 메뉴(대학생활 > 커뮤니티 > 공지사항)에도 걸려 있으므로
        # 가장 나중에 나온(가장 구체적인) 이름을 쓴다. 이름 없는 링크는 무시.
        if name or key not in found:
            found[key] = name
    return [(name or "(이름 없음)", *key) for key, name in found.items()]


def diagnose(rows, total, page_size=cn.PAGE_SIZE):
    """parse_board 결과를 (등급, 설명)으로 판정한다.

    추출 수 판정은 check_notices.main() 의 건강검사와 같은 식
    (기대치 min(total, page_size) 의 PARSE_RATE_MIN 미만이면 실패)이다.
    여기에 main() 이 보지 않는 필드 검사를 더한다 — 개수는 맞는데 제목이
    비거나 날짜가 없는 '그럴듯하게 틀린' 추출을 잡기 위해서다."""
    if total is None:
        if not rows:
            return FAIL, "총계·글 모두 못 읽음 — 지원하지 않는 레이아웃"
        return WARN, (f"{len(rows)}건 추출했지만 전체 건수(.bbs-total)를 못 읽음 "
                      f"— 이 게시판은 건강검사가 동작하지 않는다")
    if total == 0:
        return OK, "빈 게시판(전체 0건)"
    expected = min(total, page_size)
    if len(rows) < expected * cn.PARSE_RATE_MIN:
        if not rows:
            return FAIL, f"전체 {total}건인데 0건 추출 — 지원하지 않는 레이아웃"
        return FAIL, (f"전체 {total}건인데 {len(rows)}건만 추출(기대 {expected}건) — "
                      f"사이트가 {page_size}건 요청을 무시하는 것이면 sites.toml 에 "
                      f"page_size = {len(rows)}, 아니면 파서 수정 필요")
    untitled = sum(not r["title"] for r in rows)
    if untitled:
        # 한두 건이면 사이트 쪽 데이터(제목 없이 올린 글)일 수 있어 경고만,
        # 건강검사 임계와 같은 비율을 넘으면 제목 셀렉터가 깨진 것으로 본다.
        grade = FAIL if untitled > len(rows) * (1 - cn.PARSE_RATE_MIN) else WARN
        return grade, f"제목이 빈 글 {untitled}/{len(rows)}건 — 제목 셀렉터 점검"
    undated = sum(not DATE_RE.fullmatch(r["date"]) for r in rows)
    if undated == len(rows):
        return WARN, (f"{len(rows)}건 추출했지만 날짜가 전부 없음 — "
                      f"공지형 게시판이 아닐 수 있다(연구실·동아리 목록 등)")
    if undated:
        return WARN, f"{len(rows)}건 중 {undated}건 날짜 없음"
    return OK, f"{len(rows)}건 추출 / 전체 {total}건"


def check_board(base, board, menu, page_size=cn.PAGE_SIZE):
    """게시판 하나를 실제로 받아 (등급, 설명, rows) 로 반환."""
    try:
        rows, total = cn.fetch_board(base, board, menu, page_size)
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        what = f"{type(e).__name__} {status}" if status else type(e).__name__
        return FAIL, f"수집 실패({what})", []
    grade, detail = diagnose(rows, total, page_size)
    return grade, detail, rows


def sample(rows):
    """판정 옆에 보여 줄 가장 최근 글 한 건(상단 고정 글이 맨 위라 날짜로 고른다)."""
    if not rows:
        return ""
    r = max(rows, key=lambda r: r["date"])
    return f"   예: {r['date']} {r['title'][:50]}"


def inspect(url):
    try:
        r = requests.get(url, headers=cn.UA, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"홈페이지를 받지 못했다({type(e).__name__}): {url}")
        return 1
    boards = discover_boards(r.content, r.url)
    print(f"홈: {r.url}")
    if not boards:
        print("게시판 링크(/user/bbs/BMSR…/list.do)를 찾지 못했다.")
        if "/user/" in urlsplit(r.url).path:
            # 주소 체계는 같은 CMS — 게시판 없이 학과 사이트로 연결만 하는
            # 단과대 포털(예: eni.khu.ac.kr)이 이렇다.
            print("→ 같은 CMS지만 이 홈페이지에는 게시판이 없다. 소속 학과 "
                  "사이트를 각각 검사할 것.")
            return 1
        print("→ 이 사이트는 지금 파서가 다루는 CMS가 아니다. 감시하려면 이 "
              "사이트용 파서를 따로 써야 한다(log.md '다른 CMS 추가').\n"
              "  홈페이지에 있는 게시판으로 보이는 링크:")
        soup = BeautifulSoup(r.content, "html.parser")
        hints = {urljoin(r.url, a["href"]) for a in soup.find_all("a", href=True)
                 if re.search(r"notice|board|bbs", a["href"], re.I)}
        for h in sorted(hints)[:10] or ["(없음)"]:
            print(f"    {h}")
        return 1

    print(f"게시판 {len(boards)}개 발견\n")
    results = []
    for name, base, board, menu in boards:
        grade, detail, rows = check_board(base, board, menu)
        results.append((grade, detail, name, base, board, menu))
        print(f"[{grade:4}] {name} ({board}, menuNo={menu}) — {detail}{sample(rows)}")

    # sites.toml 초안. base 가 여럿이면(다른 사이트코드의 게시판을 빌려 쓰는
    # 경우) base 별로 블록을 나눈다.
    print("\n# ── sites.toml 초안 ── 공지 성격이 아닌 게시판(교육과정·자료실·FAQ 등)은 "
          "지우고 붙여 넣는다")
    for base in dict.fromkeys(b for _, _, _, b, _, _ in results):
        print(f'\n[[site]]\nname = "{urlsplit(base).hostname}"   # ← 표시할 이름으로 바꾼다'
              f'\ncollege = "단과대 이름"   # ← 소속 단과대'
              f'\nbase = "{base}"\nfilter = "all"\nboards = [')
        for grade, detail, name, b, board, menu in results:
            if b != base:
                continue
            line = f'["{name}", "{board}", "{menu}"],'
            print(f"  {line}" if grade == OK else f"  # {line}  # {grade}: {detail}")
        print("]")
    # 교수소개·갤러리 같은 비공지 게시판은 어느 사이트에나 있고 FAIL 이 정상이다.
    # 쓸 수 있는 게시판이 하나도 없을 때만 실패로 본다.
    return 0 if any(g == OK for g, *_ in results) else 1


def validate(names):
    sites = cn.load_sites()
    unknown = set(names) - {s["name"] for s in sites}
    if unknown:
        print(f"sites.toml 에 없는 사이트: {', '.join(sorted(unknown))}")
        return 1
    counts = {OK: 0, WARN: 0, FAIL: 0}
    for site in sites:
        if names and site["name"] not in names:
            continue
        print(f"\n{site['name']}  ({site['base']}, filter={site['filter']})")
        for name, board, menu in site["boards"]:
            grade, detail, rows = check_board(site["base"], board, menu,
                                              site["page_size"])
            counts[grade] += 1
            print(f"  [{grade:4}] {name} — {detail}{sample(rows)}")
    print(f"\n결과: OK {counts[OK]} · WARN {counts[WARN]} · FAIL {counts[FAIL]}")
    return 1 if counts[FAIL] else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="사이트 형식 검사기 / 등록 사이트 검증기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect", help="새 사이트의 형식을 검사하고 sites.toml 초안을 출력")
    p.add_argument("url", help="홈페이지 주소 (예: https://eng.khu.ac.kr)")
    p = sub.add_parser("validate", help="sites.toml 에 등록된 게시판을 라이브로 검증")
    p.add_argument("names", nargs="*", help="검증할 사이트명(생략하면 전부)")
    args = ap.parse_args(argv)
    return inspect(args.url) if args.cmd == "inspect" else validate(args.names)


if __name__ == "__main__":
    sys.exit(main())
