# Sprint 8.5 — V1.1 Kickoff: Documentation Integration & Verification

**This sprint changes no application code.** Its output is a synchronized V1.1 documentation baseline that Sprint 9 will treat as the single source of truth.

**The three core documents have already been authored by the CTO and are provided with this brief.** Your job is not to write them. Your job is to **install them, verify every factual claim against the actual codebase, and report every discrepancy.** Sprint 9 does not begin until this is complete.

| Provided file | Destination | Action |
|---|---|---|
| `CLAUDE.md` | `/CLAUDE.md` | replace |
| `ARCHITECTURE.md` | `/docs/ARCHITECTURE.md` | replace |
| `UX_SPEC.md` | `/docs/design/UX_SPEC.md` | replace |

---

## 0. Read before doing anything

1. The three **new** documents provided with this brief — all three, completely, before touching the repo. They are a coherent set; reading one alone will mislead you.
2. The three **existing** documents they replace — you must know what is being lost.
3. `docs/DECISIONS.md` — all 127 entries.
4. `PROGRESS.txt` and `docs/prompts/sprint-8.md`.

Then read the code the new documents make claims about (Phase 2). **You are the verification layer.** These documents were written from a code review, and a review is not a proof.

## 1. Working style

- **Work autonomously.** Do not stop to ask. Where this brief leaves something open, decide, log it in `docs/DECISIONS.md`, and continue.
- **PROGRESS.txt discipline.** Reset to Appendix A. Update per item, immediately, never batched. Markers: `[ ]` `[~]` `[x] @HH:MM` `[!]reason` `+discovery`.
- **Commit + `git push` at the end of every Phase.**
- **You may not "improve" the provided documents.** You may fix factual errors about the codebase, broken cross-references, and formatting. You may **not** change scope, architecture decisions, invariants, role definitions, or the roadmap. Anything you believe is wrong at the design level goes in the completion report, not into the file.
- **Appendix B report format is mandatory.** It is the only input to the Sprint 9 review.

---

## 2. Approved decisions — do not relitigate

**2.1 Three documents, not four.** There is no separate `V1.1-SPEC.md`. A fourth document becomes a fourth source of truth and drifts. Philosophy and scope live in `CLAUDE.md`; system design in `ARCHITECTURE.md`; the CEO's experience in `UX_SPEC.md`. Precedence on conflict: ARCHITECTURE governs structure, UX_SPEC governs experience, CLAUDE governs day-to-day implementation rules.

**2.2 `docs/V1.5-SPEC-refined.md` does not exist and never will.** The V1.5 plan is superseded by V1.1. Remove every reference to it. Do not create it.

**2.3 The V1 documents are replaced, not appended to.** The new documents already carry forward what still holds (as-built module table, security model, accepted tradeoffs, status vocabulary, DecisionCard anatomy, template-expansion risk analysis). If something valuable from the old versions was dropped, **do not silently re-add it** — report it.

**2.4 The `situation` module is not deleted.** `UX_SPEC` §3.2 removes the standalone Situation Report *UI block* and repurposes the backend capability as the PM conversation's opening report. That is Sprint 13. Touch no code this sprint.

**2.5 Invariants #11–#17 are final.** Stated in `CLAUDE.md` §4, referenced throughout the other two. If the codebase already violates one, **report it, do not fix it** — fixes are scheduled into Sprint 9.

**2.6 Documentation only.** Not one line of `apps/`, `packages/`, `scripts/`, or `alembic/`. Not even a typo fix. Bugs you find are findings, not tasks.

---

## 3. Phases

### Phase 0 — Baseline
- 0.1 Read all six documents (three new, three old) end to end
- 0.2 Read `docs/DECISIONS.md` in full
- 0.3 Record current state: HEAD SHA, `git status` clean?, `make test` result (must be 157 passed / 4 skipped — if not, that is your first finding)
- 0.4 Reset `PROGRESS.txt` to Appendix A
- 0.5 Commit + push: `chore(sprint8.5): progress checklist for V1.1 kickoff`

### Phase 1 — Install the documents
- 1.1 Replace `/CLAUDE.md`
- 1.2 Replace `/docs/ARCHITECTURE.md`
- 1.3 Replace `/docs/design/UX_SPEC.md`
- 1.4 Confirm no other file duplicates their content (a stale copy becomes a second source of truth)
- 1.5 Commit + push: `docs(v1.1): install V1.1 documentation baseline`

### Phase 2 — Verify every factual claim against the code  ★ the real work

For each item: record **confirmed** / **wrong (what the code actually does)** / **cannot determine**, with file:line evidence.

**2.1 As-built module table** (`ARCHITECTURE.md` §6.1) — for each of the ~20 modules, confirm both the responsibility description and the ✅/⚠️/🔲 marker.

**2.2 The five structural debt items** (`ARCHITECTURE.md` §6.4), verified concretely:
- (a) orphaned missions — is there genuinely no recovery in `main.py`'s lifespan, and no cancel route?
- (b) budget — does anything enforce spend, or only record it?
- (c) detached ORM — locate the exact lines in `workflow_engine/engine.py` and quote them
- (d) positional role unpacking — locate the exact line
- (e) sandbox flags — confirm `--cap-drop` and `--security-opt` are genuinely absent from `docker_sandbox.py`

**2.3 Security model** (`ARCHITECTURE.md` §7.1) — verify every sentence: command source is template data, no network, resource caps, non-root, hard kill, unconditional destruction, fail-closed. **This section must be exactly true. Any overstatement is a critical finding.**

**2.4 Invariants #1–#10** — for each, state whether the codebase upholds it today, and where you checked.

**2.5 Terminology** (`CLAUDE.md` §3) — spot-check that UI strings use Commander terms and don't leak internal ones.

**2.6 Commands** (`CLAUDE.md` §6) — run each or verify it exists in the `Makefile`. A documented command that doesn't work is a finding.

**2.7 V1 surfaces** (`UX_SPEC` §7) — confirm each page/route exists in `apps/dashboard`.

- 2.8 Commit + push: `docs(v1.1): verification pass against codebase`

### Phase 3 — Cross-document consistency
- 3.1 Build a claim map: every statement appearing in more than one document (roles, invariants, roadmap, module status, terminology, security). Confirm exact agreement, not approximate.
- 3.2 Verify roadmap sprint numbers in `CLAUDE.md` §9 match every sprint reference in the other two documents
- 3.3 Verify the two org-chart diagrams (`CLAUDE.md` §2, `ARCHITECTURE.md` §1.1) agree with each other and with `UX_SPEC` §3.1 and §5
- 3.4 Verify every internal cross-reference resolves (§ numbers, file paths, rule numbers)
- 3.5 Fix mechanical errors only; report anything substantive instead of changing it
- 3.6 Commit + push: `docs(v1.1): cross-document consistency pass`

### Phase 4 — Repository cleanup
- 4.1 Remove every reference to `docs/V1.5-SPEC-refined.md` and to "V1.5" as a plan — **but do not rewrite historical sprint briefs in `docs/prompts/`; they are a record**
- 4.2 `README.md` — V1 released (`v1.0.0`), V1.1 in development, roadmap pointer to `CLAUDE.md` §9. **Verify every command actually runs**
- 4.3 Add a header comment to `PROGRESS.txt`: the `n/m` and `%` counters must always match item state
- 4.4 `docs/DECISIONS.md` from #128. At minimum:
  - superseding the V1.5 plan with V1.1, and why
  - the two-axis org model (decision vs delegation) and why one chart was insufficient
  - Role/Employee separation and singleton leadership
  - invariants #11–#17, one line each on why
  - three documents instead of four
  - repurposing `situation` instead of deleting it
  - template-driven architecture while shipping only one template
  - every judgment you made this sprint
- 4.5 Commit + push: `docs(v1.1): repository cleanup and decision log`

### Phase 5 — Close
- 5.1 `make test` — must still be 157 passed / 4 skipped. Any change means you touched code
- 5.2 `git diff v1.0.0 --stat` — confirm only documentation paths changed
- 5.3 Final consistency read-through of all three documents in one sitting
- 5.4 Commit + push: `docs(v1.1): kickoff complete`
- 5.5 Confirm remote HEAD matches your final commit

---

## 4. Out of scope

- Any change to `apps/`, `packages/`, `scripts/`, `alembic/` — including typo fixes
- Rewriting or restructuring the three provided documents beyond mechanical correction
- Creating `V1.1-SPEC.md` or any fourth spec document
- Rewriting historical sprint briefs in `docs/prompts/`
- Implementing, prototyping, or scaffolding anything from the V1.1 roadmap
- Fixing the five structural debt items (Sprint 9)

---

## 5. Definition of Done

1. The three documents are in place; no stale copy of their content exists elsewhere
2. Every Phase 2 claim has a recorded verdict with evidence
3. `ARCHITECTURE.md` §7.1 verified sentence by sentence; any overstatement reported as critical
4. No cross-document contradiction remains; every § reference and file path resolves
5. No reference to `V1.5-SPEC-refined.md` remains
6. `README.md` current, every documented command actually run
7. `docs/DECISIONS.md` has #128+ covering all eight required topics
8. `make test` → 157 passed / 4 skipped, unchanged
9. `git diff v1.0.0 --stat` shows documentation paths only
10. Remote HEAD matches the final commit
11. `PROGRESS.txt` fully `[x]` with an accurate counter

---

## Appendix A — PROGRESS.txt checklist

```
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 8.5 — V1.1 Kickoff (Documentation Integration)
 Overall: 0/40 items · 0%
 Now working on: -
 Last update: -
 (n/m and % in this header must always match item state)
================================================

PHASE 0 — Baseline                                             (0/5)
[ ] 0.1  신규 문서 3종 정독 (CLAUDE / ARCHITECTURE / UX_SPEC)
[ ] 0.2  교체 대상 기존 문서 3종 정독 — 무엇이 사라지는지 파악
[ ] 0.3  DECISIONS.md 127건 정독
[ ] 0.4  현재 상태 기록 (HEAD SHA / git status / make test)
[ ] 0.5  PROGRESS.txt 리셋 + 커밋/푸시

PHASE 1 — 문서 설치                                            (0/5)
[ ] 1.1  /CLAUDE.md 교체
[ ] 1.2  /docs/ARCHITECTURE.md 교체
[ ] 1.3  /docs/design/UX_SPEC.md 교체
[ ] 1.4  중복 사본 부재 확인 (제2의 진실 원천 방지)
[ ] 1.5  커밋+푸시: install V1.1 documentation baseline

PHASE 2 — 코드 대조 검증                                       (0/9)
[ ] 2.1  as-built 모듈 표 ~20항목 검증 (설명 + 상태 마커)
[ ] 2.2a 고아 미션: lifespan 복구 부재 · cancel 라우트 부재
[ ] 2.2b 예산: 강제 장치 부재 (기록만 하는지)
[ ] 2.2c detached ORM: engine.py 정확한 라인 특정 + 인용
[ ] 2.2d positional unpacking 라인 특정
[ ] 2.2e 샌드박스 --cap-drop / --security-opt 부재 확인
[ ] 2.3  Security Model §7.1 문장 단위 검증 (과장 = critical)
[ ] 2.4  불변식 #1~#10 각각 준수 여부 + 확인 위치
[ ] 2.5  용어표 / 명령어 / 라우트 확인 + 커밋/푸시

PHASE 3 — 문서 간 정합성                                       (0/6)
[ ] 3.1  중복 서술 claim map 작성 + 완전 일치 확인
[ ] 3.2  로드맵 스프린트 번호 3문서 동일 확인
[ ] 3.3  조직도 2종 + UX_SPEC §3.1/§5 상호 일치
[ ] 3.4  모든 § 참조 · 파일 경로 · 규칙 번호 해석 가능
[ ] 3.5  기계적 오류만 수정, 실질 문제는 보고로
[ ] 3.6  커밋+푸시: cross-document consistency pass

PHASE 4 — 레포 정리                                            (0/5)
[ ] 4.1  V1.5 계획 참조 제거 (docs/prompts 이력은 보존)
[ ] 4.2  README.md 갱신 + 모든 명령어 실제 실행 확인
[ ] 4.3  PROGRESS.txt 카운터 규칙 헤더 주석
[ ] 4.4  DECISIONS.md #128~ (필수 8주제 + 자체 판단 전부)
[ ] 4.5  커밋+푸시: repository cleanup and decision log

PHASE 5 — 종료                                                 (0/5)
[ ] 5.1  make test → 157 passed / 4 skipped
[ ] 5.2  git diff v1.0.0 --stat → 문서 경로만 변경
[ ] 5.3  세 문서 연속 통독 최종 정합성 확인
[ ] 5.4  커밋+푸시: kickoff complete
[ ] 5.5  원격 HEAD 일치 확인
================================================
```

---

## Appendix B — Completion report format (mandatory)

Report verifiable facts, not self-assessment. Do not list what went well — the reviewer will clone the repo and check.

```
## Sprint 8.5 완료 보고

### 1. 커밋
- 최종 커밋 SHA:
- 원격 HEAD 일치 확인 (확인 방법 포함):
- 커밋 목록:
- git diff v1.0.0 --stat 결과:

### 2. Phase 2 검증 결과 — 항목별 판정
각 항목에 confirmed / wrong / undetermined + 근거(파일:라인):
- 모듈 표 20항목
- 구조적 부채 5종 (a~e) — 해당 코드 라인 인용 포함
- Security Model §7.1 문장별
- 불변식 #1~#10 각각
- 용어표 / 명령어 / 라우트

**문서가 코드에 대해 틀리게 서술한 부분을 전부 나열하라.**
이것이 이 스프린트의 가장 중요한 산출물이다.

### 3. 문서 간 모순
Phase 3에서 발견한 모순 전부. 수정한 것과 보고만 한 것을 구분.

### 4. 설계 수준에서 의심스러운 부분
제공된 문서 중 구현 관점에서 문제가 있어 보이는 것.
특히 Sprint 9~11에서 실제로 만들 때 걸림돌이 될 설계.

### 5. 구 문서에서 유실된 가치 있는 내용
새 문서가 빠뜨렸다고 판단되는 기존 내용. 다시 넣지 말고 여기에만.

### 6. 코드에서 발견한 문제 (고치지 않은 것)
검증 중 발견한 버그·불일치·위험 전부.

### 7. 테스트
- make test 결과 / 157·4 기준선과 동일한가:

### 8. Sprint 9에 넘기는 것
인증 · 파이프라인 데이터화 · 운영 신뢰성 설계 시 알아야 할 사실.
Phase 2에서 코드를 읽으며 발견한 제약과 함정.

### 9. 확신이 낮은 부분
undetermined 판정 항목과 이유. 리뷰어가 직접 봐야 할 곳.
```