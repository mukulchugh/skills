#!/usr/bin/env python3
"""Parse a frozen git diff into stable PR Review Quiz hunks."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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
    print("parse_diff.py self-check passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, help="output JSON path")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base", help="frozen merge-base SHA or ref")
    parser.add_argument("--head", default="HEAD", help="frozen PR head SHA or ref")
    parser.add_argument("--context", type=int, default=3)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if args.output is None or args.base is None:
        parser.error("output and --base are required")
    if args.context < 0:
        parser.error("--context must not be negative")
    inventory = build_inventory(args.repo, args.base, args.head, args.context)
    args.output.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for path in inventory["order"]:
        hunks = inventory["files"][path]
        additions = sum(line["type"] == "add" for hunk in hunks for line in hunk["lines"])
        deletions = sum(line["type"] == "del" for hunk in hunks for line in hunk["lines"])
        print(f"{len(hunks):>3} hunks  +{additions:<4} -{deletions:<4}  {path}")
    print(f"wrote {args.output} ({len(inventory['hunk_inventory'])} hunks)")


if __name__ == "__main__":
    main()
