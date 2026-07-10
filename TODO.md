# TODO

감사(2026-07-11) 확정 버그 11개 중 **10개 완료**(1·2·3·4·5·6·8·9·10·11),
7만 보류. 개선축의 **회귀 테스트·관측성(step summary)도 완료**. 완료 항목의
상세는 `bug_report.md` 참고. 아래는 **남은 것만**.

---

## 근시일 스코프 (오늘 할 수 있는 것)

- [ ] **Dependabot PR #2·#3·#4 처리** — `dependabot.yml`이 정상 작동해 연 PR.
  액션 메이저 버전 업 제안(setup-python v5→v6, checkout v4→v7,
  github-script v7→v9). 각 changelog 확인 후 병합(병합 시 고정 SHA가 새
  버전 것으로 갱신됨). 메이저 점프라 묻지 말고 병합 금지. PR 노이즈가 많으면
  `dependabot.yml`에 grouping이나 업데이트 상한 설정 고려.
- [ ] **(보류) 레이아웃 셀렉터 좁히기 — item 7** — `check_notices.py`
  `parse_board`에 TODO 주석 있음. `select("tbody tr")`가 문서 전역이라
  무관한 테이블에 걸릴 수 있음. 정확한 리스트 컨테이너 클래스는 **라이브
  DOM 확인 필요** → 지금 추측 수정은 검증된 파싱 회귀 위험. 일반화
  리팩터링 때 사이트별 config로 함께 처리.

---

## 앞으로의 방향성 (미래 계획 — 오늘 스코프 아님)

### ~~1. seen.json 키를 표시명 → 불변값(boardId+menuNo)~~ ✅ 완료 (2026-07-11)

`feat/stable-keys-discord` 브랜치에서 구현. `board_key()` + 런타임 멱등
이관(`migrate_seen()`). 상세는 log.md 6번.

### 2. 일반화 (KHU 전용 → 타학과/타학교)

- 1단계(같은 CMS 학과 추가): 데이터만 `site.toml`로 분리
  (base / title_prefix / boards). `tomllib` 무의존. 워크플로 `name`·파일명도
  이때 중립화. keywords.txt는 평문 유지.
- 2단계(다른 CMS 학교 추가 시에야): `parse_board`를 사이트 어댑터
  (셀렉터 + ID_RE + URL 템플릿 묶음)로 추상화. 지금 미리 하면 과설계.

### 3. 알림 채널 다변화 (Discord / Telegram) — Discord ✅ 완료 (2026-07-11)

Discord는 `feat/stable-keys-discord` 브랜치에서 구현(보안 전제는 log.md
7번에 명문화, 웹훅 준비 절차는 README로 이동). Telegram 등은 남음.

- [ ] **웹훅 준비(사용자 몫)**: `DISCORD_WEBHOOK` Secret 등록 — 절차는
  README "Discord 알림 받기" 참고. URL은 **Secret에만**.

### 4. 기타 아이디어

- 온디맨드 digest(원할 때 최근 공지 모아보기).
- 에러/경고 이슈는 관리자에게만 분리 라우팅(정상 공지와 채널 구분).
