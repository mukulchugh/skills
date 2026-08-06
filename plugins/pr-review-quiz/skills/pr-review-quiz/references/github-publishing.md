# GitHub publishing

Perform only the write named by the user. Re-fetch the PR/repository immediately before writing.

## Submit one PR review

Prefer the GitHub connector's create-review operation. Supply:

- the exact `owner/repo` and PR number;
- `commit_id` equal to the reviewed head SHA;
- an explicit event: `COMMENT`, `APPROVE`, or `REQUEST_CHANGES`;
- one concise review body;
- all validated line findings in one `file_comments` array.

Each file comment must use `path`, `body`, `line`, and `side`. Add `start_line` and `start_side` only for a real multi-line range. Do not use deprecated diff positions when line/side is available.

If the connector is unavailable, create an equivalent JSON payload in a permission-restricted temporary file and call:

```bash
gh api repos/OWNER/REPO/pulls/NUMBER/reviews --method POST --input PAYLOAD.json
```

Never place credentials in a command, file, HTML, Wiki page, or chat output. Delete the temporary payload after a successful or failed request.

Use `COMMENT` when the user requested submission but did not specify a review event. Approval and request-changes are human decisions; do not infer them.

Add the reviewed-head marker to the review body and the deterministic fingerprint marker from `SKILL.md` to each inline comment. Exclude fingerprints already present in existing comments. If GitHub rejects an anchor, do not retry it against a guessed line; remove it from `file_comments`, add the finding to the review body, re-confirm the unchanged head SHA, and submit the corrected atomic review.

For a code suggestion, generate the fenced `suggestion` block from separately validated replacement text immediately before submission. Suggestions are only valid on changed `RIGHT`-side lines. If the replacement or range is incomplete, submit prose instead.

Immediately before calling the connector or `gh api`, print the full review for the user to read: the repository, PR number, review event, and every inline comment in full — `path`, `line`, `side`, the complete body text, and any suggestion block. Do not summarize; print all of it.

Require explicit user confirmation of that printed review before submitting. A comment count is not sufficient confirmation — a reviewer cannot approve comments they have not read. If the user declines or does not respond, post nothing.

The skill writes an in-flight marker at `<library_root>/pending/<owner>--<repo>-<pr>.json` when it renders the guide, and deletes it on confirmation or at the end of the run. A marker older than 2 hours is stale; ignore it.

## Publish the Wiki learning page

GitHub Wikis are separate git repositories at `https://github.com/OWNER/REPO.wiki.git`.

1. Confirm the repository has Wiki enabled and the authenticated user can push.
2. Clone the Wiki into a narrow temporary directory using the existing GitHub credential helper. Never embed a token in the URL.
3. Use the renderer's Markdown draft. Name a new page `PR-NUMBER-SHORT-SLUG.md`; update that page only when it already identifies the same PR and head lineage.
4. Add source metadata: PR URL, reviewed head SHA, generated date, and files covered.
5. Inspect the diff, commit only the page, and push normally. Preserve all other pages.
6. Return the page URL `https://github.com/OWNER/REPO/wiki/PR-NUMBER-SHORT-SLUG`.

Do not publish secrets, private customer data, raw environment values, access tokens, or long copied source blocks. Do not edit `_Sidebar.md` or `_Footer.md` unless explicitly requested.

## Create follow-up issues

Search open and closed issues using the finding's root-cause terms and affected symbols before creating anything.

Create an issue only when the user explicitly asks and the follow-up is not already tracked. Use:

```markdown
## Context
Source PR and reviewed head SHA.

## Evidence
Affected paths/symbols and the observed behavior.

## Impact
The concrete scenario and consequence.

## Scope
What belongs in this issue; what does not.

## Acceptance criteria
- Observable completion conditions.
```

Link the guide/Wiki page when available. Keep one root cause per issue. Do not convert speculative learning or a pre-existing curiosity into work automatically.
