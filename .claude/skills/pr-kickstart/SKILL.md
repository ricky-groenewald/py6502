---
name: pr-kickstart
description: Kick off the next pull request. Syncs git state (fetch + prune, fast-forward `dev`, offer to delete merged local branches), runs `/roadmap pull` so the doc matches GitHub, pulls the full body of every open issue on the active milestone, recommends a scoped grouping for the next PR with reasoning, confirms the scope with the caller, and then enters plan mode seeded with that scope. Use when the caller asks "what's next?", "start the next PR", "kickstart a PR", or similar. This skill never commits, pushes, or closes anything — it hands off to `/commit` once the plan is approved and implemented. Use when caller asks something like "what should we work on next?" or "start the next PR".
---

# pr-kickstart

A staging skill. Its job is to get the repository and the caller's head
into a clean, well-briefed state *before* any implementation work on the
next PR starts. By the time this skill finishes, the caller is in plan
mode with a concrete, issue-backed scope — the implementation itself
happens after plan approval, and landing the work goes through
`/commit`.

## When to use

- The caller asks "what should we work on next?" or "start the next
  PR".
- A PR just merged and the caller wants to pick up the next one without
  manually spelunking through GitHub.
- The caller wants to be sure branches, roadmap, and milestone state
  are all consistent before committing to a scope.

Don't use this skill for:

- One-off commits to an already-scoped, in-flight branch — use
  `/commit`.
- Adding scope to the roadmap or opening issue stubs — use `/roadmap
  push`.
- Investigating a single specific issue the caller already named —
  just read it with `gh issue view`.

## Flow

Six steps, in order. Do not skip or reorder them.

### 1. Git hygiene

Run these **in parallel**:

```bash
git rev-parse --abbrev-ref HEAD
git status --porcelain
git fetch --all --prune
```

Then evaluate:

- **Dirty working tree** (`git status --porcelain` is non-empty):
  stop. Print the offending paths and ask the caller whether to stash,
  commit (via `/commit`), or abort. Do **not** auto-stash.
- **On a feature branch**: note it, but don't switch automatically —
  ask the caller whether they want to stay there or move to `dev`
  before kickstarting a new PR. Default suggestion: switch to `dev`.
- **On `main`**: stop and tell the caller; `main` is not a working
  branch in this repo.

Once the caller is on `dev` (or has explicitly said to stay elsewhere):

```bash
git checkout dev                   # only if not already on dev
git pull --ff-only origin dev
```

Never use plain `git pull` — fast-forward only. If fast-forward fails,
stop and surface the conflict; don't attempt a merge.

#### Pruning merged local branches

List candidates:

```bash
git branch --merged dev --format '%(refname:short)'
```

Filter out `main`, `dev`, and the current branch. Present the remaining
list to the caller with:

> These local branches are fully merged into `dev` and safe to delete:
> <list>. Delete them? (y / n / pick)

Only on explicit `y` or a pick-list, run:

```bash
git branch -d <name>
```

Never `-D` (force-delete). If `-d` refuses, the branch isn't actually
merged — surface the git error and stop, don't escalate to `-D`.

Also prune stale remote-tracking refs — `git fetch --prune` above
already did this, but note in the summary how many remote-tracking refs
were pruned (from the fetch output) so the caller sees the cleanup.

### 2. Roadmap sync

Invoke the `roadmap` skill in `pull` mode via the `Skill` tool:

```
Skill(skill="roadmap", args="pull")
```

Let it run to completion. If it reports `IN SYNC`, note that and move
on. If it edits `docs/ROADMAP.md`, show the diff to the caller and
mention that the doc edit will need to land via `/commit` as part of
(or alongside) the upcoming PR — but **do not** commit it from this
skill.

If the roadmap skill reports `ORPHANED` (scope without issues),
surface that to the caller and pause: they may want to run `/roadmap
push` first so the next-PR assessment has a complete issue list to
work from. Continue only once they confirm.

### 3. Pull open issues on the active milestone

Determine the **active milestone**: the earliest open milestone when
sorted by semver in the title (`v0.1` < `v0.2` < `v0.3`). Get the list:

```bash
gh api repos/:owner/:repo/milestones --jq \
    '.[] | select(.state == "open") | {number, title}'
```

Pick the earliest by version. If the caller has named a specific
milestone in the invocation, honour that instead.

Fetch every open issue on that milestone **with full bodies**:

```bash
gh issue list --milestone "<title>" --state open \
    --json number,title,body,labels,assignees,url --limit 100
```

Read every body. The body is where the actual scope lives — title
alone is not enough to reason about grouping.

### 4. Recommend a PR scope

Synthesise a recommendation. Evaluate each issue against:

- **Size**: is it a single-session PR or a multi-day effort?
  Favour the former for "next PR". Multi-day work lands as a series,
  not a single PR.
- **Dependency order**: does issue A unblock issue B? If so, A goes
  first, even if B is more interesting.
- **Cohesion**: do two issues touch the same file or subsystem such
  that bundling them saves a rebuild / review cycle? Grouping is
  welcome when the bundle reads as one coherent change.
- **Risk**: a risky refactor and an unrelated user-visible feature
  should not share a PR. Keep blast radius narrow.
- **Momentum**: which issue, when shipped, makes the next issue
  noticeably easier to scope? Prefer paving the road.

Present the recommendation in this shape:

```
Recommended next PR: <short name>
Scope: #<n> [, #<n>, ...]

Why this grouping:
<2–4 sentences on the reasoning — size, dependency, cohesion, risk>

Issues in scope:
  - #<n> <title>
      <one-sentence summary of the body>
  - ...

Alternatives considered:
  - <grouping B> — <one-line reason it lost>
  - <grouping C> — <one-line reason it lost>
```

Keep the whole recommendation under ~250 words. The caller will read
it and either agree or redirect; long walls of text slow that down.

If no open issue is a good fit for "next PR" (e.g. everything open is
blocked, or the milestone is effectively done), say so plainly and
stop. Don't invent scope.

### 5. Confirm with the caller

Ask explicitly:

> Proceed with <scope> as the next PR? (yes / adjust / different
> grouping)

Wait for an answer. Do **not** proceed to step 6 until the caller
agrees or gives you a modified scope. If they modify, re-present the
revised shape briefly and ask again.

The caller is allowed to:

- Add or drop an issue from the grouping.
- Pick one of the alternatives instead.
- Narrow the scope further (single issue).
- Defer and exit the skill without entering plan mode.

### 6. Enter plan mode

Once scope is confirmed, call `EnterPlanMode` with a seed that
includes:

- The chosen issue numbers + titles.
- A one-line restatement of the PR goal.
- Any cross-cutting constraint the caller flagged during confirmation
  (e.g. "keep the Apple1 display untouched").

The plan itself is produced inside plan mode using the normal
planning flow — this skill's job ends the moment `EnterPlanMode`
returns. Do **not** start writing code, editing files, or creating a
branch from inside this skill; branch creation is `/commit`'s job and
happens only after the plan is approved and implementation begins.

## What this skill must not do

- **Never commit, stage, or push.** Landing work is `/commit`'s
  responsibility, end of.
- **Never force-delete a branch** (`git branch -D`). Only `-d`, only
  on merged branches, only with caller approval.
- **Never `git pull` without `--ff-only`.** A merge commit on `dev`
  from this skill would violate the workflow.
- **Never close, comment on, or relabel GitHub issues.** Reading is
  fine; writes belong elsewhere.
- **Never create an issue.** That's `/roadmap push`.
- **Never auto-stash or auto-discard the working tree.** A dirty tree
  is a stop condition, not a problem to route around.
- **Never skip the roadmap sync** "to save time". The whole point is
  that the issue list this skill reasons about is consistent with the
  doc — skipping the sync makes every downstream recommendation
  suspect.
- **Never enter plan mode without explicit scope confirmation.** Plan
  mode is cheap to enter but annoying to exit mid-thought; the caller
  should know what they're planning before it opens.

## References

- `.claude/skills/roadmap/SKILL.md` — invoked from step 2; its own
  guardrails still apply.
- `.claude/skills/commit/SKILL.md` — the skill that takes over once
  the plan is approved and implementation begins.
- Root `CLAUDE.md` §Workflow — branch topology and the "every PR
  through a feature branch into `dev`" rule.
- `docs/ROADMAP.md` — milestone narrative; this skill reads it
  indirectly via the roadmap sync.
