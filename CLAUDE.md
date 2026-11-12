# cherrylove-api — Claude Code instructions

Workspace rules live in `../CLAUDE.md` and `../cherryLove-docs/CLAUDE.md`; read them first.
Only `approved` documents in `../cherryLove-docs` may drive code here.

## Architecture rules for this repo

- Folder tree: `config/` (Django project only) and `src/cherrylove/<module>/{domain,application,infrastructure,interfaces}` per ADR-002 §1.
- Modules: identity, cards, memories, media, diary, favorites, notifications, sync, audit, backoffice, shared (ADR-001 §1, ADR-007).
- Dependency rule: `domain` imports nothing from Django; arrows point inward; enforced by import-linter (ADR-001 §6).
- Every repository/query port takes `couple_id`; ORM access without it must fail (ADR-005).
- Writes: use case → domain → repository port. Reads: query services returning DTOs; no business rule in a query (CQRS-lite).
- Audit, sync change recording and job enqueueing happen inside the use-case transaction (ADR-001 §4, ADR-006, ADR-013).
- No `try/except` in views or use cases; typed domain errors mapped to RFC 9457 by one handler (ADR-010).
- The contract in `contract/openapi.v1.yaml` is approved by Camilo; drf-spectacular output must match it (ADR-003).
- Python 3.14.10, Django 5.2.19 LTS, PostgreSQL 18; exact pins per ADR-016, managed with uv.

## Always

- Strict typing, validation before `try/catch`, SOLID, official documentation first.
- 1 commit per step with ≥ 1 test citing its REQ ID; never push to `main` (open a PR).
- A gap in the docs becomes an open question in `../cherryLove-docs/02-requirements/open-questions.md`; never assume.
