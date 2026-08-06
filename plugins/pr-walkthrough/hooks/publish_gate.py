#!/usr/bin/env python3
"""Deny unconfirmed GitHub write operations while a pr-walkthrough review is in flight."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

STALE_AFTER = timedelta(hours=2)

WRITE_SUBCOMMANDS = (
    re.compile(r"\bgh\s+pr\s+review\b"),
    re.compile(r"\bgh\s+pr\s+comment\b"),
    re.compile(r"\bgh\s+issue\s+create\b"),
)
GH_API = re.compile(r"\bgh\s+api\b")
API_METHOD = re.compile(r"(?:--method|-X)\s+(POST|PATCH|PUT|DELETE)\b", re.IGNORECASE)
API_WRITE_PATH = re.compile(r"/(reviews|comments|issues)\b")
# Tolerate global flags between the two words: the wiki flow clones into a temporary
# directory and pushes with `git -C <dir> push`, which a `git\s+push` pattern never sees.
GIT_PUSH = re.compile(r"\bgit\b[^|;&\n]*?\bpush\b")
MUTATION_WORD = re.compile(r"(create|update|add|submit|merge|delete|post)", re.IGNORECASE)
GITHUB_SERVER = re.compile(r"github", re.IGNORECASE)


def library_root() -> Path:
    configured = os.environ.get("PR_WALKTHROUGH_HOME")
    if configured:
        return Path(configured).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home).expanduser() / "pr-walkthrough"
    return Path.home() / ".local" / "share" / "pr-walkthrough"


def load_live_markers(pending_dir: Path) -> list[dict[str, Any]]:
    live: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for entry in pending_dir.glob("*.json"):
        marker: dict[str, Any] | None = None
        try:
            marker = json.loads(entry.read_text(encoding="utf-8"))
            created_raw = marker.get("created_at")
            created_at = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if now - created_at > STALE_AFTER:
                entry.unlink(missing_ok=True)
                continue
            if not marker.get("repository") or not marker.get("pr"):
                entry.unlink(missing_ok=True)
                continue
            live.append(marker)
        except Exception:
            entry.unlink(missing_ok=True)
    return live


def is_write_bash_command(command: str) -> bool:
    if GIT_PUSH.search(command) and ".wiki" in command:
        return True
    for pattern in WRITE_SUBCOMMANDS:
        if pattern.search(command):
            return True
    if GH_API.search(command) and API_METHOD.search(command) and API_WRITE_PATH.search(command):
        return True
    return False


def is_write_mcp_tool(tool_name: str) -> bool:
    if not GITHUB_SERVER.search(tool_name):
        return False
    return bool(MUTATION_WORD.search(tool_name))


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def build_reason(marker: dict[str, Any]) -> str:
    repository = marker.get("repository", "unknown/unknown")
    pr = marker.get("pr", "?")
    return (
        f"A pr-walkthrough review is in flight for {repository}#{pr}. "
        "Inline comments must be previewed in full and confirmed by the user "
        "before any GitHub write happens. Show the user the full pending "
        "review; their explicit confirmation is what clears the marker, "
        "after which this write can be retried."
    )


def main() -> None:
    try:
        root = library_root()
        pending_dir = root / "pending"
        try:
            scan = os.scandir(pending_dir)
        except OSError:
            sys.exit(0)
        try:
            has_entries = next(scan, None) is not None
        finally:
            scan.close()
        if not has_entries:
            sys.exit(0)

        live_markers = load_live_markers(pending_dir)
        if not live_markers:
            sys.exit(0)

        payload_raw = sys.stdin.read()
        payload = json.loads(payload_raw) if payload_raw.strip() else {}
        tool_name = str(payload.get("tool_name", ""))
        tool_input = payload.get("tool_input") or {}

        is_write = False
        if tool_name == "Bash":
            command = str(tool_input.get("command", ""))
            is_write = is_write_bash_command(command)
        elif GITHUB_SERVER.search(tool_name):
            is_write = is_write_mcp_tool(tool_name)

        if is_write:
            deny(build_reason(live_markers[0]))
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
