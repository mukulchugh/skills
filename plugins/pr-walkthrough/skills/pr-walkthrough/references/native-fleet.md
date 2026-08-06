# Native review fleet

Use one portable contract across runtimes. Do not require a particular agent name, manifest format, model, or nesting feature.

## Coordinator contract

1. Detect whether native delegation is exposed and allowed. Never block the review when it is absent.
2. Give every worker a self-contained immutable packet: PR identity, frozen SHAs, diff hash and scope, repository guidance, rubric, and finding schema. Do not assume it inherits this skill, conversation history, file reads, or peer conclusions. Instruct it not to invoke this skill, delegate again, edit files, or publish anything.
3. Run up to three read-only evidence passes concurrently: intent/standards; correctness/security/data flow; tests/compatibility/maintainability. Require path, changed-line anchor, priority, claim, triggering scenario, causal trace, exact evidence quotes, disproof checks, confidence, and suggested direction; `no finding` is valid.
4. Wait for every requested pass. The coordinator verifies candidates against the current diff and code paths, rejects speculation, merges root causes, resolves disagreement, and records missing/failed lanes.
5. Permit only the coordinator to render final findings or perform explicitly requested writes. Re-fetch the head SHA immediately before any GitHub mutation.
6. When delegation is unavailable or a lane fails, run that lane sequentially with a separate candidate list. Call this logical separation, not context isolation.
7. Keep over-engineering advice separate from correctness findings. It may shorten the change or become a review focus item, but it is actionable only when it causes concrete maintenance or behavior cost.

## Runtime adapters

- Claude Code subagents have independent context windows, tool controls, permissions, parallel execution, and explicit skill preloading. A normal subagent does not inherit the parent conversation or already-invoked skill, so the review packet must be self-contained. Use read-only Explore/custom agents where available; do not depend on nested subagents. [Official Claude Code subagent documentation](https://code.claude.com/docs/en/sub-agents)
- Codex supports parallel subagent threads and coordinator synthesis; read-heavy parallel work is preferred, while concurrent writes require caution. Use the runtime's collaboration/subagent capability and inherit the active sandbox/approval policy; keep workers read-only. [Official Codex subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents.md) and [Codex app worktrees](https://openai.com/index/introducing-the-codex-app/)
- Cursor supports independent parallel subagents with separate context and Agent Skills in both editor and CLI. Use native subagents or `/multitask` when available, but keep the same worker packet and coordinator gate. [Cursor 2.4 official changelog](https://cursor.com/changelog/2-4), [Cursor subagent docs](https://cursor.com/docs/subagents), and [Cursor 2.5 async subagents](https://cursor.com/changelog/2-5)

Platform-specific agent definitions are optional adapters. The distributable core remains `SKILL.md`, the shared JSON contract, and deterministic scripts.
