좋아. 이번에는 **새 `CLAUDE.md`의 작업 방식과 Sprint 10 브리프가 완전히 일치하도록** 다시 정리하는 게 맞아.

특히 아래를 반영했어.

* **Sprint 10부터 개발 방식 변경** 명시
* “긴 프롬프트 1개 → 장시간 자율 실행 → 검증” 방식 유지
* 저장소에 이미 있는 문서를 프롬프트에 중복해서 복사하지 않는 원칙 추가
* 테스트 `220+`를 목표 숫자로 강제하지 않음
* `default_profile` immutable 조건 보강
* singleton race condition 검토 추가
* 역할 하드코딩 검증을 단순 substring 검색이 아닌 **실제 코드 분기/의존성 검증**으로 변경
* Phase 5와 Appendix의 항목 불일치 정리
* 완료 보고에 **“개발 방식 변경 및 토큰 효율 개선”**을 명시적으로 기록하도록 추가

# Sprint 10 — Phase B: Role / Employee 분리

조직을 **무한 확장 가능한 데이터 구조**로 만드는 스프린트다.

현재 Commander에서는 사실상:

```text id="b4h7az"
Agent = Role
```

에 가깝다.

PM 한 명은 PM 역할이고, Engineer 한 명은 Engineer 역할이다.

이 전제에서는 V1.1의 목표인:

```text id="68q3vj"
CTO
Backend Engineer
Frontend Engineer
한 역할에 여러 Employee
미래의 Designer / QA / DevOps / Security
```

를 안전하게 확장할 수 없다.

이 스프린트의 목적은 기능을 많이 추가하는 것이 아니다.

**조직의 구조를 역할과 사람으로 분리하고, 이후 Sprint 11~18이 이 구조 위에서 자연스럽게 확장되도록 만드는 것**이 목적이다.

---

# 0. Sprint 10 개발 방식 변경

Sprint 10부터 Commander의 구현 방식은 기존보다 **큰 단위의 자율 실행 방식**으로 전환한다.

### 변경 이유

기존 방식은 Sprint의 세부 내용을 프롬프트에 반복적으로 설명하고 작은 단위로 나누어 전달하면서, Claude Code가 이미 저장소에 존재하는 아키텍처와 문서를 다시 읽고 반복해서 판단하는 비용이 커지는 문제가 있었다.

### 변경 방법

Sprint 전체의 목표·제약·Definition of Done을 **하나의 큰 sprint brief로 전달**하고, Claude Code가 저장소의 `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `UX_SPEC.md`, `PROGRESS.txt`를 직접 읽은 뒤 **Phase 0부터 마지막 검증까지 장시간 자율적으로 수행**한다.

즉:

```text
기존
작업 → 확인 → 다음 프롬프트 → 작업 → 확인 → 다음 프롬프트

변경
큰 Sprint brief 1개
        ↓
Claude Code가 저장소 context 직접 탐색
        ↓
Phase 0~5 자율 구현
        ↓
테스트 / 브라우저 검증 / 문서화
        ↓
완료 보고
        ↓
사람 + GPT 검증
```

이 방식으로 바꾸어 **프롬프트 간 컨텍스트 중복과 불필요한 저장소 설명을 줄이고, 한 번의 구현 세션에서 더 긴 작업 흐름을 유지할 수 있게 한다.**

### 이 스프린트에서 반드시 지킬 것

* 확인을 위해 중간에 멈추지 마라.
* 저장소에 이미 존재하는 문서의 내용을 프롬프트에 다시 요구하지 마라.
* 불확실한 부분은 합리적으로 판단하고 `docs/DECISIONS.md`에 기록한 뒤 계속 진행하라.
* 각 Phase는 내부 체크포인트일 뿐, 사용자와 대화하는 필수 중단점이 아니다.
* Sprint 전체를 하나의 연속된 구현 작업으로 수행한다.
* 단, 각 Phase 완료 시 commit / `PROGRESS.txt` / 테스트 등을 통해 내부 상태를 남겨라.
* 실제로 검증하지 않은 것은 완료했다고 주장하지 마라.

---

# 1. 이 스프린트의 목표

Sprint 10이 끝나면 다음이 성립해야 한다.

### Role

템플릿이 소유하는 불변의 **직위**다.

Role은:

* 계약
* 도구
* 권한
* workflow 위치
* harness
* 기본 프로필

을 정의한다.

### Employee

CEO가 소유하는 **사람/인스턴스**다.

Employee는:

* 이름
* 모델
* 개인 프로필
* 현재 상태

를 가진다.

즉:

```text id="ic4y1f"
Role
  ↓
Position / Job Definition

Employee
  ↓
Person occupying that position
```

이 분리를 통해 Sprint 11 이후에는:

```text id="s6ikz8"
Backend Engineer
 ├── Kim
 ├── Lee
 └── ...
```

같은 구조가 가능해져야 한다.

---

# 2. 이 스프린트 종료 후 CEO가 보는 변화

CEO에게 새로운 기능이 많이 생기는 스프린트가 아니다.

핵심적인 CEO-facing 변화는:

```text id="rph0k7"
Employees
 ├── Leadership
 │    ├── PM
 │    └── Reviewer
 │
 └── Engineering
      └── Engineer
```

처럼 **Role과 Employee가 구분되어 보이는 것**이다.

채용 기능은 아직 만들지 않는다.

CTO도 아직 만들지 않는다.

실제 조직 확장은 Sprint 11에서 한다.

이번 Sprint는 그 기반을 만드는 작업이다.

---

# 3. 반드시 먼저 읽을 것

Claude Code는 아래 문서의 내용을 프롬프트에서 다시 설명받는 것이 아니라 **저장소에서 직접 읽어야 한다.**

## 문서

1. `CLAUDE.md`

   * Organization Model
   * Hard Architecture Rules #1~#18
   * 특히 #12 Tools
   * #16 Roles are data
   * #18 No silent failure
   * Working Model / autonomous sprint execution

2. `docs/ARCHITECTURE.md`

   * §1.2 Role vs Employee
   * §1.3 Company Templates
   * §4.1 Stage sequence
   * 관련 As-Built 내용

3. `docs/design/UX_SPEC.md`

   * §5.4 Employees

4. `docs/DECISIONS.md`

   * #128 이후
   * 특히 Sprint 9의 인증 / 복구 / pipeline 데이터화 관련 결정

5. `PROGRESS.txt`

6. Sprint 9 완료 보고

## 주요 코드

```text id="0p6zaw"
apps/api/app/templates/software_company.py

apps/api/app/modules/agent_runtime/
apps/api/app/modules/workflow_engine/engine.py
apps/api/app/modules/prompt_builder/

apps/api/app/core/db_models.py
apps/api/app/core/lifecycle/agent_states.py

apps/dashboard/app/company/[id]/employees/
apps/dashboard/components/EmployeeCard.tsx
```

필요한 경우 위 경로 외의 실제 사용처도 repository search를 통해 찾아라.

**위 목록이 모든 영향 파일의 목록이라고 가정하지 마라.**

---

# 4. 승인된 설계 결정 — 재논의 금지

## 4.1 Sprint 9 잔여 문제 — Phase 0 최우선

### (a) 승인 500의 원인은 코드 버그가 아니다

CEO 환경에서:

```text
POST /api/approvals/{id}/decision
```

가 500을 반환하고 브라우저가 CORS 문제처럼 표시한 현상이 있었다.

원인은 **8001 포트에 남아 있던 오래된 API 프로세스**였다.

Sprint 9 코드/스키마가 반영된 서버를 새로 띄운 후 승인은 정상 동작했다.

따라서 이 Sprint에서 승인 500 자체를 다시 조사하지 마라.

목표는 **낡은 프로세스나 스키마 불일치가 다시 제품 버그처럼 보이지 않도록 진단 가능성을 강화하는 것**이다.

---

### (b) 전역 예외 핸들링

예상치 못한 서버 예외도:

```text id="i3v1l6"
CORS 헤더가 포함된 JSON 500
```

으로 반환되어야 한다.

브라우저가 이해할 수 있는 사용자용 메시지를 반환한다.

내부 stack trace는 응답에 포함하지 않는다.

전체 traceback은 서버 로그에 남긴다.

---

### (c) API 호스트명/포트 통일

현재 개발 환경에 호스트명/포트가 여러 곳에 흩어진 문제가 있다.

다음은 동일한 값으로 통일한다.

```text id="m6r2ps"
NEXT_PUBLIC_API_URL
cors_origins
Makefile
README
.env.local.example
```

기준값:

```text
http://localhost:8000
```

`localhost`와 `127.0.0.1`을 혼용하지 않는다.

README에는 오래된 API 프로세스가 남아있는 상황을 피하기 위한 실행/재기동 방법을 명확하게 남긴다.

---

### (d) 미션 취소 UI

API에는 이미:

```text
POST /api/tasks/{id}/cancel
```

가 존재한다.

그러나 dashboard에 cancel action이 완성되어 있지 않다.

이번 Sprint에서:

```text id="cqy96k"
API function
hook
button
confirmation
error handling
```

을 구현한다.

진행 중 Mission에만 보인다.

완료된 Mission에는 보이지 않는다.

---

### (e) 취소 시 current_task_id 정리

`cancel_task`는 취소된 Employee의 `current_task_id`를 반드시 비운다.

그렇지 않으면 이후 Message routing이 과거 Mission에 연결될 수 있다.

취소 경로와 orphan recovery 경로의 Employee cleanup 동작은 일관되어야 한다.

---

# 5. 불변식 #18 — 조용한 실패 금지

`CLAUDE.md`의 #18을 실제 코드에도 반영한다.

> **CEO의 모든 액션은 결과를 말한다.**
>
> CEO가 누른 버튼은 성공했거나, 실패한 이유를 화면에 남긴다.
> 조용히 아무 일도 일어나지 않는 상태는 허용되지 않는다.

Dashboard의 모든 mutation을 전수 조사한다.

예:

```text id="dfbb0t"
useDecideApproval
cancelTask
profile mutation
company mutation
mission mutation
settings mutation
```

등.

`onError`가 없거나 equivalent error handling이 없는 mutation은 오류를 CEO에게 표면화하도록 수정한다.

---

# 6. RoleSpec — 역할을 1급 데이터로 승격

`software_company.py`의 역할 정의를 `RoleSpec`으로 승격한다.

```python
from dataclasses import dataclass
from typing import Mapping, Any

@dataclass(frozen=True)
class RoleSpec:
    key: str
    title: str
    category: str
    singleton: bool
    contract: str
    model_ref: str
    harness: str
    tools: tuple[str, ...]
    permissions: tuple[str, ...]
    default_profile: Mapping[str, Any]
```

## 6.1 RoleSpec 불변성

`@dataclass(frozen=True)`를 사용한다.

특히 `default_profile`은 nested mutable `dict`를 직접 노출하지 않는 방식으로 **실질적으로 immutable하게 취급**한다.

RoleSpec 내부 데이터를 Employee가 직접 수정할 수 있는 경로를 만들지 마라.

---

## 6.2 fields

### key

역할의 stable identifier.

예:

```text id="v4jz8v"
pm
engineer
reviewer
```

### title

CEO-facing 직위명.

### category

최소:

```text id="n8v9df"
leadership
worker
```

### singleton

Leadership만 `True`.

이번 템플릿에서는:

```text id="c3t8ye"
PM        → True
Reviewer  → True
Engineer  → False
```

CTO는 Sprint 11에서 추가한다.

### contract

역할의 출력 계약.

예:

Reviewer의 trailing Verdict 등.

### model_ref

역할의 기본 논리 모델.

모델 참조는 여기 하나만 소유한다.

### harness

현재:

```text id="tv55v2"
one_shot
```

Sprint 16 이후:

```text id="l2f96z"
tool_loop
```

등으로 확장할 수 있다.

### tools

현재는 모두:

```python
()
```

이다.

구조만 만든다.

도구 grant는 오직 template → Role 방향으로만 가능하다.

### permissions

조직 행동의 선언이다.

예:

```text id="4b9mhy"
assign_mission
request_ceo_decision
```

OS 권한이나 shell permission이 아니다.

Sprint 10에서는 선언만 한다.

Enforcement는 Sprint 12 이후다.

### default_profile

Employee 생성 시 사용하는 초기 프로필 데이터다.

RoleSpec의 다른 필드와 마찬가지로 template-owned immutable data로 취급한다.

---

# 7. 중복 Role source 제거

기존의:

```text id="p6xw7z"
TEMPLATE.roles
model_ref_for_role
PIPELINE
roles_by_key
```

등이 동일한 사실을 중복 소유하고 있다면 정리한다.

특히 모델 참조가:

```text id="2h2o5p"
RoleSpec.model_ref
model_ref_for_role()
```

양쪽에 존재하는 구조는 금지한다.

**RoleSpec이 역할 정의의 canonical source가 되어야 한다.**

다른 자료구조는 필요하다면 RoleSpec에서 파생되어야 한다.

---

# 8. StageSpec과 RoleSpec

`StageSpec`은 Workflow의 실행 단위를 정의한다.

Role은 조직 직위다.

둘의 책임을 혼동하지 마라.

예를 들어 stage는:

```text id="u6h7fr"
kind = plan / produce / review
role_key = ...
```

등의 workflow 정보를 가질 수 있다.

중요한 것은:

```text id="16f3am"
stage
  ↓
role definition
  ↓
employee resolution
```

이라는 방향이다.

Workflow engine이 특정 역할 이름을 보고 실행 logic을 선택해서는 안 된다.

---

# 9. Employee — AgentORM의 의미 변경

`AgentORM`의 class name은 이번 Sprint에서 변경하지 않는다.

대규모 ORM rename은 Out of Scope다.

그러나 의미상 `AgentORM`은 Employee다.

## 9.1 role → role_key

기존:

```text id="1nq4uo"
AgentORM.role
```

을:

```text id="4s5b80"
AgentORM.role_key
```

로 변경한다.

Alembic migration을 작성한다.

`RoleSpec.key`를 참조하는 의미를 명확히 한다.

---

## 9.2 한 Role에 여러 Employee 허용

Worker Role은 같은 role key를 가진 Employee를 여러 명 가질 수 있어야 한다.

이번 Sprint에서는 실제 채용 UI를 만들지 않는다.

그러나 service/repository/query 구조는 이미:

```text id="if5kyk"
one role
    ↓
many employees
```

를 지원할 수 있어야 한다.

역할별 단일 Employee를 가정하는 조회 코드를 찾아 제거한다.

---

# 10. Singleton enforcement

`singleton=True` Role에 대해서만 복수 Employee 생성을 막는다.

예:

```text id="eg83sv"
PM
 └── first Employee ✅

PM
 ├── first Employee
 └── second Employee ❌
```

Worker Role:

```text id="8d7knc"
Engineer
 ├── Employee A ✅
 ├── Employee B ✅
 └── Employee C ✅
```

가 가능해야 한다.

## 10.1 Enforcement

서비스 레이어에서 사용자 의미가 있는 오류를 반환한다.

단, **동시 요청 race condition 가능성은 반드시 검토한다.**

다음 시나리오를 고려한다.

```text id="7r6pje"
Request A → no employee found
Request B → no employee found

A → create
B → create
```

현재 스코프에서 DB-level uniqueness가 필요한지 판단한다.

필요하다면 구현하고, 구현하지 않는다면 왜 서비스 레이어 enforcement로 충분한지 `docs/DECISIONS.md`에 남긴다.

불필요한 과설계는 하지 않는다.

---

# 11. Company 생성

회사 생성 시 초기 Employee는 RoleSpec에서 파생되어야 한다.

RoleSpec:

```text id="yq8y32"
PM
Engineer
Reviewer
```

가 있으면 founding employees를 생성하는 코드가 이 데이터를 사용해야 한다.

별도의 역할별 initialization list를 추가로 유지하지 마라.

---

# 12. Role → Employee resolution

현재 엔진이:

```python
agents[stage.role_key]
```

처럼 역할당 하나의 Agent를 선택한다면 이를 제거한다.

## 12.1 Sprint 10 선택 규칙

현재 스프린트에서는 다음으로 고정한다.

> 해당 Role의 Employee 중 **idle 상태인 사람**을 우선 선택한다.
> 여러 명이면 **가장 오래 배정받지 않은 Employee**를 선택한다.
> idle이 없다면 전체 Employee 중 **가장 오래 배정받지 않은 Employee**를 선택한다.

이 규칙은 하나의 명시적인 resolver 함수에 둔다.

예:

```text id="1g1tbt"
resolve_employee_for_role(...)
```

실제 함수명은 코드 구조에 맞게 판단한다.

중요한 것은 **선택 규칙이 한 곳에 있어야 한다는 것**이다.

Sprint 12에서 PM의 명시적 Employee assignment로 변경될 때 다른 엔진 코드가 아니라 이 선택 계층이 교체되도록 만든다.

---

# 13. 선택 규칙의 결정론

같은 입력이면 같은 Employee가 선택되어야 한다.

동률을 명확하게 정의한다.

예:

```text id="yoag7q"
last_assigned_at
→ created_at
→ stable primary key
```

등.

실제 필드는 repository의 기존 모델을 확인한 후 가장 적절한 결정 기준을 선택한다.

새 필드를 만들 필요가 있다면 근거를 기록한다.

동률 처리 규칙은 반드시 테스트로 고정한다.

---

# 14. 선택 결과는 Event로 남긴다

Employee resolution은 조직적으로 중요한 의사결정이다.

따라서 선택 결과를 이벤트로 남긴다.

이벤트는 최소한 시스템이 다음을 설명할 수 있도록 해야 한다.

```text id="9r7p7r"
어떤 Role이었는가?
누가 선택되었는가?
선택 시점은 언제인가?
왜 그 Employee가 선택되었는가?
```

가능한 경우 선택된 Employee뿐 아니라 resolver가 적용한 규칙도 observable하게 만든다.

---

# 15. 불변식 #16 — 역할 이름을 코드에서 제거

Engine, Prompt Builder, Frontend에서 역할 이름을 기준으로 한 하드코딩 분기를 제거한다.

금지:

```python id="xrrrfb"
role == "engineer"
role_key == "pm"
role == "reviewer"
```

또한:

```python id="qbv9mg"
TEMPLATE.roles[0]
TEMPLATE.roles[1]
TEMPLATE.roles[2]
```

같은 위치 기반 접근도 제거한다.

---

# 16. 허용되는 예외

다음은 허용한다.

### Template 자체

Template이 자기 데이터를 조립하기 위해:

```text id="w0hd5e"
PM_KEY
ENGINEER_KEY
REVIEWER_KEY
```

같은 상수를 사용하는 것은 허용한다.

단, 이 상수들이 engine/module behavior를 분기시키는 용도로 흘러가서는 안 된다.

### Stage kind

다음은 허용한다.

```text id="v1g36p"
plan
produce
review
```

이는 organizational role이 아니라 workflow semantics다.

---

# 17. 불변식 #16 자동 검증

단순한 substring 검사로 구현하지 마라.

예를 들어:

```python
assert "engineer" not in source
```

같은 테스트만 만들지 않는다.

그런 검사는:

* 주석
* 문서 문자열
* fixture
* 로그 메시지
* 테스트 설명

때문에 false positive를 만들 수 있다.

대신 실제로:

```text id="i1n5ld"
role name을 기준으로 engine behavior가 분기되는 코드
role name을 기준으로 prompt logic이 분기되는 코드
role position/order에 의존하는 code
```

가 존재하지 않는다는 것을 검증한다.

가능하면 AST 또는 정적 코드 패턴 검사를 사용한다.

테스트의 목적은:

> "해당 문자열이 파일에 전혀 없다"

가 아니라:

> **"engine/prompt behavior가 특정 Role identity에 하드코딩되어 있지 않다"**

를 보장하는 것이다.

---

# 18. Roles API

읽기 전용 API를 추가한다.

```text
GET /api/projects/{id}/roles
```

이 API는 해당 Company의 template이 제공하는 Role 목록을 CEO에게 보여준다.

노출 필드:

```text id="3xamv8"
key
title
category
singleton
description
```

다음은 외부에 노출하지 않는다.

```text id="8b6jhr"
contract
tools
permissions
```

Role은 template-owned data이므로 CEO가 수정하는 write route는 만들지 않는다.

---

# 19. Employees 화면

`docs/design/UX_SPEC.md §5.4`를 따른다.

예:

```text id="e0h05x"
Leadership
  PM        · Jun  · Claude Sonnet
  Reviewer  · Tae  · Claude Sonnet

Engineering
  Engineer
    · Kim · Claude Sonnet
```

UI에서는 반드시:

```text id="24z2r1"
Role = 조직의 자리
Employee = 그 자리에 앉은 사람
```

이라는 구분이 읽혀야 한다.

### 금지

이번 Sprint에서는 채용 UI를 만들지 않는다.

Leadership에 추가 employee를 만드는 버튼을 보여주지 않는다.

"hidden means absent" 원칙을 지킨다.

기존 Employee profile edit 기능은 유지한다.

---

# 20. Mock mode

Sprint 10에서 추가된 모든 구조는:

```text id="0mtfqc"
COMMANDER_PROVIDER=mock
API keys = 0
```

환경에서 동작해야 한다.

특히:

```text id="k9g3om"
Role resolution
Employee state
singleton enforcement
workflow
approval
cancel
```

등이 mock에서 깨지면 안 된다.

전체 기본 파이프라인:

```text id="l9j2n7"
Company
→ Mission
→ PM
→ Engineer
→ Reviewer
→ Approval
→ Merge
```

가 계속 완주 가능해야 한다.

---

# 21. 동작 변화 0

Sprint 10은 구조 리팩터링이다.

CEO가 보는 기존 pipeline은 변하지 않는다.

```text id="x5cw2q"
PM
 ↓
Engineer
 ↓
Reviewer
 ↓
CEO Decision
 ↓
Merge
```

동일해야 한다.

이번 Sprint에서 CTO를 추가하지 않는다.

새로운 planning layer를 추가하지 않는다.

Agent Harness를 추가하지 않는다.

Project Memory를 추가하지 않는다.

---

# 22. 테스트 원칙

기존 테스트는 가능한 한 유지한다.

기존 테스트가 실패하면 반드시 다음을 구분한다.

### (i) 실제 동작 변화

Sprint 10의 설계 변경으로 동작이 정말 바뀐 경우.

→ 정상적인 테스트 수정일 수 있다.

### (ii) 구현 세부 결합

동작은 동일하지만 테스트가:

```text id="6d5jxb"
AgentORM.role
agents["engineer"]
TEMPLATE.roles[0]
```

같은 내부 구현에 직접 결합되어 실패한 경우.

→ 테스트 건강성 문제로 보고한다.

기존 테스트를 수정한다면 **각 변경 이유를 완료 보고에 기록한다.**

---

# 23. 테스트 숫자를 목표로 만들지 마라

기존 baseline은:

```text id="n9g83c"
194 tests
```

이다.

Sprint 10은 의미 있는 테스트를 추가해야 하지만:

```text id="kqky4m"
220+
```

같은 숫자를 KPI로 맞추기 위해 테스트를 인위적으로 쪼개거나 중복 assertion을 추가하지 않는다.

테스트 수는 **결과로 기록한다.**

테스트가 실제로 커버해야 하는 것:

```text id="j4gc1c"
RoleSpec 무결성
Role singleton semantics
Employee role_key
복수 worker
singleton rejection
employee resolver
idle 우선
동률 처리
resolution event
role hardcoding guard
roles API
mutation error surfacing
cancel cleanup
```

이다.

---

# 24. 테스트 전용 Multi-Employee Template

실제 `software_company` template을 변경하여 테스트하지 않는다.

별도의 테스트 전용 template을 만든다.

예:

```text id="g3x67o"
role:
  engineer
employees:
  engineer-A
  engineer-B
```

이 template을 사용하여:

* 같은 Role에 여러 Employee가 존재한다.
* idle 우선 선택
* 오래된 assignment 우선
* 동률 처리
* 선택 결과 event

가 결정론적으로 동작하는지 검증한다.

---

# 25. Phase별 작업

Claude Code는 **Phase 사이에서 확인을 요청하지 말고** 아래 전체를 순서대로 수행한다.

---

## Phase 0 — 진단 가능성 + Sprint 9 잔여 문제

### 0.1

`PROGRESS.txt`를 Appendix A로 리셋한다.

### 0.2

포트/호스트명을 8000 기준으로 통일한다.

대상:

```text
NEXT_PUBLIC_API_URL
cors_origins
Makefile
README
.env.local.example
```

README에 오래된 API 프로세스를 남기지 않는 실행/재기동 방법을 정리한다.

### 0.3

서버 기동 시:

```text id="x5sz87"
git SHA
Alembic head revision
현재 DB revision
```

을 확인할 수 있도록 한다.

DB가 head와 다르면:

* startup failure
* 또는 매우 명확한 warning

중 하나가 되어야 한다.

### 0.4

전역 exception handler를 추가한다.

예상치 못한 오류:

```text id="5xxm22"
JSON 500
CORS header
CEO-safe message
server traceback
```

이어야 한다.

### 0.5

`CLAUDE.md`에 #18 반영.

### 0.6

Dashboard mutation 전수 조사.

`onError` 또는 동등한 오류 표면화가 없는 모든 mutation을 수정한다.

### 0.7

Mission cancel UI 구현.

### 0.8

`cancel_task` 이후 Employee의 `current_task_id = None`.

회귀 테스트 추가.

### 0.9

commit:

```text id="d4qhvv"
fix(sprint9-followup): decision 500, error surfacing, cancel UI
```

push까지 한다.

---

# 26. Phase 1 — RoleSpec 정의

### 1.1

frozen `RoleSpec` 정의.

### 1.2

`software_company.py`의 세 Role을 RoleSpec으로 재작성.

### 1.3

중복 Role source 제거.

### 1.4

StageSpec이 Role 정의를 올바르게 참조하도록 정리.

### 1.5

`tools` / `permissions` 선언.

현재 실제 tool grant는 없다.

### 1.6

테스트:

* RoleSpec immutability
* singleton semantics
* canonical source
* model_ref duplication 방지
* default_profile immutability

등을 충분히 커버한다.

### 1.7

commit:

```text id="pr2n3a"
refactor(template): RoleSpec as first-class data
```

push.

---

# 27. Phase 2 — Employee schema

### 2.1

`AgentORM.role` → `role_key`.

Alembic migration.

### 2.2

복수 Employee 조회 가능 구조 정리.

### 2.3

singleton enforcement.

### 2.4

Company founding employees 생성이 RoleSpec 기반이 되도록 정리.

### 2.5

테스트:

* migration
* role_key
* singleton rejection
* multiple worker employees
* role query behavior
* race condition consideration

### 2.6

commit:

```text id="d9f2s3"
feat(employees): role_key schema and singleton enforcement
```

push.

---

# 28. Phase 3 — Role → Employee resolution

### 3.1

선택 규칙을 단일 resolver로 구현.

### 3.2

Engine이 resolver를 사용하도록 변경.

### 3.3

선택 결과를 Event로 발행.

### 3.4

테스트 전용 multi-employee template.

### 3.5

테스트:

* idle 우선
* assignment age
* no-idle fallback
* tie-breaking
* deterministic behavior
* event emission

### 3.6

commit:

```text id="03r7bq"
feat(workflow): role-to-employee resolution
```

push.

---

# 29. Phase 4 — #16 enforcement + UI

### 4.1

Engine / Prompt Builder의 Role-specific hardcoding 제거.

### 4.2

Frontend의 Role-specific presentation hardcoding 제거.

색상/아이콘/라벨이 Role identity에 직접 결합되어 있다면 data-driven rendering으로 변경한다.

### 4.3

자동 검증 추가.

단순 substring 검색이 아니라:

```text id="d7g6tc"
role-specific behavioral branch
position-based access
hardcoded role dependency
```

를 검증한다.

### 4.4

Roles API.

### 4.5

Employees UI grouping.

### 4.6

```bash id="h4frpp"
pnpm typecheck
pnpm build
```

### 4.7

commit:

```text id="5qgs9b"
feat(org): roles are data, employees are instances
```

push.

---

# 30. Phase 5 — Final verification

### 5.1

전체:

```bash id="pqgy7e"
make test
```

### 5.2

기존 194 테스트가 모두 통과하는지 확인한다.

실패가 있다면 각각:

```text id="5bgl5v"
실제 동작 변경
vs
구현 세부 결합
```

으로 분류한다.

### 5.3

브라우저에서 직접 확인:

```text id="sgapn8"
Company creation
→ Mission creation
→ PM
→ Engineer
→ Reviewer
→ Approval
→ Merge
→ Cancel
→ Employees
```

### 5.4

최종 `CLAUDE.md` 갱신.

이번 Sprint에서 실제 구현된 내용을 반영한다.

### 5.5

`docs/ARCHITECTURE.md` As-Built 갱신.

특히:

```text id="5x2ytm"
Role / Employee
employee resolution
role data model
```

을 반영한다.

### 5.6

`docs/design/UX_SPEC.md §5.4` 갱신.

### 5.7

`docs/DECISIONS.md` 갱신.

특히:

* singleton race condition 판단
* implementation tradeoff
* 테스트 수정 이유
* 역할 hardcoding 검증 방식
* Sprint 10에서 발견했지만 이후 Sprint로 넘긴 사항

을 기록한다.

### 5.8

최종 `PROGRESS.txt`를 정확한 상태로 갱신한다.

### 5.9

최종 commit + push.

### 5.10

원격 HEAD가 최종 commit과 일치하는지 확인한다.

---

# 31. Out of Scope

이번 Sprint에서는 다음을 구현하지 않는다.

* CTO 역할 추가 → Sprint 11
* 실제 채용 UI → Sprint 11
* 실제 multi-employee creation → Sprint 11
* Employee firing → Sprint 11
* PM ↔ CTO planning → Sprint 12
* Project Specification → Sprint 12
* Requirement Discovery → Sprint 12
* CEO ↔ PM 지속 대화 → Sprint 13
* PM Report → Sprint 13
* decision authority classification → Sprint 13
* Render UI shell → Sprint 14
* sidebar restructure → Sprint 14
* widget dock → Sprint 15
* Agent Harness → Sprint 16
* tool loop → Sprint 16
* self-correction → Sprint 17
* Project Memory → Sprint 18
* second company template → V1.1 전체에서 제외
* `AgentORM` → `EmployeeORM` 대규모 rename
* permissions enforcement → 이후 Sprint

이번 Sprint에서 미래 기능을 위해 **extension point를 만드는 것**은 허용한다.

하지만 미래 기능 자체를 구현하지 않는다.

---

# 32. Definition of Done

## 1. Startup diagnostics

API 기동 로그에:

```text id="s0zvji"
git SHA
Alembic head
current DB revision
```

이 보인다.

DB가 head와 다르면 failure 또는 명확한 warning이 발생한다.

---

## 2. Global error visibility

예상치 못한 서버 예외를 일부러 발생시켰을 때:

* API는 CORS가 붙은 JSON 500을 반환
* 내부 traceback은 서버 로그
* CEO 화면에는 사람이 이해할 수 있는 오류가 표시

된다.

### 2a. Host / port consistency

다음이 모두 동일한 host/port를 사용한다.

```text id="v34d7z"
NEXT_PUBLIC_API_URL
cors_origins
Makefile
README
.env.local.example
```

기준:

```text
http://localhost:8000
```

---

## 3. Mission cancel

진행 중 Mission에 cancel이 나타난다.

완료된 Mission에는 없다.

실제 클릭하여 동작을 확인한다.

---

## 4. Employee cleanup

취소된 Mission의 담당 Employee는:

```text id="xok3co"
current_task_id = None
```

이다.

---

## 5. RoleSpec canonical source

RoleSpec이 역할 정의의 유일한 source다.

특히:

```text id="4ygz6m"
model reference
title
contract
harness
role metadata
```

가 다른 source에 중복되지 않는다.

---

## 6. Singleton enforcement

`singleton=True` Role에 두 번째 Employee 생성을 시도하면 서비스 레이어에서 거부된다.

race condition 가능성도 검토되어 있어야 한다.

---

## 7. Multi-employee resolution

테스트 전용 template에서 동일 Role에 Employee 2명을 두었을 때:

* idle 우선
* 오래된 assignment 우선
* 동률 deterministic
* 선택 결과 event

가 모두 검증된다.

---

## 8. #16 enforcement

Engine / Prompt Builder에 특정 Role identity에 결합된 분기가 없다.

자동 검증으로 이를 검사한다.

단순 substring 검색으로 false positive를 만들지 않는다.

---

## 9. Roles API

```text id="efp7u7"
GET /api/projects/{id}/roles
```

가 CEO-facing 필드만 반환한다.

노출 금지:

```text id="1nhg0b"
contract
tools
permissions
```

---

## 10. Employees UI

Leadership / Worker가 구분되어 보인다.

Role / Employee도 구분되어 읽힌다.

채용 UI는 존재하지 않는다.

---

## 11. Existing behavior unchanged

기존 흐름:

```text id="4thfyo"
Company
→ Mission
→ PM
→ Engineer
→ Reviewer
→ Approval
→ Merge
```

가 이전과 동일하게 동작한다.

---

## 12. Mock mode

API key 0 / mock provider에서 전체 기존 pipeline이 완주한다.

---

## 13. Tests

`make test`가 green이어야 한다.

기존 194개 테스트는 가능한 한 전부 유지되어야 하며, 수정한 테스트는 이유를 모두 보고한다.

신규 테스트 개수 자체는 KPI가 아니다.

테스트 수는 실제 결과로 기록한다.

---

## 14. Dashboard build

```bash id="1q0ncb"
pnpm typecheck
pnpm build
```

green.

---

## 15. Remote HEAD

최종 commit이 remote HEAD와 일치한다.

---

# 33. Appendix A — PROGRESS.txt

```text
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 10 — Phase B: Role / Employee 분리
 Overall: 0/45 items · 0%
 Now working on: -
 Last update: -
================================================

PHASE 0 — 진단 가능성 + Sprint 9 잔여 문제          (0/9)
[ ] 0.1 PROGRESS.txt 리셋
[ ] 0.2 포트/호스트명 8000 통일 + README 실행 안내
[ ] 0.3 git SHA + Alembic diagnostics
[ ] 0.4 global exception handler
[ ] 0.5 invariant #18
[ ] 0.6 dashboard mutation error surfacing
[ ] 0.7 mission cancel UI
[ ] 0.8 cancel_task current_task_id cleanup
[ ] 0.9 commit + push

PHASE 1 — RoleSpec 정의                             (0/7)
[ ] 1.1 RoleSpec frozen dataclass
[ ] 1.2 software_company RoleSpec migration
[ ] 1.3 canonical Role source
[ ] 1.4 StageSpec integration
[ ] 1.5 tools / permissions structure
[ ] 1.6 RoleSpec tests
[ ] 1.7 commit + push

PHASE 2 — Employee schema                           (0/6)
[ ] 2.1 AgentORM.role -> role_key + migration
[ ] 2.2 multi-employee query paths
[ ] 2.3 singleton enforcement
[ ] 2.4 RoleSpec-based founding roster
[ ] 2.5 schema / singleton / multi-worker tests
[ ] 2.6 commit + push

PHASE 3 — Role -> Employee resolution               (0/6)
[ ] 3.1 resolver
[ ] 3.2 engine integration
[ ] 3.3 resolution event
[ ] 3.4 test multi-employee template
[ ] 3.5 deterministic selection tests
[ ] 3.6 commit + push

PHASE 4 — #16 enforcement + UI                      (0/7)
[ ] 4.1 engine / prompt hardcoding removal
[ ] 4.2 frontend role presentation data-driven
[ ] 4.3 automated behavioral hardcoding guard
[ ] 4.4 Roles API
[ ] 4.5 Employees grouping
[ ] 4.6 typecheck + build
[ ] 4.7 commit + push

PHASE 5 — verification / docs / report              (0/10)
[ ] 5.1 make test
[ ] 5.2 existing 194 tests verification
[ ] 5.3 classify modified existing tests
[ ] 5.4 browser: company -> mission completion
[ ] 5.5 browser: employees -> approval -> cancel
[ ] 5.6 CLAUDE.md
[ ] 5.7 ARCHITECTURE.md
[ ] 5.8 UX_SPEC.md
[ ] 5.9 DECISIONS.md
[ ] 5.10 final commit + push + remote HEAD
================================================
```

---

# 34. Appendix B — 완료 보고 형식

Sprint 완료 시 아래 형식으로 보고한다.

```text id="9h3v8p"
## Sprint 10 완료 보고

### 1. 커밋
- 최종 commit SHA
- remote HEAD
- 일치 여부
- commit 목록

### 2. 개발 방식 변경
- 왜 Sprint 10부터 large autonomous sprint 방식으로 변경했는가
- 무엇을 변경했는가
- context / prompt duplication 측면에서 무엇이 개선되었는가
- 실제 개발 흐름에서 어떤 장점이 확인되었는가

### 3. 진단 가능성
- 통일한 host / port
- 수정 파일
- startup SHA / Alembic diagnostics
- global error handler
- 의도적으로 발생시킨 예외에서 CEO 화면에 표시된 내용
- mutation error surfacing 전체 목록

### 4. DoD 15개
각 항목:

- PASS
- FAIL
- UNVERIFIED

중 하나.

브라우저로 확인한 경우:

- 무엇을 클릭했는지
- 무엇이 나타났는지

를 한 줄로 기록.

curl로만 확인했다면 브라우저 검증으로 주장하지 않는다.

### 5. 테스트
- 시작: 194
- 종료: ___
- 신규 테스트 영역
- 기존 테스트 수정 목록
- 각 수정 이유:
  - (i) 실제 동작 변경
  - (ii) 구현 세부 결합

(ii)가 존재한다면 구체적인 결합 지점을 설명한다.

### 6. RoleSpec
- canonical source가 어디인가
- 중복 제거한 source
- default_profile immutable 보장 방법
- model_ref 단일 source 확인

### 7. Role → Employee resolver
- resolver 위치
- idle 우선 규칙
- assignment age 기준
- tie-breaking
- event
- multi-employee test 결과

### 8. Singleton
- 서비스 레이어 enforcement
- concurrent creation race condition 검토 결과
- DB constraint를 추가했다면 이유
- 추가하지 않았다면 이유
- DECISIONS 번호

### 9. 불변식 #16
- 제거한 hardcoded role branch 전체 목록
- 남은 예외
- 예외의 근거
- 자동 검증 방식
- 단순 substring 검사 여부
- 실제 behavioral dependency 검사 방식

### 10. 불변식 준수
- #3 reason / observability
- #6 mock
- #10 documentation sync
- #12 tool whitelist
- #16 roles are data
- #18 no silent failure

각각 한 줄.

### 11. 브리프를 벗어난 판단
- 무엇을 판단했는가
- 왜 판단했는가
- DECISIONS 번호

### 12. 브리프가 틀렸던 부분
지시대로 하는 것이 불가능하거나 해로웠던 부분.

비어 있다면 그 이유도 설명한다.

### 13. Sprint 11에 넘기는 것
- 새로운 Role 하나를 추가할 때 필요한 파일
- 현재 architecture에서 실제 변경량
- multi-employee 실사용 시 예상 문제
- CTO 추가 시 예상되는 영향

### 14. 확신이 낮은 부분
동작하지만 설계가 미심쩍은 곳.

- 파일
- 이유
- 리뷰 필요성

### 15. 최종 상태
- 테스트
- typecheck
- build
- mock E2E
- browser verification
- remote HEAD
- 전체 Sprint 상태
```

---

# 35. 마지막 실행 지침

이 Sprint brief를 받은 뒤:

1. 먼저 저장소의 현재 상태와 관련 문서를 읽는다.
2. Sprint 10 전체 작업 범위를 이해한다.
3. Phase 0부터 시작한다.
4. 각 Phase를 완료하면서 `PROGRESS.txt`와 commit을 갱신한다.
5. 중간 확인을 요청하지 않는다.
6. 불확실한 내용은 합리적으로 결정하고 `docs/DECISIONS.md`에 기록한다.
7. Sprint 10에 속하지 않는 미래 기능은 구현하지 않는다.
8. 테스트만 통과시키는 것이 아니라 실제 UI / API / runtime 동작을 검증한다.
9. 최종적으로 Appendix B 형식의 완료 보고를 작성한다.
10. 최종 commit을 push하고 remote HEAD 일치를 확인한다.

**Start Sprint 10 now.**
