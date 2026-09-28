---
name: docs-drift
description: Scan every doc, README, CLAUDE.md, skill, and agent file for claims that contradict the code. Report only; never edits. Use before a release, at the end of a milestone (#64), or when a PR renamed public symbols. Invoke as `/docs-drift` for the full scan, or `/docs-drift <path>` to limit the scan to one doc.
---

# docs-drift

A read-only audit. The three files under `docs/` are a contract (root
`CLAUDE.md` §Documentation), and the per-package `CLAUDE.md`, README,
skill, and agent files are what humans and Claude read before touching
code. When any of them describes something the code no longer does, the
next change built on that description is wrong before it starts. This
skill finds those spots and hands back a checklist. Fixing them is a
separate, human-approved edit.

## When to use

- Before cutting a release (`dev` → `main`).
- At the end of a milestone, as the first half of the cleanup pass
  (see #64).
- After any PR that renamed, re-signatured, moved, or removed a public
  symbol, file, or config key. The `/commit pr` doc-drift check catches
  the names a branch touched; this skill catches everything else.
- When someone says "the docs say X but the code does Y".

## What it scans

Docs: `docs/ARCHITECTURE.md`, `docs/SYSTEM_CONFIG.md`,
`docs/ROADMAP.md`, root `CLAUDE.md`, `src/py6502/sim/CLAUDE.md`,
`src/py6502/ui/CLAUDE.md`, `README.md`, `src/py6502/sim/README.md`,
`src/py6502/ui/README.md`, every `.claude/skills/*/SKILL.md`, every
`.claude/agents/*.md`, and the module docstrings under
`src/py6502/sim/system/`.

Use `Read`, `Grep`, `Glob`, and read-only `Bash` (`sed -n`, `grep`,
`git ls-files`, `gh issue list`). Verify concrete claims against code,
not vibes. Every finding needs a code line that contradicts the doc.

## The checks

Work through all ten. Skipping one is how drift survives a scan.

1. **Signatures and code blocks.** Every code block or inline signature
   in a doc vs the real `.pxd` / `.pyx` / `.py`: `Component`, `Memory`,
   `BusController`, `MOS6502`, `System`, `TextDisplay`, `Font`, the
   peripherals, the config dataclasses, the registry. Return types,
   `except` clauses, parameter names, field types.
2. **The `System` API list.** ARCHITECTURE's `cpdef` listing vs
   `src/py6502/sim/system/system.pxd`, entry by entry.
3. **SYSTEM_CONFIG vs the loader.** Validation rules 1–13 vs what
   `loader.py` enforces and the exception it raises. The dataclass
   listing vs `config.py`, field by field. The appendix preset vs
   `src/py6502/sim/assets/presets/*.yaml`. The registry listing vs
   `registry.py`. The build-order section vs `System.__init__`.
4. **Layout trees.** Every directory tree in a doc vs `git ls-files`.
   Missing files, renamed files, subpackages that do not exist.
5. **Cross-references.** Section numbers and anchors between docs
   (`§9`, `#9-how-...`) resolve to the section they name.
6. **Described UI behaviour.** What README and the ui docs say a
   window, dialog, menu, or setting does vs `src/py6502/ui/windows/*.py`
   and `src/py6502/ui/utils/settings.py`. Where files persist.
7. **Tests and CI claims.** Tests named in docs exist under `tests/`.
   Claims about CI, conformance runners, markers, or fixtures match
   what is actually in the repo (`.github/`, `scripts/`, `conftest.py`,
   `pyproject.toml`).
8. **Milestone assignments.** Any "v0.2 target" / "v0.3 work" phrase in
   a doc vs the issue's milestone on GitHub (`gh issue list --milestone`).
9. **Skill and agent templates.** Code templates in `.claude/skills`
   vs a real component's shape. Rule text in `.claude/agents` vs the
   file it claims to summarise.
10. **In-source docstrings and comments.** Module and class docstrings
    that describe an older behaviour (a getter that used to render, a
    mode list missing a mode, a section number that moved).

## What it returns

Grouped by file, one bullet per finding:

```
## <doc path>

- <doc path>:<line> — says <what the doc claims, few words>.
  Code: <code path>:<line> <what the code actually does>.
  Fix: <one line>.
```

Mark each bullet `[known]` if the caller supplied an earlier findings
list and the item is on it, `[new]` otherwise. End with:

```
Counts: <known> known, <new> new, <total> total.
```

Keep the whole report under ~1800 words. If a doc is clean, say so in
one line rather than omitting it, so the caller knows it was checked.

## What this skill must not do

- **Never edit a file.** Not the docs, not the code, not a docstring.
  The output is a report; edits go through a reviewed PR.
- **Never touch git state.** No staging, no committing, no branch
  changes, no stash.
- **Never fabricate a line number.** Every `path:line` in the report
  comes from a `Read` or `grep -n` result in this run. If you cannot
  point at a line, do not report the item.
- **Never report a style preference as drift.** Drift is a factual
  contradiction between prose and code. Wording, tone, and length are
  out of scope.
- **Never exceed ~1800 words.** If the list is longer, group the
  mechanical items (layout trees, section numbers) into one bullet per
  file and keep the individual bullets for items that change meaning.

## References

- Root `CLAUDE.md` §Documentation — why the `docs/` files are a
  contract.
- `.claude/skills/commit/SKILL.md` §Doc-drift check — the per-branch
  version of this scan that runs before every PR.
- `.claude/skills/roadmap/SKILL.md` — the sibling read-mostly skill,
  and the template for how a skill documents its boundaries.
- #64 — the end-of-milestone cleanup pass this skill feeds.
