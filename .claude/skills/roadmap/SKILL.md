---
name: roadmap
description: Bidirectional sync between `docs/ROADMAP.md` and GitHub milestones/issues using the `gh` CLI. In `pull` mode, refresh the open-issue lists in ROADMAP.md to match current GitHub state. In `push` mode, open GitHub issue stubs for any scope mentioned in ROADMAP.md that doesn't yet have an issue. In `status` mode, print a diff report without touching either side. Use this when the caller asks to "sync the roadmap" or when a PR changes scope language without touching issues.
---

# roadmap

A small, deliberate sync tool. GitHub milestones and issues are the
source of truth; `docs/ROADMAP.md` is a human-readable snapshot plus the
*why*. This skill keeps the two consistent without pretending one is
generated from the other.

## Modes

Invoke with one of:

- `/roadmap status` — print a diff report. No file edits, no GitHub
  writes. Default mode when in doubt.
- `/roadmap pull` — update `docs/ROADMAP.md` so its open-issue bullet
  lists match the current GitHub state. Preserves all prose.
- `/roadmap push` — open GitHub issue stubs for scope mentioned in
  `docs/ROADMAP.md` that doesn't yet have an issue. Always confirms with
  the caller before creating issues.

## Required context

Before doing anything, gather:

```bash
# Milestones
gh api repos/:owner/:repo/milestones --jq '.[] | {number, title, state, open_issues, closed_issues}'

# Issues per milestone (run once per milestone)
gh issue list --milestone "<milestone title>" --state all \
    --json number,title,state,labels --limit 100
```

Then `Read` `docs/ROADMAP.md`. Identify the three milestone sections
(v0.1, v0.2, v0.3) and the "Open issues in GitHub milestone ..." bullet
list inside each.

## `status` mode

Produce a short report in three parts:

1. **Drift: issue lists in the doc vs GitHub.** For each milestone:
   issues in the doc but closed/moved/renamed on GitHub (stale bullets);
   open issues on GitHub missing from the doc (new work not yet
   reflected).
2. **Scope language without issues.** Skim each milestone's "Scope"
   prose for bullets that describe concrete work items. For each one,
   check whether an open issue on the milestone plausibly covers it (by
   keyword match against issue title). Flag prose bullets with no
   matching issue.
3. **Summary line.** One of:
   - `IN SYNC` — no drift, no orphaned scope.
   - `DRIFT` — issue lists need a `pull`.
   - `ORPHANED` — scope language has no backing issues; needs `push` or
     a scope trim.
   - `DRIFT + ORPHANED` — both.

Keep the whole report under 300 words.

## `pull` mode

1. Run `status` first and show it to the caller.
2. For each milestone, rebuild the open-issue bullet list to match
   GitHub. Format:
   ```
   - [#<number>](https://github.com/ricky-groenewald/py6502/issues/<number>) — <title>
   ```
   Sort by issue number ascending. Drop closed issues. Keep the surrounding
   prose and the "explicit non-goals" section unchanged.
3. If an issue's title in the doc differs from GitHub, prefer GitHub's
   title — that's the source of truth.
4. Use the `Edit` tool, not `Write`, so prose is preserved.
5. Show a final diff and a short "pulled N issues into v0.X" summary.

## `push` mode

1. Run `status` first and show it to the caller.
2. For each orphaned scope bullet, propose a GitHub issue: title, body
   (one paragraph quoting the relevant prose from ROADMAP.md), milestone,
   labels (infer from the surrounding milestone: `simulator`,
   `frontend`, `feature`, etc. — err on the side of fewer labels).
3. **Present the full list to the caller and ask for explicit approval
   before creating anything.** Creating GitHub issues is visible to
   others; it falls under the "risky action" bucket from the root
   guidelines.
4. On approval, create issues with:
   ```bash
   gh issue create --title "<title>" --body "<body>" \
       --milestone "<milestone title>" --label "<labels>"
   ```
5. Print the URLs of created issues.
6. After creating, run `pull` to refresh the bullet lists in the doc so
   the new issues show up in the right sections.

## What the skill must not do

- **Never close, reopen, rename, or relabel GitHub issues.** This skill
  only creates issues, and only in `push` mode with explicit approval.
- **Never force-push, rebase, or otherwise rewrite git history.** The
  only writes to the working tree are edits to `docs/ROADMAP.md` via the
  `Edit` tool.
- **Never write to `main` or `dev` directly.** Leave committing /
  branching to the caller.
- **Never fabricate an issue number.** If an issue doesn't exist on
  GitHub, it doesn't go into the doc. The number comes from `gh issue
  create` output.
- **Never silently move an issue between milestones.** Moving an issue
  is a human decision; if `status` suggests an issue belongs elsewhere,
  flag it and stop.

## References

- `docs/ROADMAP.md` — the file this skill edits.
- The `ricky-groenewald/py6502` GitHub repo — the source of truth.
- Root `CLAUDE.md` §Workflow and `docs/ROADMAP.md` §Git workflow for the
  PR and review gates any roadmap change should eventually pass
  through.
