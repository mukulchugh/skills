#!/usr/bin/env python3
"""Parse a frozen git diff into stable PR Walkthrough hunks."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=text,
        encoding="utf-8" if text else None,
        errors="surrogateescape" if text else None,
    )


def parse_patch(path: str, patch: str) -> list[dict[str, Any]]:
    hunks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    old_line = new_line = 0
    for raw_line in patch.splitlines():
        match = HUNK_RE.match(raw_line)
        if match:
            old_line, new_line = int(match.group(1)), int(match.group(3))
            current = {"id": f"{path}#{len(hunks)}", "header": raw_line, "lines": []}
            hunks.append(current)
            continue
        if current is None or raw_line.startswith("\\ No newline at end of file") or not raw_line:
            continue
        marker, value = raw_line[0], raw_line[1:]
        if marker == "+":
            current["lines"].append({"type": "add", "old_line": None, "new_line": new_line, "text": value})
            new_line += 1
        elif marker == "-":
            current["lines"].append({"type": "del", "old_line": old_line, "new_line": None, "text": value})
            old_line += 1
        elif marker == " ":
            current["lines"].append({"type": "context", "old_line": old_line, "new_line": new_line, "text": value})
            old_line += 1
            new_line += 1
    return hunks


def build_inventory(repo: Path, base: str, head: str, context: int = 3) -> dict[str, Any]:
    repo = Path(str(git(repo, "rev-parse", "--show-toplevel")).strip())
    base_sha = str(git(repo, "rev-parse", "--verify", f"{base}^{{commit}}")).strip()
    head_sha = str(git(repo, "rev-parse", "--verify", f"{head}^{{commit}}")).strip()
    raw_paths = git(repo, "diff", "--name-only", "-z", base_sha, head_sha, text=False)
    assert isinstance(raw_paths, bytes)
    paths = [os.fsdecode(value) for value in raw_paths.split(b"\0") if value]
    files: dict[str, list[dict[str, Any]]] = {}
    skipped: list[str] = []
    additions = deletions = 0
    for path in paths:
        patch = str(
            git(
                repo,
                "diff",
                "--no-color",
                "--no-ext-diff",
                f"--unified={context}",
                base_sha,
                head_sha,
                "--",
                path,
            )
        )
        hunks = parse_patch(path, patch)
        if not hunks:
            skipped.append(path)
            continue
        files[path] = hunks
        additions += sum(line["type"] == "add" for hunk in hunks for line in hunk["lines"])
        deletions += sum(line["type"] == "del" for hunk in hunks for line in hunk["lines"])
    return {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "order": list(files),
        "files": files,
        "hunk_inventory": [hunk["id"] for hunks in files.values() for hunk in hunks],
        "stats": {"files": len(paths), "additions": additions, "deletions": deletions},
        "skipped_without_text_hunks": skipped,
    }


TEST_DIR_TOKENS = {"test", "tests", "spec", "specs", "__tests__", "__specs__"}
TEST_NAME_RE = re.compile(r"(^|[._-])(test|spec)([._-]|$)")
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".lock"}
LOCK_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "cargo.lock",
    "poetry.lock",
    "gemfile.lock",
    "composer.lock",
}


def is_test_path(path: str) -> bool:
    segments = path.lower().split("/")
    if any(segment in TEST_DIR_TOKENS for segment in segments):
        return True
    return bool(TEST_NAME_RE.search(segments[-1]))


def guess_role(path: str) -> str:
    lower = path.lower()
    name = lower.rsplit("/", 1)[-1]
    if name in LOCK_FILENAMES or Path(name).suffix in CONFIG_EXTENSIONS or "generated" in lower:
        return "config_or_generated"
    return "core_logic"


def top_level_dir(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else "(root)"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unit"


def unique_id(base: str, used: set[str]) -> str:
    candidate, suffix = base, 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def build_skeleton(inventory: dict[str, Any], repo_slug: str) -> dict[str, Any]:
    groups: dict[str, list[str]] = {}
    test_paths: list[str] = []
    for path in inventory["order"]:
        if is_test_path(path):
            test_paths.append(path)
        else:
            groups.setdefault(top_level_dir(path), []).append(path)

    used_ids: set[str] = set()
    units: list[dict[str, Any]] = []
    for dirname, paths in groups.items():
        units.append(
            {
                "id": unique_id(f"change-{slugify(dirname)}", used_ids),
                "kind": "change",
                "risk": "review",
                "title": f"TODO: describe the {dirname} changes",
                "context": "TODO: explain what this unit changes and why it matters",
                "review_focus": ["TODO: what should a reviewer focus on here"],
                "files": [
                    {"path": path, "role": guess_role(path), "hunks": inventory["files"][path]}
                    for path in paths
                ],
                "quiz": [],
            }
        )
    if test_paths:
        units.append(
            {
                "id": unique_id("tests", used_ids),
                "kind": "tests",
                "risk": "review",
                "title": "TODO: describe the test coverage",
                "context": "TODO: explain what these tests verify",
                "review_focus": ["TODO: what should a reviewer focus on here"],
                "files": [
                    {"path": path, "role": "test", "hunks": inventory["files"][path]}
                    for path in test_paths
                ],
                "quiz": [],
            }
        )

    return {
        "meta": {
            "repository": f"TODO: owner/{repo_slug}",
            "pr_number": 1,
            "url": f"https://github.com/OWNER/{repo_slug}/pull/1",
            "title": "TODO: fill in the PR title",
            "base_ref": "",
            "head_ref": "",
            "head_sha": inventory["head_sha"],
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "summary": "TODO: summarize what this PR changes and why",
            "verdict": "",
        },
        "stats": dict(inventory["stats"]),
        "review_process": {
            "mode": "full",
            "execution": "single",
            "merge_base_sha": inventory["base_sha"],
            "passes": [
                {
                    "lane": "TODO: name this review pass",
                    "status": "completed",
                    "summary": "TODO: summarize what this pass checked",
                }
            ],
            "limitations": [],
        },
        "hunk_inventory": list(inventory["hunk_inventory"]),
        "units": units,
        "findings": [],
        "learning": {"architecture": [], "data_flows": [], "invariants": [], "gotchas": []},
    }


def self_check() -> None:
    hunks = parse_patch(
        "src/example.py",
        """diff --git a/src/example.py b/src/example.py
@@ -2,2 +2,3 @@ def example():
 keep()
-old()
+new()
+extra()
""",
    )
    assert hunks[0]["id"] == "src/example.py#0"
    assert hunks[0]["lines"] == [
        {"type": "context", "old_line": 2, "new_line": 2, "text": "keep()"},
        {"type": "del", "old_line": 3, "new_line": None, "text": "old()"},
        {"type": "add", "old_line": None, "new_line": 3, "text": "new()"},
        {"type": "add", "old_line": None, "new_line": 4, "text": "extra()"},
    ]

    def hunk(path: str, index: int) -> dict[str, Any]:
        return {
            "id": f"{path}#{index}",
            "header": "@@ -1,1 +1,1 @@",
            "lines": [{"type": "context", "old_line": 1, "new_line": 1, "text": "noop"}],
        }

    files = {
        "src/app.py": [hunk("src/app.py", 0)],
        "src/latest.py": [hunk("src/latest.py", 0)],
        "src/utils/helper.py": [hunk("src/utils/helper.py", 0), hunk("src/utils/helper.py", 1)],
        "tests/test_app.py": [hunk("tests/test_app.py", 0)],
        "web/__tests__/widget.js": [hunk("web/__tests__/widget.js", 0)],
        "web/widget.test.ts": [hunk("web/widget.test.ts", 0)],
        "api/handler.spec.ts": [hunk("api/handler.spec.ts", 0)],
        "lib/util_test.py": [hunk("lib/util_test.py", 0)],
        "package-lock.json": [hunk("package-lock.json", 0)],
    }
    inventory = {
        "base_sha": "b" * 40,
        "head_sha": "h" * 40,
        "order": list(files),
        "files": files,
        "hunk_inventory": [item["id"] for group in files.values() for item in group],
        "stats": {"files": 9, "additions": 0, "deletions": 0},
        "skipped_without_text_hunks": [],
    }
    skeleton = build_skeleton(inventory, "example-repo")
    rendered_ids = [
        item["id"] for unit in skeleton["units"] for file in unit["files"] for item in file["hunks"]
    ]
    assert len(rendered_ids) == len(set(rendered_ids))
    assert sorted(rendered_ids) == sorted(inventory["hunk_inventory"])
    assert set(skeleton["hunk_inventory"]) == set(rendered_ids)
    for unit in skeleton["units"]:
        assert unit["kind"] in {"change", "tests"}
        assert unit["risk"] in {"skim", "review", "read-closely"}
        for file in unit["files"]:
            assert file["role"] in {
                "schema_or_model",
                "core_logic",
                "consumer_or_call_site",
                "test",
                "config_or_generated",
            }
    tests_unit = next(unit for unit in skeleton["units"] if unit["kind"] == "tests")
    assert {file["path"] for file in tests_unit["files"]} == {
        "tests/test_app.py",
        "web/__tests__/widget.js",
        "web/widget.test.ts",
        "api/handler.spec.ts",
        "lib/util_test.py",
    }
    assert all(file["role"] == "test" for file in tests_unit["files"])
    unit_ids = {unit["id"] for unit in skeleton["units"]}
    assert "change-web" not in unit_ids and "change-api" not in unit_ids
    lock_unit = next(unit for unit in skeleton["units"] if unit["id"] == "change-root")
    assert lock_unit["files"][0]["role"] == "config_or_generated"
    src_unit = next(unit for unit in skeleton["units"] if unit["id"] == "change-src")
    assert {file["path"]: file["role"] for file in src_unit["files"]}["src/latest.py"] == "core_logic"
    print("parse_diff.py self-check passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, help="output JSON path")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base", help="frozen merge-base SHA or ref")
    parser.add_argument("--head", default="HEAD", help="frozen PR head SHA or ref")
    parser.add_argument("--context", type=int, default=3)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument(
        "--skeleton",
        action="store_true",
        help="write a guide-shaped scaffold (prose left as TODO placeholders) instead of the plain inventory",
    )
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if args.output is None or args.base is None:
        parser.error("output and --base are required")
    if args.context < 0:
        parser.error("--context must not be negative")
    inventory = build_inventory(args.repo, args.base, args.head, args.context)
    if args.skeleton:
        payload: dict[str, Any] = build_skeleton(inventory, args.repo.resolve().name or "repo")
    else:
        payload = inventory
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for path in inventory["order"]:
        hunks = inventory["files"][path]
        additions = sum(line["type"] == "add" for hunk in hunks for line in hunk["lines"])
        deletions = sum(line["type"] == "del" for hunk in hunks for line in hunk["lines"])
        print(f"{len(hunks):>3} hunks  +{additions:<4} -{deletions:<4}  {path}")
    print(f"wrote {args.output} ({len(inventory['hunk_inventory'])} hunks)")


if __name__ == "__main__":
    main()
