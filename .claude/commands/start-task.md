You are starting a new development phase for bike-routes-api, following the "Start" stage of the phase lifecycle defined in `docs/PLAN.md` (identical process for `docs/IMPROVEMENT-PLAN.md` phases — see that file's own note). Follow every step in order. Never skip a step. Never create a branch without explicit confirmation.

---

## Step 1 — Check for pending changes

Run `git status`. If there is anything uncommitted (staged or not) or untracked that isn't expected scratch output: **stop immediately**, show it to the developer, and resolve or commit before continuing. Never branch off a dirty tree.

---

## Step 2 — Identify the phase

If not already obvious from the conversation, ask which phase this is for. Check both `docs/PLAN.md` (original v1 build, phases 0-5 — all shipped) and `docs/IMPROVEMENT-PLAN.md` (post-v1 initiative) for the phase's name, branch name, and current status.

If the phase's status row does not say "Not started": stop and flag it. Resuming or redoing a phase that already has a status is a decision the developer confirms explicitly, not something to assume.

---

## Step 3 — Sync `develop`

Run:

```bash
git fetch origin develop
git log HEAD..origin/develop --oneline
```

If `develop` has commits not yet in the local tree, pull before continuing. If either command fails, stop and report the error — do not continue.

---

## Step 4 — Create the phase branch

Confirm the exact branch name with the developer — it should match the name already listed in the relevant status table (e.g. `feature/support-points-endpoint`). Only after confirmation:

```bash
git checkout -b <branch-name> develop
```

Report that the branch was created and is now active.

---

## Step 5 — Handoff to `/write-spec`

Do NOT write a spec or any implementation code in this skill. Tell the developer exactly this:

> "✅ Branch `<branch-name>` created off `develop`. Next step: invoke `/write-spec` before any implementation."

Wait for the developer to invoke it. Do not continue.
