# cherrylove-api

Django + DRF API, Django Admin and worker.

Part of **CherryLove**, a private shared space for a couple. This repo holds no product code yet: the first code
comes from step 1 of its implementation plan.

## Source of truth

All requirements, decisions and architecture live in
[cherryLove-docs](https://github.com/cmlooz/cherryLove-docs/blob/main/README.md). The rules for this repo come from: ADR-001 (modules, layers), ADR-002 §1 (folder tree), ADR-003 (contract), ADR-004/005 (auth), ADR-013 (jobs), ADR-016 (versions).

## Working agreement

- Conventional Commits, 1 commit per step, 1 PR per phase, ≥ 1 test per step (DEC-023).
- Every commit, PR and test cites the REQ / DEC / ADR IDs it implements.
- `main` is protected: PR + green `ci`, rebase merge only (ADR-015, DEC-039).
- Enable the local hook once per clone: `git config core.hooksPath .githooks`.
