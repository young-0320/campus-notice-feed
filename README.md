# KHU EE 공지 감시기

경희대 전자공학과(ee.khu.ac.kr) 공지 게시판 5곳을 3일마다 확인하고,
신규 글이 있으면 GitHub Issue를 자동 생성한다. GitHub이 이슈 생성 시 메일을 보낸다.

## 감시 대상

| 게시판 | boardId | menuNo |
|---|---|---|
| 소식 | BMSR00044 | 21700021 |
| 학사/장학 | BMSR00040 | 21700019 |
| 취업정보/대외활동 | BMSR00040 | 21700020 |
| 행사 | BMSR00044 | 21700046 |
| 기타공지 | BMSR00040 | 21700022 |

`check_notices.py`의 `BOARDS`에서 추가/삭제 가능.

## 설치

1. **새 private 리포지토리 생성** (예: `khu-notice-watcher`)
2. 이 폴더의 파일 3개를 그대로 push
   ```
   check_notices.py
   .github/workflows/khu-notice.yml
   README.md
   ```
3. 리포지토리 **Settings → Actions → General → Workflow permissions**
   → `Read and write permissions` 체크
4. **Actions 탭 → "KHU EE 공지 감시" → Run workflow**로 수동 1회 실행

첫 실행은 기존 글을 전부 baseline으로 저장하고 알림을 보내지 않는다.
`seen.json`이 커밋되면 정상. 이후 실행부터 신규 글만 잡는다.

## 알림 메일 받기

리포지토리 우측 상단 **Watch → All Activity** 로 설정하면
이슈 생성 시 GitHub 계정 메일로 알림이 온다.

## 로컬 실행

```bash
pip install requests beautifulsoup4
python check_notices.py
```

## 키워드 하이라이트

제목에 관심 키워드가 있으면 이슈에서 ⭐ 섹션으로 따로 묶인다.
키워드는 **`keywords.txt`** 파일에서 수정한다 (파이썬 코드를 건드릴 필요 없음).

- 한 줄에 키워드 하나
- `#`로 시작하는 줄과 빈 줄은 무시 (카테고리 주석용)
- 대소문자 구분 안 함 (`FAB` == `fab`)
- 파일을 지우거나 비우면 `check_notices.py`의 `DEFAULT_KEYWORDS`로 폴백

GitHub 웹에서 `keywords.txt`를 열어 바로 편집·커밋해도 된다.

## 주의

- 학교 서버가 컨테이너 네트워크 허용목록 밖이라 **실제 HTML 파싱은 검증되지 않았다.**
  첫 수동 실행에서 로그를 보고, 신규 글이 0건으로만 나오면 셀렉터를 손봐야 한다.
- 게시글 ID는 `view('546618')` 패턴에서 정규식으로 추출한다.
  목록 번호는 상단 고정 공지 때문에 불안정하므로 쓰지 않는다.
- 실패해도 조용히 넘어가지 않도록, 수집 실패 시에도 이슈가 생성된다.
