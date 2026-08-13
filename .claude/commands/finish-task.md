You are closing out a bike-routes-api phase, following the "End" stage of `docs/PLAN.md`'s phase lifecycle (identical process for `docs/IMPROVEMENT-PLAN.md` phases). Follow every step in order. Never skip a step, and never commit or open a PR without the developer's explicit confirmation at the gates marked below.

---

## Step 1 — Run the automated test plan

Confirm the local PostGIS is up:

```bash
docker compose ps
```

Expect the `postgis` service `Up`/`healthy`. If it isn't, start it (`docker compose up -d`) and wait until it is.

Run:

```bash
uv run pytest -q
```

⛔ **Hard gate.** Running this yourself and reporting "passed" is NOT the same as the developer having verified it — `docs/PLAN.md` is explicit about this. Hand her the exact commands to run herself (the full suite, plus the specific new module by path) and the exact expected result (test count, and the new test names if any are new). **Do not proceed to Step 3 until she has personally confirmed the result.**

---

## Step 2 — Check spec-vs-implementation coherence

Re-read the phase's spec doc (`docs/specs/NN-*.md`) against the actual diff. If anything diverged during implementation, update the spec now so it stays accurate — not aspirational.

---

## Step 3 — Direct review pass

Review the full diff yourself, as a demanding senior engineer looking for flaws — not a rubber stamp. Cover:

- **Correctness**: logic errors, edge cases, and what's *missing* (an untested path, an unhandled boundary) — not just what's visibly wrong.
- **Design fit**: reuses existing helpers instead of reinventing them; complexity proportional to the actual problem; a public response shape changes additively, never silently breaking.
- **Architecture rules** (`docs/ARCHITECTURE.md`): no business logic in `router`, no raw SQL/ORM outside `repository`; spatial queries use the GiST index; pagination+bbox+standard envelope/error shape present; nothing outside `docs/CONTEXT.md`'s scope without a surfaced decision.
- **Security checklist**: API key hashed and mandatory with no bypass; rate limiting on the route; input validation rejects unexpected fields; bbox/page-size caps enforced; no internal leakage in errors; new deps pinned and `pip-audit`-checked.

Do **not** use the generic `/code-review` skill for this project — it requires a PR to already exist and always posts an AI-attributed GitHub comment, both a wrong fit here. This direct pass replaces it.

Fix anything found before moving to Step 4. If a fix changes test coverage, loop back to Step 1 and re-confirm with the developer before continuing.

---

## Step 4 — Dedicated review skills

Run, separately (each does something Step 3 doesn't):

- `/security-review` — adversarial security pass.
- `/verify` (this project's own `.claude/skills/verify/SKILL.md`, not a generic one) — hit the changed endpoint for real (curl/httpie), don't just trust green tests.

Fix everything found before continuing.

---

## Step 5 — Check for conflicts with `develop`

```bash
git fetch origin develop
git merge-tree $(git merge-base HEAD origin/develop) HEAD origin/develop
```

Resolve any conflicts now — never after opening the PR.

---

## Step 6 — Hard gate: commit

⛔ Only after the developer has personally confirmed Step 1's test results **and** you've fixed everything found in Steps 3-4, stage and commit.

- No AI attribution anywhere: no "Generated with X", no "Co-Authored-By", no AI self-reference in commit messages, code comments, or the PR body.
- Conventional Commits format: `type(scope): description`.

---

## Step 7 — Open the PR

Open the PR to `develop` (never directly to `main` — `main` only moves at the release phase) with a description of what changed and why, no AI mention anywhere. Update the status table in whichever of `docs/PLAN.md` / `docs/IMPROVEMENT-PLAN.md` tracks this phase.

⛔ **Never merge.** Merge authority stays with the developer, always, no matter how green CI is — report the PR is ready and stop.
