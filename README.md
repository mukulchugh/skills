# Skills

Portable agent skills by Mukul Chugh. One package, installed natively by Codex,
Claude Code and Cursor through each host's own plugin manifest. Python standard
library only — no dependencies, no build step, no runtime service.

Two skills over the same pull request, for two different readers. **`pr-walkthrough`**
reviews the code. **`pr-brief`** answers what it means for the product. Install once;
both arrive.

## PR Walkthrough

`pr-walkthrough` reviews a frozen GitHub pull request. It partitions every real
diff hunk into logical review modules, runs independent review lanes, verifies
each finding against cited source, and renders a self-contained HTML walkthrough
you can read, archive or send to someone else.

Not a summary of the diff. The walkthrough is built from the actual hunks, and
the renderer refuses to build it unless every hunk is accounted for exactly once.

### What the walkthrough gives you

- **Triage before reading.** Findings sit in a rail beside the diff and collapse
  to a single row inline at the exact line they belong to.
- **Evidence, not assertion.** Every finding carries quoted source, a confidence
  score, and which review lanes reached it independently.
- **What was ruled out.** Candidates that were investigated and cleared are
  recorded with the reason — so the next reviewer doesn't re-open a settled
  question.
- **A flow diagram** of what the change actually does, built from the traced data
  flow rather than the file list.
- **Codebase notes** separating what was observed in the code from what was
  inferred on top of it.
- **Progress that persists**, per module, in the page itself.

### Write safety

A bare run never touches GitHub. Writes need an explicit verb, and each verb
authorizes only the write it names.

Before any inline comment is posted, every comment is printed in full — path,
line, side, body — and requires confirmation. **A count is not confirmation.**
On Claude Code a bundled hook enforces this; elsewhere the skill's own gate does.

### Cost

Review lanes are sized to the change, not to a flat policy — none under five hunks
with no risk surface, one up to twenty-five, two once a risk surface is touched, and
three only past sixty hunks *with* a risk surface. Lanes stop once the invariant and
data flow are established rather than reading whole files, and a head that has already
been reviewed is reused rather than re-derived.

## PR Brief

`pr-brief` is the other half. It answers what the change means for users and for the
business, in one pass — no lanes, no subagents, no hunk partitioning. The deep read
already exists in the walkthrough; if one was run against the same head SHA, the brief
reuses its findings instead of repeating the work.

One document, two moments:

- **Before merge** — what a user can now do that they could not, who is affected and
  at what scale, what breaks commercially if this is wrong, what is deliberately out
  of scope, and which metric should move.
- **After merge** — what shipped, what support, sales and docs each need to know, and
  what to watch for.

Every non-obvious claim cites a path, a line and a quote, listed in full at the bottom
of the brief. The renderer rejects an empty evidence list. That constraint is the whole
point: it is the difference between a brief and a press release.

Product language only — no hunks, no symbols, no diff vocabulary. A reader who does not
code can act on it.

## Install

### Claude Code

```text
/plugin marketplace add mukulchugh/skills
/plugin install pr-walkthrough@mukulchugh-skills
```

### Codex

```text
codex plugin marketplace add mukulchugh/skills
codex plugin add pr-walkthrough@mukulchugh-skills
```

### Cursor

Clone this repository, then copy or symlink `plugins/pr-walkthrough` to
`~/.cursor/plugins/local/pr-walkthrough` and reload Cursor. The checked-in Cursor
marketplace manifest is ready for submission; once listed, `/add-plugin` works too.

## Use

```text
/pr-walkthrough owner/repository#123                 read-only
/pr-walkthrough submit owner/repository#123          posts inline comments
/pr-walkthrough publish wiki owner/repository#123    writes a Wiki page
/pr-walkthrough create issues owner/repository#123   opens issues
/pr-walkthrough plan fixes owner/repository#123     read-only, proposes changes

/pr-brief owner/repository#123                       read-only
/pr-brief comment owner/repository#123               posts one PR comment
```

Reviews are archived under `~/.local/share/pr-walkthrough/reviews/`, keyed by
repository, PR and head SHA, so any agent or shell can find the latest one:

```bash
render_review.py --list-reviews
render_review.py --latest owner/repository#123
```

## Optional pieces

**`--serve`** — starts a localhost-only writer so the open page can record reading
progress to disk. Opt-in; the artifact works normally without it.

**`--skeleton`** — `parse_diff.py --skeleton` emits a guide-shaped scaffold with the
real hunks already grouped, so they never have to be assembled by hand.

**Hooks** (Claude Code only, in `plugins/pr-walkthrough/hooks/`) — a publish gate
that blocks unconfirmed GitHub writes while a review is in flight, a background
watcher that reports a finished walkthrough, and a session-start injector for the
cached stack profile. Codex and Cursor behaviour is unchanged.

## Develop

```bash
python3 scripts/validate_package.py
```

Checks every manifest, runs every script's self-check, and verifies each hook path
exists and is executable. No dependencies to install. CI runs it on Linux, macOS
and Windows.

See [CHANGELOG.md](CHANGELOG.md) for release notes.

MIT licensed.
