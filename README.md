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

제목에 아래 단어가 있으면 이슈에 ⭐ 섹션으로 따로 묶인다.
`check_notices.py`의 `KEYWORDS`에서 수정.

```
반도체 공정 FAB 팹 소자 실습 인턴 탐방 설계 경진 챌린지
공모 채용 교육 수료 종합설계 졸업 장학 IDEC 삼성 하이닉스
```

## 주의

- 학교 서버가 컨테이너 네트워크 허용목록 밖이라 **실제 HTML 파싱은 검증되지 않았다.**
  첫 수동 실행에서 로그를 보고, 신규 글이 0건으로만 나오면 셀렉터를 손봐야 한다.
- 게시글 ID는 `view('546618')` 패턴에서 정규식으로 추출한다.
  목록 번호는 상단 고정 공지 때문에 불안정하므로 쓰지 않는다.
- 실패해도 조용히 넘어가지 않도록, 수집 실패 시에도 이슈가 생성된다.
