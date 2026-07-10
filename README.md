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

## 파서 건강검사 (마크업 변경 감지)

학교가 게시판 마크업을 바꾸면 파서가 아무것도 못 잡으면서도 에러 없이
"신규 0건"처럼 보이는 **조용한 실패**가 일어날 수 있다. 이를 잡기 위해:

- 데이터 행(td 2개 이상) 대비 ID 추출 성공률이 `PARSE_RATE_MIN`(0.7) 미만이거나
- 데이터 행 자체가 0개(구조가 통째로 바뀜)면

수집 실패로 간주하고 **"파서 점검 필요" 이슈**를 띄운다. 이 이슈가 오면
`check_notices.py`의 `tbody tr` 셀렉터나 `ID_RE`(`view('id')` 패턴)를
실제 페이지에 맞게 손봐야 한다.

## 주의

- 학교 서버가 컨테이너 네트워크 허용목록 밖이라 **실제 HTML 파싱은 아직
  실사이트로 검증되지 않았다.** 첫 수동 실행 로그를 반드시 확인할 것.
- 게시글 ID는 `view('546618')` 패턴에서 정규식으로 추출한다.
  목록 번호는 상단 고정 공지 때문에 불안정하므로 쓰지 않는다.
- 이슈 제목/본문은 게시글 텍스트(외부 입력)를 파일로 넘겨 생성한다.
  스크립트 인젝션 방지를 위해 `${{ }}` 인라인을 쓰지 않으니 워크플로 수정 시 주의.
