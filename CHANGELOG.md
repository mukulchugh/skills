# Changelog

All notable changes to this repository are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2026-08-06

Renamed from `pr-review-quiz` to `pr-walkthrough`.

The quiz is thirteen optional questions in a side rail; the product is an
evidence-backed review walkthrough with a publish gate. The old name led with the
smallest feature and would have been wrong the moment the questions were dropped.

### Changed

- Skill, plugin and command are now `pr-walkthrough`. **Re-install to pick it up** —
  the old plugin id no longer resolves.
- The archive root moved to `~/.local/share/pr-walkthrough/`. Reviews written under
  the old root stay discoverable: if the new root does not exist and the old one
  does, the old one is still read.
- `PR_WALKTHROUGH_HOME` overrides the archive root. `PR_REVIEW_QUIZ_HOME` is still
  honoured as a fallback.

## [1.1.0] — 2026-08-06

The review artifact becomes a workbench, and three things the workflow only
promised are now enforced.

### Added

- **Confirmation gate before any GitHub write.** Submitting a review prints every
  inline comment in full — path, line, side, body, and any suggestion block — and
  waits for explicit confirmation. A comment count is not confirmation; you cannot
  approve comments you have not read.
- **Three bundled hooks** (`hooks/hooks.json`). A `PreToolUse` publish gate that
  hard-denies unconfirmed GitHub writes while a review is in flight, a background
  watcher that tells the agent when a manual walkthrough finishes, and a
  `SessionStart` injector that supplies the cached stack profile. All three are a
  Claude Code enhancement layer — Codex and Cursor behaviour is unchanged.
- **`render_review.py --serve`** — an opt-in, localhost-only writer that accepts
  reading progress from the artifact. The token lives only in the serving process,
  so the copy inside an archived page grants nothing later.
- **`parse_diff.py --skeleton`** — emits a guide-shaped scaffold with the real hunks
  already grouped, tests split out, and every judgement field left as a greppable
  `TODO:`. Hand-assembling hunks was where coverage mismatches came from.
- **`disproved`** in the guide schema — candidates that were investigated and
  cleared, with the reason and the evidence that settles them. An unrecorded
  disproof gets re-litigated by the next reviewer.
- **`findings[].found_by`** — which review lanes reached a finding independently.
  Convergence by separate routes is stronger evidence than a self-assigned score.
  Unknown lane names are rejected at validation.
- **Stack and integration grounding** (`references/context-grounding.md`). Detects
  usable read-only integrations from the agent's own tool list and the repository's
  manifests, never by probing, and caches the result so it stops asking.
- **Syntax highlighting** in the diff, from a standard-library tokenizer across ten
  grammars and 40+ extensions. Escaping happens per token, never after.

### Changed

- The artifact is now one panel at a time behind a floating table of contents:
  Overview, then each review module, then Wrap up and Codebase notes.
- Findings read as a comment trail beside the diff and collapse to a single row
  inline, so triage comes before reading and the diff keeps its rhythm.
- Diffs wrap by default; the code column fills the card.
- Visual language follows the parent design system: light shell with white floating
  chrome, one interactive accent used only on interactive and active states, a
  derived radius scale, and glass surfaces carrying the inset top-edge highlight.

### Fixed

- The diff rows were shrink-wrapping to roughly half the available width, so lines
  wrapped far earlier than the column required.
- Programmatic focus on a module heading painted a visible focus ring on every
  navigation.
- `validate_package.py` resolved hook paths with `shlex`, which is POSIX-mode by
  default and drops the backslashes in a Windows path.

### Internal

- `self_check` asserts CSS and icon-sprite coverage in both directions, across both
  the populated and the empty page state. It caught six dead-asset regressions
  during this release.
- `validate_package.py` verifies every hook script referenced by `hooks.json`
  exists and, off Windows, is executable — a wrong hook path otherwise ships
  silently and simply never fires.

## [1.0.0] — 2026-08-05

Initial release, as `pr-review-quiz`. It reviews a frozen pull request, partitions every
diff hunk into logical units, runs independent review lanes, verifies findings
against cited source, and renders a persistent HTML walkthrough. Installs on
Codex, Claude Code and Cursor from one package.

[1.2.0]: https://github.com/mukulchugh/skills/releases/tag/v1.2.0
[1.1.0]: https://github.com/mukulchugh/skills/releases/tag/v1.1.0
[1.0.0]: https://github.com/mukulchugh/skills/releases/tag/v1.0.0
