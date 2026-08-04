You are writing the spec for a bike-routes-api phase, following the "Middle" stage of `docs/PLAN.md`'s phase lifecycle (identical process for `docs/IMPROVEMENT-PLAN.md` phases). Follow every step in order. Do NOT write any implementation code (`.py` files under `app/`) until the developer has explicitly approved the spec.

---

## Step 1 — Re-read context

Read, in full:
- `docs/CONTEXT.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_SOURCES.md`
- Whichever of `docs/PLAN.md` / `docs/IMPROVEMENT-PLAN.md` this phase belongs to
- Any existing code relevant to the phase (e.g. sibling resource modules, to follow the same layering pattern — `router.py`/`service.py`/`repository.py`/`schemas.py`)

---

## Step 2 — Check coherence before writing anything

Compare the phase's plan against what you just read. If anything has drifted — a fact assumed when the plan was written turns out to be wrong, or a related part of the codebase changed since — surface it to the developer and reconcile it explicitly before proceeding. Do not carry a stale assumption into the spec.

---

## Step 3 — Write the spec

Run `ls docs/specs/` to find the next sequential number (`NN` = highest existing + 1). Create `docs/specs/NN-phase-name.md` — this must be the first file written for this phase, before any `.py` file. Cover, at minimum:

- Goal / scope
- Inputs
- Outputs (function signatures, response shapes)
- Error / edge cases
- Files to be created or changed
- The test cases that will prove it

---

## Step 4 — Hard gate: wait for approval

⛔ **Do NOT implement anything yet.** Show the developer the spec's path and ask:

> "Spec written at `docs/specs/NN-phase-name.md`. Please review it — confirm to proceed with implementation, or tell me what to adjust."

Wait for explicit confirmation before writing any code.

---

## Step 5 — Implement

Only after confirmation, implement exactly what the spec describes. If implementation reveals the spec needs to change, update the spec doc to match reality before moving on — it must stay true, not aspirational.

---

## Step 6 — Handoff to `/finish-task`

Do NOT invoke `/finish-task` automatically. Tell the developer exactly this:

> "✅ Implementation complete, matching the spec. Next step: invoke `/finish-task` to validate and open the PR."

Wait for the developer to invoke it. Do not continue.
