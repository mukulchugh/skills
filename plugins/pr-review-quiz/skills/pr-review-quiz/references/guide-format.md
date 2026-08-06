# Guide input format

Create UTF-8 JSON with this shape. Use `null` for missing old/new line numbers. Keep all strings plain text; the renderer escapes them.

```json
{
  "meta": {
    "repository": "owner/repo",
    "pr_number": 123,
    "url": "https://github.com/owner/repo/pull/123",
    "title": "Add retry policy",
    "base_ref": "main",
    "head_ref": "retry-policy",
    "head_sha": "full commit sha",
    "generated_at": "2026-08-06T10:00:00Z",
    "summary": "The PR adds persisted retry configuration and wires it into job execution.",
    "verdict": "Needs changes"
  },
  "stats": { "files": 4, "additions": 120, "deletions": 18 },
  "review_process": {
    "mode": "full",
    "execution": "native_parallel",
    "merge_base_sha": "full merge-base commit sha",
    "passes": [
      { "lane": "intent and standards", "status": "completed", "summary": "Checked stated requirements, repository rules, scope, and complexity." },
      { "lane": "correctness and reliability", "status": "completed", "summary": "Traced changed data flows, contracts, permissions, and concurrency." },
      { "lane": "tests and compatibility", "status": "completed", "summary": "Checked coverage, compatibility, performance, and public contracts." }
    ],
    "limitations": []
  },
  "hunk_inventory": ["src/job.ts#0", "src/runner.ts#0", "src/job.test.ts#0"],
  "units": [
    {
      "id": "retry-policy",
      "kind": "change",
      "risk": "read-closely",
      "title": "Persist and execute retry policy",
      "context": "The model stores retry policy and the runner consumes it when a job fails.",
      "review_focus": ["Fallback behavior for old rows", "Retry limit boundary"],
      "files": [
        {
          "path": "src/job.ts",
          "role": "schema_or_model",
          "hunks": [
            {
              "id": "src/job.ts#0",
              "header": "@@ -10,6 +10,7 @@",
              "lines": [
                { "type": "context", "old_line": 10, "new_line": 10, "text": "export interface Job {" },
                { "type": "add", "old_line": null, "new_line": 11, "text": "  retryLimit: number" }
              ]
            }
          ]
        }
      ],
      "quiz": [
        {
          "question": "Where does an old persisted Job get its retry limit?",
          "answer": "The deserializer supplies the compatibility default before Runner sees it.",
          "why": "Without that boundary, existing rows change runtime behavior or fail to load."
        }
      ]
    }
  ],
  "findings": [
    {
      "priority": "P1",
      "title": "Default old jobs before execution",
      "body": "Jobs persisted before this field was added deserialize it as undefined, so the first failure bypasses the intended retry cap.",
      "path": "src/job.ts",
      "line": 11,
      "side": "RIGHT",
      "unit_id": "retry-policy",
      "confidence": 9,
      "found_by": ["correctness and reliability", "tests and compatibility"],
      "evidence": [
        { "path": "src/job.ts", "line": 11, "quote": "retryLimit: number" },
        { "path": "src/deserialize.ts", "line": 28, "quote": "return JSON.parse(raw) as Job" }
      ]
    }
  ],
  "disproved": [
    {
      "claim": "Two concurrent runners can both schedule the final retry.",
      "why_not": "The attempt counter is incremented inside the same transaction that claims the job, so the second runner reads the incremented value.",
      "evidence": [
        { "path": "src/runner.ts", "line": 64, "quote": "await tx.update(job).set({ attempts: job.attempts + 1 })" }
      ]
    }
  ],
  "learning": {
    "architecture": ["Job is the persisted contract; Runner owns execution policy."],
    "data_flows": [
      {
        "title": "Failure to retry",
        "steps": ["Runner records the failure", "Policy computes the next attempt", "Queue schedules the retry"],
        "files": ["src/runner.ts", "src/policy.ts", "src/queue.ts"]
      }
    ],
    "invariants": ["A job must never schedule more than retryLimit retries."],
    "gotchas": ["Persisted rows created before the migration have no retryLimit field."]
  }
}
```

## Validation rules

- Make every `units[].id` unique.
- Use `kind` `change` or `tests`.
- Use risk `skim`, `review`, or `read-closely`.
- Use roles `schema_or_model`, `core_logic`, `consumer_or_call_site`, `test`, or `config_or_generated`.
- Make the set of rendered hunk ids exactly equal `hunk_inventory`; do not duplicate a hunk.
- Use diff line types `add`, `del`, or `context`.
- Use finding priority `P0` through `P3`; line must be positive and side `LEFT` or `RIGHT`.
- Anchor `RIGHT` findings to a matching `new_line` and `LEFT` findings to a matching `old_line`. The renderer rejects unmatched anchors.
- Set finding confidence from 7 through 10 and include at least one exact evidence quote with a positive source line. Evidence may point outside the diff when it proves the affected contract.
- Set `found_by` to the lanes that reached the finding independently. Every entry must match a `review_process.passes[].lane`; the renderer rejects an unknown lane. Omit it when only one lane ran. Convergence across lanes is a stronger signal than a self-assigned score, so record it rather than folding it into `confidence`.
- Put every candidate that was investigated and cleared in `disproved`, with the `claim` as it was raised and `why_not` naming the specific reason it fails. Include the evidence that settles it whenever a quote exists. This is not optional bookkeeping: an unrecorded disproof is re-litigated by the next reviewer, and re-argued questions are the most expensive kind. Record a disproof even when it was obvious to you.
- Use one to three quiz items per unit only when they teach a decision, flow, invariant, or gotcha.
- Record review mode, execution mode, merge base, every requested lane, and any limitations in `review_process`. Use pass status `completed`, `fallback`, or `failed`.
- Prefix every architecture, invariant, and gotcha claim with `Observed:` or `Inference:` and include a path, symbol, or line reference in the claim.

The Wiki draft intentionally includes explanations, architecture, flows, invariants, gotchas, and quizzes but omits the full diff and review findings.
