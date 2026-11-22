# CLAUDE.md

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

# 프로젝트 컨텍스트 (campus-notice-feed)

다음 세션에서 이어서 작업할 수 있도록 남기는 컨텍스트. 상세 결정·근거는
`log.md`에, 사용법은 `README.md`에 있으니 먼저 그 둘을 읽을 것.

## 무엇인가

대학 공지 게시판을 3일마다 크롤링해 신규 글을 GitHub Issue로 알리는
서버리스 봇. GitHub Actions에서만 돈다(서버·비용 없음). **현재는 경희대
국제캠 19개 사이트(전자공학 + 공과대학·생명과학대학) 47개 게시판**을 감시한다.
국제캠 전체 → 서울캠 → 타 학교 순으로 넓히는 게 방향이다.
기능 전체와 확장 절차는 `log.md` 맨 아래 "기능 목록"·"기능 추가 방식".

## 구조 한눈에

- `check_notices.py` — 설정 로드(`load_sites`) → 크롤링(`fetch_board`) →
  신규 판별(`seen.json` 비교) → 필터·교차 게시 병합 → 이슈 본문 생성(`main`)
  → 제목/본문을 **파일로** 출력 + Discord·이메일 전송(`write_output`).
- `sites.toml` — 감시 대상 사이트·게시판·`filter`(코드 밖).
- `sitecheck.py` — `inspect <url>`(새 사이트 형식 검사 + sites.toml 초안),
  `validate`(등록 게시판 라이브 검증). 사이트를 넣거나 파서를 고칠 때 쓴다.
- `.github/workflows/khu-notice.yml` — cron 실행, github-script가 파일을
  읽어 이슈 생성, `seen.json` 커밋.
- `keywords.txt` — ⭐ 하이라이트 겸 필터 키워드(코드 밖). `seen.json` — 상태(봇이 커밋).

## 이미 반영된 설계 결정 (되돌리지 말 것)

1. **이슈 생성은 파일 전달 방식**(`issue_title.txt`/`issue_body.md` →
   `fs.readFileSync`). `GITHUB_OUTPUT`엔 `has_new`만. `${{ }}` 인라인·heredoc
   금지 — 스크립트 인젝션 방지. 워크플로 손댈 때 이 원칙 깨지 말 것.
2. **키워드는 `keywords.txt`**. 지금은 평문(평평한 목록)이 최적. 가중치·
   카테고리·채널 라우팅이 필요해지면 그때 TOML(`tomllib`, 무의존성)로 승급.
3. **두 레이아웃 지원** — `fetch_board`가 표형(`tbody tr`)과 썸네일형
   (`ul.bbs-thumb > li`, 제목 `strong.t`/날짜 `span.date`)을 모두 파싱.
   `BMSR00040`=표, `BMSR00044`=썸네일. 라이브 검증 완료.
4. **파서 건강검사(전체건수 기준)** — `fetch_board`가 `(rows, total)` 반환.
   `total`=사이트의 "전체 N 건"(`.bbs-total`). 기대치 `min(total, PAGE_SIZE)`의
   `PARSE_RATE_MIN`(0.7) 미만만 추출되면 마크업 변경으로 보고 이슈. 전체
   0건(빈 게시판)은 검사 생략 → 오탐 없음. (candidates 방식에서 교체됨.)
5. **seen.json 키는 불변값(`boardId:menuNo`)** — `board_key()`로 생성.
   구버전(표시명 키) 파일은 `migrate_seen()`이 런타임에 멱등 이관.
   레포의 seen.json을 직접 고치지 말 것(봇 커밋과 충돌).
6. **Discord 알림은 선택 기능** — `DISCORD_WEBHOOK` Secret → env로만 주입,
   `requests.post(json=...)` 전송, 실패는 삼키고 예외 타입+상태코드만 출력
   (URL이 예외 메시지에 포함되므로 예외 본문 출력 금지).

7. **감시 대상은 `sites.toml`** — 사이트 추가는 설정만으로. seen.json 키는
   사이트를 포함하지 않는 `boardId:menuNo` 그대로다(menuNo 대역이 사이트마다
   달라 충돌 없음 — `load_sites` 가 중복을 검사한다). 키 형식을 바꾸지 말 것.
8. **필터는 사이트별 `filter`**(`all` 기본 / `keywords`). 키워드 목록은
   `keywords.txt` 하나를 ⭐ 과 필터가 같이 쓴다. 영문 키워드는 단어 경계,
   한글은 부분일치.
9. **메일은 GitHub 이슈 알림이 기본**(받는 사람이 레포를 Watch). Gmail SMTP
   발송(`notify_email`, Secret `SMTP_USER`/`SMTP_PASSWORD`/`MAIL_TO`)은 선택
   기능으로만 남겨 둔다. 수신자 주소는 레포에 두지 않는다.
10. **교차 게시 병합은 실행 내·제목 완전일치**(캠퍼스 태그만 뗀다). 합쳐진
    글은 버리지 않고 `같은 제목: [사이트](URL)` 링크로 남긴다 — 건수만 남기는
    방식으로 되돌리지 말 것(제목만 같은 다른 글을 놓치게 된다).
11. **이슈 제목은 접두사 없이** `새 공지 N건 (⭐k) — 단과대 n · …`. 메일
    제목으로 쓰이므로 `[KHU]` 같은 대괄호 접두사를 다시 붙이지 말 것. 출처는
    `[단과대 · 학과 · 게시판]`(`sites.toml` 의 `college`).
12. **접속 불가 사이트는 그 실행에서 건너뛴다**(ConnectionError/Timeout 만.
    HTTP 오류는 게시판 단위). 이슈 본문은 `ISSUE_BODY_MAX` 에서 자른다.
13. **알림 테스트는 워크플로 수동 실행의 `test_notify`**(`TEST_NOTIFY=true`).
    최근 7일 글을 신규로 간주해 `(테스트)` 이슈·Discord·Gmail 을 보내고
    seen.json 은 저장하지 않는다. 받는 사람 주소·비밀번호는 Secret 에만 —
    레포 파일·커밋·이슈에 적지 말 것.

## 다음 후보 (우선순위 순, 상세는 log.md "미해결")

1. 국제캠 나머지 사이트 등록 — 검사 결과는 log.md 9번 표. 게시판 선별과
   `filter` 값은 사용자에게 확인. 그다음 서울캠(미조사).
2. 한글 키워드 부분일치 오탐, 교차 게시 병합의 유사 제목 처리.
3. 알림 채널 추가(Telegram 등) — 자격 증명은 반드시 Actions Secrets로.
4. 다른 CMS 사이트(서울캠 일부 추정) — 절차는 log.md "다른 CMS 추가".

## 작업 규칙

- **커밋 저자는 Young 단독**(git config에 설정됨). Claude 공동저자 트레일러
  붙이지 말 것.
- **push는 사용자 확인 후에만.** 현재 로컬 커밋이 origin보다 앞서 있을 수 있음.
- 테스트: `python -m pytest`(네트워크 불필요, fixtures mock HTML).
- 실사이트 확인: `python sitecheck.py validate`. 클라우드 세션에서는 개인
  환경 `campus-notice-feed` 가 조사한 khu.ac.kr 호스트 40곳을 허용한다
  (Default 환경은 차단). 새 호스트는 그 환경의 허용 목록에 추가해야 한다.
