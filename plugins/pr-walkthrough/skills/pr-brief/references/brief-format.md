# Brief input format

Create UTF-8 JSON with this shape. Keep all strings plain text; the renderer escapes them.

```json
{
  "meta": {
    "repository": "owner/repo",
    "pr_number": 482,
    "url": "https://github.com/owner/repo/pull/482",
    "title": "Add CSV export to the billing dashboard",
    "base_ref": "main",
    "head_ref": "billing-csv-export",
    "head_sha": "full commit sha",
    "generated_at": "2026-08-08T10:00:00Z",
    "stance": "Ship it",
    "headline": "Billing admins can export their invoice history without asking support."
  },
  "stats": { "files": 6, "additions": 340, "deletions": 12 },
  "before_merge": {
    "changes_for_users": [
      { "capability": "Download the last 12 months of invoices as CSV from the billing page.", "previously": "Invoice history was only available by filing a support ticket." }
    ],
    "who_is_affected": [
      { "segment": "Orgs on a paid plan with billing admin access", "scale": "every paid org", "basis": "the export button is unconditional on the billing page" }
    ],
    "if_this_is_wrong": [
      { "risk": "Export includes another org's invoice rows", "consequence": "a cross-tenant data leak on the highest-trust page in the product", "severity": "blocking" }
    ],
    "out_of_scope": [
      "Scheduled or recurring export", "PDF export", "Export of usage line items"
    ],
    "metrics": [
      { "name": "Support tickets tagged 'invoice history'", "expect": "drops toward zero", "how_measured": "ticket volume by tag, week over week" }
    ]
  },
  "after_merge": {
    "shipped": [
      "CSV export button on the billing dashboard, scoped to the viewing org."
    ],
    "support": [
      { "note": "Customers no longer need a ticket for invoice history.", "expect": "questions about the export's date-range limit" }
    ],
    "sales": [
      "Invoice history export is now self-serve, not a manual ask."
    ],
    "docs": [
      { "artifact": "Help article: Requesting invoice history", "why_stale": "tells customers to file a ticket" }
    ],
    "watch_for": [
      "Export requests that time out on large accounts", "Any row scoped to the wrong org"
    ]
  },
  "rollout": {
    "strategy": "Ships with the branch; no flag.",
    "rollback": "Revert removes the button; no data migration.",
    "flags": []
  },
  "evidence": [
    { "claim": "The export query is scoped by the caller's org id.", "path": "src/billing/export.ts", "line": 58, "quote": "WHERE org_id = ctx.orgId" }
  ]
}
```

## Validation rules

- Include `meta`, `stats`, `before_merge`, `after_merge`, `rollout`, and `evidence` — the renderer requires all six top-level sections, even when a section's arrays are empty.
- Set `meta.stance` to one of `Ship it`, `Ship with follow-ups`, or `Hold`.
- Write `meta.headline` as one sentence, product-level, with no file names or symbols.
- Give every non-obvious claim in `before_merge` and `after_merge` a matching entry in `evidence`; the renderer rejects an empty evidence list.
- In every `evidence[]` entry, cite a real `path`, a positive `line`, and the exact `quote` found there. Evidence may point outside the diff when it proves the affected contract.
- In `before_merge.who_is_affected[]`, make `basis` name the actual condition producing the `scale` claim — a flag, a plan tier, a role, or an unconditional code path — not a guess.
- In `before_merge.if_this_is_wrong[]`, make `severity` a short, honest label for how bad the failure is (for example `blocking`, `degraded`, `cosmetic`); do not soften a blocking risk to look shippable. Only `blocking` is special: matched case-insensitively, it sorts to the front and renders strongest. Every other label renders as an ordinary risk, so do not reach for a synonym like `critical` or `P0` and expect the same weight.
- Leave any array empty rather than inventing a placeholder entry; the renderer omits the section instead of printing one.
- Use product and commercial language in every string field. No hunks, no symbols, no diff vocabulary — file paths and line numbers live only in `evidence`.
- When a fact is not knowable from the change (revenue, customer counts, roadmap intent), say so in the relevant prose field instead of omitting the field or guessing a number.
