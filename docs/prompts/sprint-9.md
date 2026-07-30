# Sprint 9 — Phase A: 기반 정비 + 계정/인증

V1.1의 첫 코드 스프린트. 조직이 5역할로 확장되고 에이전트가 루프를 돌기 전에, **그 하중을 견딜 뼈대**를 먼저 세운다. 이 스프린트가 부실하면 Sprint 16(Agent Harness)에서 전부 무너진다.

이 스프린트는 **기능 스프린트가 아니라 기반 스프린트다.** CEO에게 보이는 새 기능은 로그인 하나뿐이다.

---

## 0. 시작하기 전에 반드시 읽어라

1. `CLAUDE.md` (루트) — **최우선.** 철학, 조직 모델, 불변식 #1~#17, V1.1 로드맵
2. `docs/ARCHITECTURE.md` — V1.1 Target(§1~5) + V1 As-Built(§6) + 구조적 부채(§6.4)
3. `docs/design/UX_SPEC.md` — CEO Workspace 정보구조
4. Sprint 8.5 완료 보고 — 특히 "코드에서 발견한 문제"와 "Sprint 9에 넘기는 것" 항목
5. `docs/DECISIONS.md` — 특히 Sprint 5~8 구간과 #128 이후
6. `PROGRESS.txt`

읽어야 할 코드 (수정 대상의 핵심):
- `apps/api/app/modules/workflow_engine/engine.py` (720줄, 이번 스프린트에서 가장 많이 바뀐다)
- `apps/api/app/templates/software_company.py`
- `apps/api/app/main.py` (lifespan)
- `apps/api/app/core/db_models.py`, `core/lifecycle/task_states.py`
- `apps/api/app/modules/costs/`
- `apps/api/app/modules/sandbox/docker_sandbox.py`
- `apps/api/tests/conftest.py`

## 1. 작업 방식

- **자율적으로 일해라.** 확인차 멈추지 마라. 브리프가 열어둔 부분은 판단하고 `docs/DECISIONS.md`에 기록하고 계속 가라.
- **PROGRESS.txt 규율.** Appendix A로 리셋. 항목 단위 즉시 갱신. 몰아서 금지.
- **Phase마다 conventional 커밋 + `git push`.** 원격 HEAD가 최종 커밋과 일치해야 완료다.
- **불변식은 협상 대상이 아니다.** 특히 #6(mock 완전 동작), #9/#12(AI는 실행 명령 선택 불가), #15(계정 스코프).
- **Appendix B의 완료 보고 형식을 반드시 지켜라.**

---

## 2. 승인된 설계 결정 — 재논의 금지

모든 열린 질문은 아래에서 이미 답했다. 다시 묻지 말고, 더 나은 방법을 찾았다고 바꾸지도 마라. 정말로 불가능한 지시를 발견하면 그때만 우회하고 그 사실을 완료 보고 §4에 적어라.

### 2.1 인증 방식 — HttpOnly 세션 쿠키 (JWT 아님)

- **DB에 `sessions` 테이블을 두고, 세션 토큰을 HttpOnly 쿠키로 발급한다.**
- 이유: 로컬 단일 서버 환경에서 JWT는 과하다. 로그아웃/강제 만료가 DB row 삭제 한 번으로 끝나고, 프론트가 토큰을 저장하지 않으므로 XSS 표면이 줄어든다.
- 쿠키 설정: `httponly=True`, `samesite="lax"`, `secure=` 설정값(로컬 기본 `False`), `max_age` 30일.
- 세션 토큰: `secrets.token_urlsafe(32)`. **토큰 자체를 DB에 저장하지 말고 SHA-256 해시를 저장해라.** (DB 유출 시 세션 탈취 방지)
- 슬라이딩 만료: 요청마다 `last_seen_at` 갱신, 만료까지 7일 미만이면 연장.
- 프론트는 모든 API 호출에 `credentials: "include"`. CORS는 이미 `allow_credentials=True`이므로 `allow_origins`가 와일드카드가 아닌지만 확인해라(와일드카드면 쿠키가 안 붙는다).

### 2.2 비밀번호 — bcrypt 해시만. 평문 저장 절대 금지

- `bcrypt` 패키지 직접 사용(cost factor 12). `passlib`은 쓰지 마라(유지보수 정체).
- **스키마에 평문 비밀번호 컬럼이 존재해서는 안 된다.** 로그에도 남기지 마라.
- 최소 요건: 8자 이상. 그 이상의 복잡도 규칙은 만들지 마라(로컬 도구다).
- 비밀번호 분실은 CLI 스크립트로 리셋한다(§2.6).

### 2.3 users / sessions 스키마 — OAuth 확장을 미리 수용한다

```
users
  id              str, PK (uuid)
  email           str, unique, 소문자 정규화 후 저장
  display_name    str
  password_hash   str | NULL      # local이 아니면 NULL
  auth_provider   str             # 'local' | 'google' | ...
  provider_subject str | NULL     # OAuth의 sub. local이면 NULL
  created_at      datetime
  last_login_at   datetime | NULL
  UNIQUE (auth_provider, provider_subject)

sessions
  id              str, PK         # 토큰의 SHA-256 해시
  user_id         str, FK -> users.id, ON DELETE CASCADE
  created_at      datetime
  last_seen_at    datetime
  expires_at      datetime
```

**Google OAuth는 이번에 구현하지 않는다.** 하지만 `modules/auth/`를 아래 구조로 만들어서, 나중에 파일 하나 추가로 끝나게 해라:

```
modules/auth/
  __init__.py
  routes.py          # /api/auth/*
  service.py         # 가입·로그인·세션 발급/검증/폐기
  schemas.py
  identity.py        # IdentityProvider 인터페이스 + UserIdentity
  providers/
    local.py         # email+password 구현 (이번 스프린트 유일한 구현체)
```

`IdentityProvider`는 `authenticate(credentials) -> UserIdentity | None`과 `provider_key` 정도의 최소 인터페이스면 충분하다. **추상화를 과하게 만들지 마라.** Google을 추가할 때 `providers/google.py` 하나만 쓰면 되는 수준이면 성공이다.

### 2.4 계정 스코프 (불변식 #15)

- `ProjectORM`에 `owner_id` (FK → users.id, **NOT NULL**) 추가.
- 다른 테이블은 project를 통해 스코프된다. 별도 owner 컬럼 추가하지 마라.
- FastAPI dependency `get_current_user`를 만들고 **모든 라우터에 적용해라.** 인증 없이 접근 가능한 라우트는 다음뿐이다:
  - `GET /api/health`, `GET /api/health/db`
  - `POST /api/auth/register`, `POST /api/auth/login`
- **SSE 스트림(`/stream`)도 인증 대상이다.** 쿠키가 자동 전송되므로 동작하지만, 반드시 테스트로 확인해라.
- **남의 회사에 접근하면 403이 아니라 404다.** 존재 자체를 노출하지 않는다. project_id를 받는 모든 라우트에 적용.

### 2.5 인증 라우트

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/auth/register` | email, password, display_name → 계정 생성 + 즉시 로그인 |
| POST | `/api/auth/login` | email, password → 세션 쿠키 발급 |
| POST | `/api/auth/logout` | 세션 폐기 + 쿠키 삭제 |
| GET | `/api/auth/me` | 현재 CEO 정보 (미인증 시 401) |

에러 메시지 규칙: **로그인 실패 시 "이메일이 없다"와 "비밀번호가 틀렸다"를 구분하지 마라.** 계정 열거 공격 방지. 단일 메시지로 통일하되 Commander 목소리로 써라(내부 용어 누출 금지).

### 2.6 관리자 CLI 스크립트 2종

- `scripts/export_users.py` → CSV 출력. 컬럼: `id, email, display_name, auth_provider, created_at, last_login_at, password_hash`. **평문 비밀번호 컬럼은 없다.** 출력 경로를 인자로 받고, 없으면 stdout.
- `scripts/reset_password.py --email <email> --password <new>` → 해당 계정 비밀번호 재설정.
- Makefile에 `export-users` 타깃 추가(`## ` 주석 포함해서 `make help`에 뜨게).

### 2.7 마이그레이션 — 기존 데이터 파괴는 승인됨

CEO가 명시적으로 승인했다: **기존 개발 DB의 회사/미션 데이터는 전부 버려도 된다.**

- Alembic 마이그레이션에서: `users`/`sessions` 생성 → 기존 project 계층 데이터를 **FK 자식부터 순서대로 삭제** → `projects.owner_id`를 NOT NULL로 추가.
- `downgrade()`는 컬럼/테이블 제거만 한다. **삭제된 데이터는 복구할 수 없음을 마이그레이션 파일 docstring에 명시해라.**
- `scripts/seed.py`가 데모 CEO 계정을 만들도록 갱신한다:
  - 기본값 `ceo@commander.local` / `commander1234`, `.env`의 `COMMANDER_DEMO_EMAIL` / `COMMANDER_DEMO_PASSWORD`로 오버라이드 가능
  - 데모 회사 "Acme AI"의 `owner_id`를 이 계정으로 설정
  - README와 `.env.example`에 이 기본 계정을 명시해라
- 이 파괴적 조치를 `docs/DECISIONS.md`에 기록해라.

### 2.8 파이프라인 데이터화 — 동작은 그대로, 구조만 바꾼다

현재 엔진 최상단의 이 줄이 문제다:

```python
_PM, _ENGINEER, _REVIEWER = TEMPLATE.roles   # positional unpacking
```

역할이 5개가 되는 순간 깨진다. 아래로 바꾼다:

- `TEMPLATE`에 `pipeline: tuple[StageSpec, ...]` 추가.
- `StageSpec` 필드: `role_key: str`, `kind: Literal["plan", "produce", "review"]`, `lands_code: bool`, `runs_checks: bool`
- 엔진은 하드코딩된 3단계가 아니라 **이 시퀀스를 순회한다.** 코드 랜딩과 체크 실행은 스테이지 플래그에 붙는다.
- `resume_from`은 role_key가 아니라 **스테이지 인덱스**로 다룬다(같은 역할이 두 번 등장할 수 있으므로).
- `prompt_builder/role_contracts.py`의 `TEMPLATE.roles[1]` 같은 positional 의존도 전부 제거해라.

이 작업은 불변식 #16(역할은 데이터)의 기반 공사다. Sprint 10이 이 위에 Role/Employee 분리를 올린다.

**중요: 이번 스프린트에서 실제 파이프라인은 변하지 않는다.** `software_company` 템플릿은 여전히 PM → Engineer → Reviewer 3스테이지다. 기존 157개 테스트가 전부 그대로 통과해야 한다. 검증은 **테스트 전용 4스테이지 템플릿**을 만들어 엔진이 임의 시퀀스를 도는지 확인하는 것으로 한다. CTO나 Frontend Engineer를 미리 추가하지 마라 — 그건 Sprint 10/11이다.

### 2.9 운영 신뢰성 4종

**(a) 고아 미션 복구**
`lifespan` 시작 시 `in_progress` / `in_review` 상태의 Task를 스캔해 `blocked`로 전환하고 사유와 함께 이벤트를 발행한다. `pending_approval`은 정상 대기 상태이므로 건드리지 마라.
- 신규 `EventType.TASK_RECOVERED` + payload 모델 + `python scripts/generate_ts_schemas.py` 재생성
- 사유 문구는 CEO가 읽는다: "서버가 재시작되어 진행 중이던 업무가 중단되었습니다" 수준의 회사 목소리로.

**(b) 미션 취소**
- `POST /api/tasks/{task_id}/cancel` (본문 선택: 사유)
- 엔진이 `_running: dict[task_id, asyncio.Task]` 레지스트리를 유지한다. `start_task`/`resume_after_decision`에서 등록, 종료 시 `finally`로 제거.
- 취소는 `asyncio.Task.cancel()` → 상태 `cancelled` → 이벤트.
- **`asyncio.CancelledError`는 `except Exception`에 잡히지 않는다**(BaseException 계열). `_run_pipeline`에 명시적 핸들러를 넣어 취소를 실패로 오인하지 않게 해라.
- `TASK_TRANSITIONS`에 `in_progress → cancelled`, `in_review → cancelled`를 허용 추가.
- 프론트: 미션 상세에 취소 버튼(진행 중일 때만).

**(c) stale ORM 접근 제거**
`_run_pipeline`이 세션을 닫은 뒤 detached `task` ORM 객체를 계속 읽는다(`task.deliverable_type`, `task.branch_name`). 현재는 fallback 덕에 우연히 동작하지만 루프가 생기면 깨진다.
- 파이프라인이 필요로 하는 값을 **불변 스냅샷(frozen dataclass 또는 Pydantic 모델)** 으로 한 번 읽고, 갱신이 필요한 시점에만 세션을 다시 연다.
- ORM 객체를 세션 밖으로 들고 나가는 패턴을 엔진 전체에서 제거해라.

**(d) 미션 예산 가드 (불변식 #13)**
- 설정(`core/config.py` + `.env.example`): `COMMANDER_MISSION_MAX_TOKENS`(기본 200000), `COMMANDER_MISSION_MAX_USD`(기본 5.0), `COMMANDER_MISSION_MAX_SECONDS`(기본 900)
- 각 스테이지 실행 **전**에 누적 사용량을 확인하고, 초과 시 스테이지를 시작하지 않고 Task를 `blocked`로 둔다.
- 신규 `EventType.BUDGET_EXCEEDED` + payload(어떤 한도를, 얼마나, 어느 스테이지에서). 사유는 CEO가 읽는 문장으로.
- 누적 조회는 `modules/costs`에 함수를 추가해서 쓴다. 엔진이 costs 내부를 직접 쿼리하지 마라(불변식 #1).
- **mock 모드에서도 회계가 돌아야 한다.** mock provider가 usage를 반환하는지 확인하고, 안 하면 그럴듯한 가상 usage를 반환하게 해라. 예산 한도를 낮춰서 mock으로 초과를 재현할 수 있어야 한다.

### 2.10 Phase 0 하이진 3종

- **pacing 스위치**: `_pause()`의 `random.uniform(0.5, 1.5)`가 테스트에서도 그대로 돈다(풀 파이프라인 테스트 1개가 15.7초, 전체 232초). `settings.commander_pacing_enabled`(기본 True, env `COMMANDER_PACING`)를 추가하고 `conftest.py`에서 끈다. **프로덕션 기본값은 켬 유지** — 페이싱은 Timeline이 살아있게 보이는 UX 장치다.
- **샌드박스 하드닝**: `docker create`에 `--cap-drop ALL`과 `--security-opt no-new-privileges`를 추가해라. `--read-only`는 체크가 `/workspace`에 쓸 수 있으므로 **넣지 마라** — 대신 그 이유를 코드 주석과 DECISIONS에 남겨라.
- **PROGRESS 카운터**: Sprint 8의 Phase 4 헤더가 `(4/6)`인데 항목은 6개 완료였다. Appendix A 리셋으로 해소되지만, 헤더 카운터를 항목 상태와 항상 일치시킨다는 규칙을 PROGRESS 헤더 주석에 남겨라.

### 2.11 프론트엔드 — "작동하는 최소"만

Render 벤치마크 기반 정식 UI는 **Sprint 14**다. 지금은 디자인에 시간을 쓰지 마라. 기존 다크 테마 컴포넌트를 재사용해라.

- `/login`, `/register` 페이지 (기존 스타일 재사용, 새 디자인 시스템 만들지 마라)
- 미인증 상태로 보호된 경로 진입 → `/login` 리다이렉트
- API가 401을 반환하면 → 세션 정리 후 `/login`
- 로그아웃 버튼 (사이드바 하단)
- 우상단에 계정 표시 영역을 **최소 형태로** 마련 (Render 패턴의 씨앗. 이메일 또는 이니셜 + 로그아웃. 드롭다운 메뉴 같은 건 만들지 마라)
- 회사 목록은 당연히 내 것만 보인다
- **"Google로 로그인" 버튼을 만들지 마라.** 불변식 "hidden means absent" — 작동하지 않는 UI는 존재하지 않아야 한다

### 2.12 Sprint 8.5 리뷰에서 확정된 문서 수정 4건

Sprint 8.5가 실제 설계 공백 1건과 사소한 불일치 3건을 찾아냈다. CTO가 결정했으므로 그대로 적용하고, 각각 `docs/DECISIONS.md`에 기록해라.

**(a) Headquarters의 운명 — 확정: CEO Workspace에 흡수되어 사라진다.**
사이드바 페이지로 이동하지 않는다. 같은 라우트(`/company/[id]`), 같은 목적, 다른 형태다. V1 Headquarters의 4개 블록은 이렇게 매핑된다:

| V1 Headquarters 블록 | V1.1 행선지 |
|---|---|
| Decision strip (hero) | Pending Approvals 위젯 + PM 리포트의 "승인 필요" 항목 |
| Situation Report | PM 리포트 (UX_SPEC §3.2) |
| Vitals 4개 | Progress · Employees · Risks · Costs 위젯 |
| 축약 Timeline | Timeline 위젯 |

근거: 위젯 도크가 Headquarters의 기능을 이미 전부 대체한다. 둘을 함께 남기면 정면 중복이고, CEO에게 "어느 화면을 봐야 하는가"라는 불필요한 질문을 만든다.

적용:
- `docs/ARCHITECTURE.md` §8의 "V1 as-built surfaces … These are not discarded in V1.1 — most become Sidebar pages" 문장을 고쳐라. Headquarters는 **흡수(absorbed)** 이고 나머지가 사이드바 페이지로 남는다는 것을 명확히 하고, 위 매핑 표를 넣어라.
- `docs/design/UX_SPEC.md` §7 도입부에 Headquarters가 흡수되었음과 그 매핑을 한 단락으로 명시해라 (§2 IA 트리는 이미 옳으므로 건드리지 마라).
- `CLAUDE.md` 용어표: `| Dashboard | Headquarters |` → `| Dashboard | CEO Workspace |`. "Headquarters"는 은퇴한다.
- `CLAUDE.md` §8의 "CEO surface:" 목록에서 Headquarters를 CEO Workspace로 바꾸지 마라 — 그 문장은 **V1 as-built 서술**이므로 Headquarters가 맞다. 대신 V1.1에서 흡수됨을 §9 경계 서술에 한 줄 추가해라. 이 구분을 흐리지 마라.

**(b) Park 예시 불일치.** `CLAUDE.md` §2의 로스터 예시가 Kim/Lee/Park 세 명을 모두 Backend Engineer 아래 두는데, `UX_SPEC` §5.4는 Park을 Frontend Engineer로 둔다. **UX_SPEC이 맞다.** `CLAUDE.md` 예시를 두 역할로 고쳐서 "한 역할에 세 명"으로 오독되지 않게 해라:

```
Backend Engineer
  ├── Kim  (Claude Sonnet)
  └── Lee  (GPT-5.5)
Frontend Engineer
  └── Park (Gemini)
```

**(c) stale 문서 3종 — 삭제하지 말고 배너를 붙여라.** `docs/backend/MODULES.md`, `docs/backend/DEPENDENCIES.md`, `docs/adr/README.md`는 Sprint 2 시절 서술이라 현재 as-built와 맞지 않는다. 삭제는 기록 손실이고, 방치는 오정보다. 각 파일 최상단에 다음 배너를 넣어라:

```
> **HISTORICAL (Sprint 2).** 이 문서는 초기 모듈 경계 설계 기록이며 현재 구현과 일치하지 않는다.
> 현재의 진실의 원천은 `docs/ARCHITECTURE.md`다. 참고용 이력으로만 읽어라.
```

**(d) `docs/prompts/`는 건드리지 마라.** 과거 스프린트 브리프는 이력이다. Sprint 8.5가 올바르게 보존했다.

이 4건은 문서 수정이므로 Phase 0에서 처리하고, 이후 Phase에서는 코드에 집중해라.

---

## 3. Phase별 작업

각 Phase는 conventional 커밋 + `git push`로 끝난다.

### Phase 0 — 하이진 + 문서 잔여 수정 (§2.10, §2.12)
- 0.1 PROGRESS.txt를 Appendix A로 리셋
- 0.1a §2.12의 문서 수정 4건 적용 (Headquarters 운명 확정 · Park 예시 · 용어표 · stale 문서 배너)
- 0.2 pacing 스위치 + conftest 적용, 테스트 총 소요시간 before/after 기록
- 0.3 샌드박스 `--cap-drop ALL` + `--security-opt no-new-privileges`, read-only 미적용 사유 주석
- 0.4 PROGRESS 카운터 규칙 주석
- 0.5 커밋+푸시: `chore(sprint9): hygiene — docs closure, pacing switch, sandbox hardening`

### Phase 1 — 운영 신뢰성 (§2.9)
- 1.1 stale ORM 제거 (**먼저 한다.** 이후 작업이 이 위에 올라간다)
- 1.2 고아 미션 복구 + `TASK_RECOVERED` 이벤트 + TS 재생성
- 1.3 취소 라우트 + 실행 레지스트리 + `CancelledError` 처리 + 상태전이 허용
- 1.4 예산 가드 + `BUDGET_EXCEEDED` 이벤트 + costs 조회 함수 + config
- 1.5 mock 모드에서 예산 초과 재현 가능한지 실제로 확인
- 1.6 테스트 추가 (복구 3+, 취소 4+, 예산 5+)
- 1.7 커밋+푸시: `feat(reliability): orphan recovery, mission cancel, budget guard`

### Phase 2 — 파이프라인 데이터화 (§2.8)
- 2.1 `StageSpec` + `TEMPLATE.pipeline` 정의
- 2.2 엔진을 시퀀스 순회 구조로 리팩터. positional unpacking 전부 제거
- 2.3 `resume_from`을 스테이지 인덱스 기반으로
- 2.4 `prompt_builder` positional 의존 제거
- 2.5 테스트 전용 4스테이지 템플릿으로 임의 시퀀스 동작 검증 (5+ 테스트)
- 2.6 **기존 157개 테스트가 전부 통과하는지 확인** (동작 변화 0이 목표)
- 2.7 `docs/ARCHITECTURE.md`의 워크플로우 엔진 서술 동기화
- 2.8 커밋+푸시: `refactor(workflow): template-driven stage pipeline`

### Phase 3 — 인증 백엔드 (§2.1~2.7)
- 3.1 `users`/`sessions` 모델 + Alembic 마이그레이션 (파괴적 삭제 포함, docstring 경고)
- 3.2 `modules/auth/` 구조 + `IdentityProvider` + `providers/local.py`
- 3.3 bcrypt 해싱 + 검증
- 3.4 세션 발급/검증/폐기 + 슬라이딩 만료 + 토큰 해시 저장
- 3.5 인증 라우트 4종
- 3.6 `get_current_user` dependency + **전 라우터 적용**
- 3.7 `ProjectORM.owner_id` + 모든 project 스코프 라우트에 소유권 검사(남의 것 → 404)
- 3.8 SSE 스트림 인증 확인
- 3.9 `scripts/export_users.py`, `scripts/reset_password.py`, Makefile 타깃
- 3.10 `scripts/seed.py` 데모 계정 대응
- 3.11 `.env.example` + `core/boot_checks.py` 갱신
- 3.12 테스트 (가입/중복이메일/로그인/실패메시지 통일/세션만료/미인증 401/타계정 404/SSE — 15+)
- 3.13 커밋+푸시: `feat(auth): local accounts, sessions, per-account scoping`

### Phase 4 — 프론트 최소 인증 (§2.11)
- 4.1 `/login`, `/register` 페이지
- 4.2 인증 상태 관리 + 미인증 리다이렉트
- 4.3 전역 401 처리
- 4.4 모든 API 호출에 `credentials: "include"`
- 4.5 사이드바 로그아웃 + 우상단 계정 표시(최소)
- 4.6 `pnpm typecheck` + `pnpm build` 통과
- 4.7 커밋+푸시: `feat(auth): minimal login/register UI`

### Phase 5 — 검증 · 문서 · 보고
- 5.1 `make test` 전체 (pytest + typecheck + build)
- 5.2 **수동 E2E 시나리오를 실제로 돌리고 결과를 기록해라** (DoD §5의 9개 항목)
- 5.3 `CLAUDE.md` 갱신: 인증 레이어, 파이프라인 데이터화, 신규 이벤트 타입, 신규 명령어. **아키텍처 변경은 같은 커밋에서 문서 동기화**(불변식 #10)
- 5.4 `docs/ARCHITECTURE.md` As-Built 갱신
- 5.5 `README.md`: 로그인 필요 사실 + 데모 계정 + 신규 make 타깃
- 5.6 `docs/DECISIONS.md` 기록 (최소: §2.12 문서 수정 4건의 근거, 세션 쿠키 선택 근거, 토큰 해시 저장, 평문 비밀번호 거부, 파괴적 마이그레이션, read-only 미적용, 404 vs 403, 그 외 네가 내린 모든 판단)
- 5.7 커밋+푸시: `chore(sprint9): docs sync, sprint complete`
- 5.8 원격 HEAD 일치 확인

---

## 4. Out of Scope

이번 스프린트에서 **절대** 하지 마라:

- Role/Employee 분리, 역할 데이터화 (Sprint 10)
- CTO 역할, 복수 직원, 직원 채용 플로우 (Sprint 11)
- Project Specification, PM↔CTO 협의, Requirement Discovery (Sprint 12)
- CEO↔PM 대화, PM 리포트, 결정 권한 분류 (Sprint 13)
- Render UI 셸, 2단 레이아웃, 사이드바 재편 (Sprint 14)
- 위젯 시스템, 위젯 카탈로그 (Sprint 15)
- Agent Harness, 툴 루프, Repository Awareness (Sprint 16)
- 자가 수정 루프 (Sprint 17)
- Project Memory, Sprint Learning (Sprint 18)
- Mission Tree, 잔여 위젯 (Sprint 19)
- Google OAuth **구현** (스키마·인터페이스만 준비)
- 비밀번호 재설정 이메일, 이메일 인증, 2FA
- 멀티유저 협업, 권한 레벨(admin/member)
- mock provider 콘텐츠 개선

"하는 김에" 미리 만들지 마라. V1/V1.1 경계 원칙과 동일하게, **스프린트 경계도 지켜야 로드맵이 의미를 갖는다.**

---

## 5. Definition of Done

전부 **실제로 실행해서** 확인해라. 코드를 읽고 "될 것이다"라고 판단하지 마라.

1. 미션 실행 중 서버를 강제 종료(Ctrl+C) 후 재기동 → 해당 미션이 `blocked` 상태이고, Timeline에 사유가 CEO 목소리로 남아 있다. `in_progress`로 남은 미션이 0건이다
2. 미션 실행 중 취소 버튼 → 5초 이내 `cancelled`, Timeline에 기록, 에이전트가 idle로 복귀
3. `COMMANDER_MISSION_MAX_TOKENS`를 아주 낮게 설정하고 mock 미션 실행 → `blocked` + `BUDGET_EXCEEDED` 이벤트 + CEO가 읽을 수 있는 사유
4. 회원가입 → 로그아웃 → 로그인 → 내 회사만 보인다
5. 두 번째 계정 생성 → 첫 계정의 project_id로 직접 API 호출 → **404**(403 아님)
6. 인증 쿠키 없이 API 호출 → 401 (health와 auth 라우트 제외 전부)
7. `python scripts/export_users.py` → CSV 생성, **평문 비밀번호 없음**
8. `make demo` → 데모 계정으로 로그인 → 미션 하나를 끝까지(생성→기획→구현→체크→감사→승인→머지) 완주
9. 테스트 전용 4스테이지 템플릿으로 엔진이 정상 동작
10. `make test` 전부 그린. **테스트 카운트 157 → 190 이상**
11. 전체 테스트 소요 시간이 pacing 스위치로 유의미하게 단축됨 (before/after 숫자 보고)
12. `CLAUDE.md` / `ARCHITECTURE.md`가 실제 코드 상태와 일치
13. 원격 HEAD가 최종 커밋과 일치
14. mock 모드에서 API 키 0으로 전체 흐름이 여전히 동작 (불변식 #6)

---

## Appendix A — PROGRESS.txt 체크리스트

```
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 9 — Phase A: Foundation & Authentication
 Overall: 0/56 items · 0%
 Now working on: -
 Last update: -
 (헤더의 n/m과 %는 항목 상태와 항상 일치시킬 것)
================================================

PHASE 0 — 하이진 + 문서 잔여 수정                              (0/9)
[ ] 0.1  PROGRESS.txt 리셋
[ ] 0.1a Headquarters 흡수 확정 (ARCHITECTURE §8 + UX_SPEC §7 + 매핑 표)
[ ] 0.1b 용어표 Dashboard -> CEO Workspace / V1 as-built 서술은 보존
[ ] 0.1c CLAUDE.md Park 예시를 2역할로 수정
[ ] 0.1d stale 문서 3종에 HISTORICAL 배너
[ ] 0.2  pacing 스위치 (settings + conftest) / 소요시간 before-after 기록
[ ] 0.3  샌드박스 --cap-drop ALL + --security-opt no-new-privileges
[ ] 0.4  read-only 미적용 사유 주석 + PROGRESS 카운터 규칙 주석
[ ] 0.5  커밋+푸시: chore(sprint9) hygiene

PHASE 1 — 운영 신뢰성                                          (0/11)
[ ] 1.1  stale ORM 제거 — 파이프라인 스냅샷 도입
[ ] 1.2  엔진 전체에서 detached ORM 사용 패턴 제거 확인
[ ] 1.3  고아 미션 복구 (lifespan 스캔 -> blocked)
[ ] 1.4  EventType.TASK_RECOVERED + payload + TS 재생성
[ ] 1.5  실행 레지스트리 (_running dict) + finally 정리
[ ] 1.6  POST /api/tasks/{id}/cancel + 상태전이 허용 추가
[ ] 1.7  asyncio.CancelledError 명시적 처리 (실패로 오인 금지)
[ ] 1.8  예산 가드 config 3종 + costs 누적 조회 함수
[ ] 1.9  EventType.BUDGET_EXCEEDED + 스테이지 진입 전 검사
[ ] 1.10 mock 모드에서 예산 초과 실제 재현 확인
[ ] 1.11 테스트 (복구 3+ / 취소 4+ / 예산 5+) + 커밋+푸시

PHASE 2 — 파이프라인 데이터화                                  (0/8)
[ ] 2.1  StageSpec 정의 (role_key / kind / lands_code / runs_checks)
[ ] 2.2  TEMPLATE.pipeline 추가
[ ] 2.3  엔진 시퀀스 순회 리팩터
[ ] 2.4  _PM/_ENGINEER/_REVIEWER positional unpacking 제거
[ ] 2.5  resume_from 을 스테이지 인덱스 기반으로
[ ] 2.6  prompt_builder positional 의존 제거
[ ] 2.7  테스트 전용 4스테이지 템플릿 + 검증 테스트 5+
[ ] 2.8  기존 157 테스트 전부 통과 확인 + 커밋+푸시

PHASE 3 — 인증 백엔드                                          (0/14)
[ ] 3.1  users / sessions 모델 정의
[ ] 3.2  Alembic 마이그레이션 (파괴적 삭제 + docstring 경고)
[ ] 3.3  modules/auth 구조 + IdentityProvider 인터페이스
[ ] 3.4  providers/local.py (email+password)
[ ] 3.5  bcrypt 해싱/검증 (cost 12, 평문 저장 없음 재확인)
[ ] 3.6  세션 발급/검증/폐기 + 토큰 SHA-256 해시 저장
[ ] 3.7  슬라이딩 만료 (last_seen_at, 7일 미만 시 연장)
[ ] 3.8  인증 라우트 4종 (register/login/logout/me)
[ ] 3.9  get_current_user dependency + 전 라우터 적용
[ ] 3.10 ProjectORM.owner_id + 소유권 검사 (타계정 -> 404)
[ ] 3.11 SSE 스트림 인증 동작 확인
[ ] 3.12 scripts/export_users.py + reset_password.py + make export-users
[ ] 3.13 seed.py 데모 계정 + .env.example + boot_checks
[ ] 3.14 테스트 15+ + 커밋+푸시

PHASE 4 — 프론트 최소 인증                                     (0/7)
[ ] 4.1  /login 페이지
[ ] 4.2  /register 페이지
[ ] 4.3  인증 상태 관리 + 미인증 리다이렉트
[ ] 4.4  전역 401 처리 + credentials:"include" 전 호출 적용
[ ] 4.5  사이드바 로그아웃 + 우상단 계정 표시(최소)
[ ] 4.6  typecheck + build 통과
[ ] 4.7  커밋+푸시: feat(auth) minimal login UI

PHASE 5 — 검증 · 문서 · 보고                                   (0/7)
[ ] 5.1  make test 전체 그린 (카운트 기록)
[ ] 5.2  DoD 14개 항목 수동 E2E 실행 + 결과 기록
[ ] 5.3  CLAUDE.md 갱신 (인증/파이프라인/이벤트/명령어)
[ ] 5.4  ARCHITECTURE.md As-Built 갱신
[ ] 5.5  README.md (로그인 필요 + 데모 계정 + 신규 타깃)
[ ] 5.6  DECISIONS.md 기록 (필수 7항목 + 자체 판단 전부)
[ ] 5.7  커밋+푸시 + 원격 HEAD 일치 확인
================================================
```

---

## Appendix B — 완료 보고 형식 (필수)

이 보고가 리뷰와 다음 스프린트 설계의 유일한 입력이다. **자기 평가가 아니라 검증 가능한 사실**을 적어라. 잘한 점을 나열하지 마라 — 리뷰어가 클론해서 직접 확인한다.

```
## Sprint 9 완료 보고

### 1. 커밋
- 최종 커밋 SHA:
- 원격 HEAD 일치 확인: (확인한 방법도 적을 것)
- 커밋 목록 (SHA + 메시지):

### 2. Phase별 결과
Phase 0~5 각각:
- 완료 여부
- 브리프 지시와 실제 구현의 차이 (없으면 "없음")
- 예상보다 어려웠던 지점

### 3. DoD 14개 항목 검증 결과
항목별로: 통과 / 실패 / 미검증
**실제로 실행한 명령과 관찰한 결과를 적어라.** "될 것이다"는 미검증이다.

### 4. 테스트
- 시작 시점: 157 passed / 4 skipped
- 종료 시점: ___ passed / ___ skipped
- 신규 테스트가 무엇을 커버하는지 (Phase별 개수와 대상)
- 전체 소요 시간 before / after (pacing 스위치 효과)

### 5. 브리프를 벗어난 판단
브리프가 명시하지 않아 스스로 결정한 것 전부.
각 항목: 무엇을 / 왜 / DECISIONS.md 번호

### 6. 브리프가 틀렸던 부분
지시대로 하는 것이 불가능하거나 해로웠던 지점.
무엇이 왜 틀렸고 어떻게 우회했는지.
**이 항목이 비어 있으면 의심스럽다 — 720줄짜리 엔진을 리팩터하는데 브리프가 완벽할 리 없다.**

### 7. 보안 자체 점검
- 평문 비밀번호가 DB/로그/CSV 어디에도 없음을 확인한 방법:
- 인증 없이 접근 가능한 라우트 전체 목록:
- 타계정 데이터 접근 시 404를 반환함을 확인한 방법:
- 세션 토큰이 DB에 해시로만 저장됨을 확인한 방법:

### 8. 불변식 준수 확인
#6 (mock 완전 동작), #9/#12 (AI는 실행 명령 선택 불가),
#10 (문서 동기화), #13 (예산), #15 (계정 스코프)
각각 어떻게 지켰는지 한 줄씩.

### 9. 다음 스프린트로 넘기는 것
Sprint 10(Role/Employee 분리)을 설계할 때 알아야 할 사실.
특히 파이프라인 데이터화 과정에서 발견한, 역할을 데이터로 추가할 때의 제약이나 함정.
(Sprint 10은 Role/Employee를 분리하고 역할을 템플릿 데이터로 완전히 옮긴다)

### 10. 확신이 낮은 부분
동작은 하지만 설계가 미심쩍은 곳.
리뷰어가 특별히 봐야 할 파일과 이유.
```