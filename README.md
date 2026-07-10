# campus-notice-feed

대학 공지 게시판을 주기적으로 크롤링해 신규 글을 GitHub Issue로 알려주는
서버리스 봇. 이슈 생성 시 GitHub이 알림 메일을 보낸다. GitHub Actions에서만
돌기 때문에 서버·비용이 없다.

> 현재는 경희대 전자공학과(ee.khu.ac.kr) 게시판 5곳 전용이다.
> 추후 타 학과/학교로 일반화 예정 (그래서 레포명은 `campus-notice-feed`).

## 감시 대상

| 게시판 | boardId | menuNo |
|---|---|---|
| 소식 | BMSR00044 | 21700021 |
| 학사/장학 | BMSR00040 | 21700019 |
| 취업정보/대외활동 | BMSR00040 | 21700020 |
| 행사 | BMSR00044 | 21700046 |
| 기타공지 | BMSR00040 | 21700022 |

`check_notices.py`의 `BOARDS`에서 추가/삭제 가능.

## 구성

```
check_notices.py                    # 크롤링·신규 판별·이슈 본문 생성
keywords.txt                        # 관심 키워드 목록 (⭐ 하이라이트)
.github/workflows/khu-notice.yml    # 3일마다 실행하는 GitHub Actions
seen.json                           # 본 글 ID 상태 (봇이 자동 커밋, 최초엔 없음)
log.md                              # 설계 변경 기록
```

## 설치

1. 이 리포지토리를 그대로 사용하거나 fork 한다.
2. **Settings → Actions → General → Workflow permissions**
   → `Read and write permissions` 체크 (seen.json 커밋·이슈 생성에 필요)
3. **Actions 탭 → "KHU EE 공지 감시" → Run workflow**로 수동 1회 실행

첫 실행은 기존 글을 전부 baseline으로 저장하고 알림을 보내지 않는다.
`seen.json`이 커밋되면 정상. 이후 실행부터 신규 글만 잡는다.
(단, 첫 실행에서 파서가 깨진 게 감지되면 baseline 대신 점검 이슈를 띄운다.)

## 알림 메일 받기

리포지토리 우측 상단 **Watch → All Activity** 로 설정하면
이슈 생성 시 GitHub 계정 메일로 알림이 온다.

## Discord 알림 받기 (선택)

`DISCORD_WEBHOOK` Secret을 설정하면 신규 공지/수집 실패 알림이
Discord 채널로도 전송된다. 미설정 시 자동으로 생략된다.

1. Discord 채널 → 톱니바퀴(채널 편집) → **Integrations → Webhooks →
   New Webhook** → **Copy Webhook URL**
2. GitHub repo → **Settings → Secrets and variables → Actions →
   New repository secret** → 이름 `DISCORD_WEBHOOK`, 값에 복사한 URL

> ⚠️ Webhook URL은 **Secret에만** 넣는다. URL을 아는 사람은 누구나 그
> 채널에 메시지를 보낼 수 있으므로 채팅·커밋·이슈에 절대 붙여넣지 말 것
> (퍼블릭 레포에서 특히 주의). 유출 시 Discord에서 webhook을 삭제하고
> 새로 만들면 된다.

## 로컬 실행

```bash
pip install requests beautifulsoup4
python check_notices.py
```

`GITHUB_OUTPUT` 환경변수가 없으면(로컬) 이슈 생성 없이 결과만 출력한다.

## 키워드 하이라이트

제목에 관심 키워드가 있으면 이슈에서 ⭐ 섹션으로 따로 묶인다.
키워드는 **`keywords.txt`** 파일에서 수정한다 (파이썬 코드를 건드릴 필요 없음).

- 한 줄에 키워드 하나
- `#`로 시작하는 줄과 빈 줄은 무시 (카테고리 주석용)
- 대소문자 구분 안 함 (`FAB` == `fab`)
- 파일을 지우거나 비우면 `check_notices.py`의 `DEFAULT_KEYWORDS`로 폴백

GitHub 웹에서 `keywords.txt`를 열어 바로 편집·커밋해도 된다.

## 게시판 레이아웃 (두 종류)

게시판마다 목록 마크업이 다르다. 파서는 둘 다 자동 처리한다.

- **표형** (`BMSR00040`: 학사/장학·취업정보·기타공지) — `<table><tbody><tr>`
- **썸네일 카드형** (`BMSR00044`: 소식·행사) — `<ul class="bbs-thumb"><li>`

## 파서 건강검사 (마크업 변경 감지)

학교가 게시판 마크업을 바꾸면 파서가 아무것도 못 잡으면서도 에러 없이
"신규 0건"처럼 보이는 **조용한 실패**가 일어날 수 있다. 이를 잡기 위해
사이트가 표시하는 **"전체 N 건"**(`.bbs-total`)을 기준으로 삼는다:

- 전체 글이 있는데(N>0) 실제 추출 수가 기대치(`min(N, 30)`)의
  `PARSE_RATE_MIN`(0.7) 미만이면 → **"파서 점검 필요" 이슈**를 띄운다.
- 전체 0건(빈 게시판)은 정상으로 보고 경고하지 않는다.

이 이슈가 오면 `check_notices.py`의 셀렉터(`tbody tr` / `ul.bbs-thumb > li`)나
`ID_RE`(`view('id')` 패턴), `.bbs-total` 파싱을 실제 페이지에 맞게 손봐야 한다.

## 주의

- 실제 사이트(ee.khu.ac.kr) 5개 게시판에 대해 파싱이 검증되었다
  (표형 4곳·썸네일형 1곳 정상 추출, 행사는 현재 전체 0건인 빈 게시판).
  단 학교가 마크업을 바꾸면 깨질 수 있으니 위 건강검사가 이를 감지한다.
- 게시글 ID는 `view('546618')` 패턴에서 정규식으로 추출한다.
  목록 번호는 상단 고정 공지 때문에 불안정하므로 쓰지 않는다.
- 이슈 제목/본문은 게시글 텍스트(외부 입력)를 파일로 넘겨 생성한다.
  스크립트 인젝션 방지를 위해 `${{ }}` 인라인을 쓰지 않으니 워크플로 수정 시 주의.
