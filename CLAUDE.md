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
전자공학과(ee.khu.ac.kr) 5개 게시판 전용**이지만, 레포명(`campus-notice-feed`)
그대로 **타 학과/학교로 일반화하는 게 최종 방향**이다.

## 구조 한눈에

- `check_notices.py` — 크롤링(`fetch_board`) → 신규 판별(`seen.json` 비교)
  → 이슈 본문 생성(`main`) → 제목/본문을 **파일로** 출력(`write_output`).
- `.github/workflows/khu-notice.yml` — cron 실행, github-script가 파일을
  읽어 이슈 생성, `seen.json` 커밋.
- `keywords.txt` — ⭐ 하이라이트 키워드(코드 밖). `seen.json` — 상태(봇이 커밋).

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

## 다음 후보 (우선순위 순, 상세는 log.md "미해결")

1. **`seen.json` 키를 표시명 → 불변값(boardId+menuNo)으로 교체.** 지금은
   게시판 이름만 바꿔도 `known`이 비어 그 게시판 전체가 신규로 폭발하는 버그.
   (`menuNo`가 목록을 분리하는지는 라이브로 검증 완료 — 겹침 0, 중복 알림 없음.)
2. `is_hot` 부분일치 오탐 개선(단어 경계).
3. 알림 채널 다변화(Discord/Telegram 등) — Webhook은 반드시 Actions Secrets로.
4. (일반화 단계) 게시판/학교 설정을 config로 분리.

## 작업 규칙

- **커밋 저자는 Young 단독**(git config에 설정됨). Claude 공동저자 트레일러
  붙이지 말 것.
- **push는 사용자 확인 후에만.** 현재 로컬 커밋이 origin보다 앞서 있을 수 있음.
- 로컬 테스트용 venv: 사용자 스크래치패드에 있음(requests/bs4 설치됨).
  실사이트는 네트워크 차단이라 mock HTML로 파서 로직을 검증해왔다.
