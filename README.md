# Skills

Portable agent skills by Mukul Chugh. The repository exposes the same skill bundle to Codex, Claude Code, and Cursor through each host's native plugin manifest.

## PR Review Quiz

`pr-review-quiz` reviews a frozen GitHub pull request, partitions every real diff hunk into logical review units, runs independent native-agent review lanes, verifies findings against cited source, and renders a persistent keyboard-navigable HTML walkthrough. Tests are kept in separate units. GitHub comments, Wiki pages, and issues are written only when explicitly requested.

GitHub writes require an explicit verb — a bare run never touches GitHub. Before any inline comment is posted, every comment is previewed in full: path, line, side, and body. That preview requires confirmation. A count is not confirmation.

Artifacts are archived under `~/.local/share/pr-review-quiz/reviews/` by default, so any local agent or CLI can retrieve the latest review.

## Install

### Codex

```text
codex plugin marketplace add mukulchugh/skills
codex plugin add pr-review-quiz@mukulchugh-skills
```

### Claude Code

Run these inside Claude Code:

```text
/plugin marketplace add mukulchugh/skills
/plugin install pr-review-quiz@mukulchugh-skills
```

### Cursor

Clone this repository, then copy or symlink `plugins/pr-review-quiz` to `~/.cursor/plugins/local/pr-review-quiz` and reload Cursor. The checked-in Cursor marketplace manifest is ready for marketplace submission; after listing, the plugin can also be installed through Cursor's `/add-plugin` flow.

## Use

```text
/pr-review-quiz owner/repository#123
/pr-review-quiz submit owner/repository#123
/pr-review-quiz publish wiki owner/repository#123
/pr-review-quiz create issues owner/repository#123
```

The first form is read-only. Publishing verbs authorize only the named GitHub write.

## Live progress (`--serve`)

The walkthrough renderer (`plugins/pr-review-quiz/skills/pr-review-quiz/scripts/render_review.py`) takes an optional `--serve` flag. It starts a localhost-only writer so the open HTML page can report reading progress back to disk as the reviewer works through it. Opt-in, off by default — the artifact renders and works completely normally without it.

## Hooks (Claude Code only)

Three hooks ship in `plugins/pr-review-quiz/hooks/`:

- `publish_gate.py` — blocks unconfirmed GitHub writes while a review is in flight.
- `watch_progress.py` — runs in the background and notifies the agent when the reader finishes the walkthrough.
- `inject_context.py` — supplies the cached stack/integration profile at session start.

Hooks are a Claude Code-only enhancement layer. Behavior on Codex and Cursor is unchanged.

Validate the package without installing dependencies:

```bash
python3 scripts/validate_package.py
```

MIT licensed.
