---
name: commit
description: The mandatory path for any git commit or pull request in this repository. Enforces the protected-branch rule (`main` and `dev` are never committed to directly), the feature-branch naming convention, the single-imperative-headline commit style, and the no-`Co-Authored-By: Claude` rule. Invoke as `/commit` for a plain commit on the current feature branch, or `/commit pr` to additionally push and open a GitHub pull request into `dev`. Use this skill every time the user asks you to commit or open a PR — never commit or `gh pr create` out-of-band.
---

# commit

The single point of truth for landing work in this repo. Any time the
user asks you to commit or open a PR, you invoke this skill — there is
no other path. The reason it exists is that `py6502` has hard rules
about branches, commit message shape, and author attribution that are
easy to forget mid-flow; centralising them here makes them a checklist
instead of folklore.

## Modes

- `/commit` — stage + commit on the current feature branch.
- `/commit pr` — everything in `/commit`, plus push the branch upstream
  and open a pull request into `dev`.

Both modes share the same safety gate and commit-message rules below.
Never run `git commit` or `gh pr create` outside this skill.

## Safety gate: protected branches

Before staging anything:

```bash
git rev-parse --abbrev-ref HEAD
```

If the result is `main` or `dev`, **stop**. Do not stage, do not commit,
do not stash. Tell the caller:

> You're on `<branch>`. Features land via a PR from a feature branch
> into `dev` (see `docs/ROADMAP.md` §Git workflow). What would you like
> to name the feature branch?

Wait for an answer. Once they give you a name, sanity-check it against
the convention below, create the branch, and only then proceed:

```bash
git checkout -b <branch-name>
```

If the caller explicitly says "just commit to dev anyway" or similar,
**still refuse**. The rule is in `CLAUDE.md` and `docs/ROADMAP.md`;
overriding it needs a root-CLAUDE.md edit, not a one-off bypass. Point
them at the docs and stop.

### Feature-branch naming

Prefixes in active use:

- `feat/<kebab-case-topic>` — new functionality or scope.
- `fix/<kebab-case-topic>` — bug fix.
- `docs/<kebab-case-topic>` — documentation-only changes.
- `refactor/<kebab-case-topic>` — internal restructuring with no
  behaviour change.
- `chore/<kebab-case-topic>` — build, tooling, dependency bumps, CI.

The topic should be short (2–6 words), lowercase, hyphen-separated, and
describe the *work*, not the ticket number. Examples:
`feat/system-iac-and-device-abstractions`,
`fix/wozmon-backspace-echo`, `docs/architecture-tick-hooks`.

If the caller proposes a name that doesn't fit a known prefix, suggest
the nearest match but defer to them if they insist.

## Gathering context

Once you know you're on a feature branch, run these **in parallel**
with the `Bash` tool:

```bash
git status                         # never -uall, which OOMs on big repos
git diff --stat                    # summary of unstaged changes
git diff --cached --stat           # summary of already-staged changes
git log --oneline -10              # commit-message style reference
```

Read the output before writing the commit message. Pay special
attention to:

- Files outside the stated scope of the change (possible accidental
  inclusion).
- `.env`, `credentials*.json`, `*.key`, `*.pem`, private `*.yaml` —
  **never stage these**. If one shows up in `git status`, stop and flag
  it to the caller.
- Anything under `play/` — treat as read-only per root `CLAUDE.md`.
  Never stage it without an explicit instruction.

## Staging

Stage **specific files by name**. Do not use `git add -A`, `git add .`,
or `git add -u`. The list of files to stage is whatever is in scope for
the commit the caller described — when in doubt, stage only the files
that appear in both `git diff --stat` and your mental model of the
task, and ask about any leftover modifications before including them.

```bash
git add path/one path/two path/three
```

If the scope is very large (e.g. a restructure), batching the `git add`
commands is fine — but every path is still typed explicitly.

## Commit message

The contract, in order:

1. **Single imperative headline.** ≤ 70 characters, present tense,
   starts with a verb (`Split`, `Add`, `Fix`, `Refactor`, `Remove`).
   No trailing period. This is by far the most common shape — match
   the existing history before reaching for a body.
2. **Optional short body** — only when the *why* isn't obvious from the
   diff alone, and only when the change genuinely spans multiple
   concerns. Two or three short lines, wrapped at ~72 cols. Never
   re-describe what the diff already shows; focus on the reason.
3. **No `Co-Authored-By:` trailer. Ever.** Not for Claude, not for any
   variation of Claude, not "Generated with", not "🤖". Human
   authorship is the default in this repo, full stop.
4. **No issue-closing keywords in the commit itself** (`Closes #34`,
   `Fixes #29`). Those belong in the PR description, where GitHub
   actually wires them up. The commit references the work, the PR
   closes the issue.

Pass multi-line messages via a HEREDOC so formatting is preserved:

```bash
git commit -m "$(cat <<'EOF'
Split Apple1 peripheral and rewrite sim.system against IaC spec
EOF
)"
```

Single-line is fine as `git commit -m "..."` without the HEREDOC.

### Rejected shapes (don't generate these)

- `"feat: add foo"` — conventional-commits prefix. Not used here.
- `"Updated X"` — past tense. Use imperative.
- `"WIP"`, `"fixes"`, `"more work"` — not descriptive.
- Multi-paragraph bodies that recap the entire PR. That's the PR
  description's job.
- Anything with an emoji in the headline unless the user explicitly
  asked for one.

## The commit itself

```bash
git commit -m "<headline>"
# then
git log --oneline -3
```

Never pass `--no-verify`, `--no-gpg-sign`, `-c commit.gpgsign=false`, or
`--amend`. If a pre-commit hook fails, the commit did *not* happen; fix
the underlying issue, re-stage, and create a **new** commit.

If the hook failure is opaque, read the hook output to the caller and
ask how they want to proceed — don't guess.

## `/commit pr` mode

After the commit lands, and **only** after, run the PR flow:

1. **Push** the branch upstream with `-u` on first push:

   ```bash
   git push -u origin HEAD
   ```

   Never `--force` or `--force-with-lease` on first push. If a retry
   needs a force-push on a previously-reviewed branch, stop and ask.

2. **Gather PR context** in parallel:

   ```bash
   git log dev..HEAD --oneline
   git diff dev...HEAD --stat
   ```

   Read the full commit range, not just `HEAD`. The PR description
   summarises the whole branch.

3. **Draft the PR body** using this template, filled from the commits +
   diff:

   ```markdown
   ## Summary
   - <bullet 1>
   - <bullet 2>

   ## Why
   <one paragraph on the motivation — this is where context lives>

   ## Test plan
   - [ ] <specific manual or automated check>
   - [ ] <specific manual or automated check>

   ## Closes
   <GitHub issue references, e.g. `Closes #29`, `Closes #34` — only if
   the branch genuinely closes them>
   ```

   Keep the summary tight (3–6 bullets). The *why* paragraph is the
   part that ages well; write it for someone reading the PR six months
   from now.

4. **Create the PR into `dev`** via HEREDOC:

   ```bash
   gh pr create --base dev --title "<same headline as the commit, or a tighter summary>" --body "$(cat <<'EOF'
   ## Summary
   ...
   EOF
   )"
   ```

   If the branch has more than one commit, prefer a tighter headline
   that covers the full range rather than reusing the last commit's
   headline verbatim.

5. Print the PR URL that `gh pr create` returned so the caller can
   click through.

Never PR directly into `main`. Versioned releases are the only path
into `main`, and they're human-driven. If the caller asks for a
`main`-targeted PR, stop and confirm it's actually a release cut — if
it is, still pause for explicit approval before running `gh pr create`.

## What this skill must not do

- **Never force-push `main` or `dev`.** Ever. Not even if asked.
- **Never update git config** (`git config ...`).
- **Never `git add -A` / `git add .`.** Always stage by name.
- **Never commit files matching** `.env*`, `credentials*`,
  `*secrets*`, `*.key`, `*.pem`, `id_rsa*`, `*.pfx`.
- **Never bypass hooks** with `--no-verify`.
- **Never amend** an existing commit. A failed hook means the commit
  didn't happen; create a new one.
- **Never run `git reset --hard`, `git checkout .`, `git clean -fd`,
  `git restore .`** to "clean up" before committing. If the working
  tree has unexpected files, ask the caller what they are.
- **Never add a `Co-Authored-By: Claude`** (or any variant) trailer.
- **Never commit when the protected-branch gate fails.** Branch
  creation is a caller-initiated action.

## References

- Root `CLAUDE.md` §Workflow — commit style, no `Co-Authored-By`.
- `docs/ROADMAP.md` §Git workflow — branch topology, force-push rules.
- `.claude/skills/roadmap/` — the other skill that touches git state,
  and a good template for how a skill documents its boundaries.
