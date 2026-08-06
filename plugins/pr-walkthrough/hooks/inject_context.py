#!/usr/bin/env python3
"""Inject the cached stack/MCP profile for the current repository at session start."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TTL_DAYS = 14
MAX_CONTEXT_CHARS = 600

SSH_REMOTE = re.compile(r"^git@github\.com:([^/]+)/(.+?)(?:\.git)?/?$")
HTTPS_REMOTE = re.compile(r"^(?:https?|ssh|git)://(?:[^@/]+@)?github\.com[/:]([^/]+)/(.+?)(?:\.git)?/?$")


def library_root() -> Path:
    configured = os.environ.get("PR_WALKTHROUGH_HOME")
    if configured:
        return Path(configured).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home).expanduser() / "pr-walkthrough"
    return Path.home() / ".local" / "share" / "pr-walkthrough"


def parse_github_remote(url: str) -> tuple[str, str] | None:
    url = url.strip()
    match = SSH_REMOTE.match(url) or HTTPS_REMOTE.match(url)
    if not match:
        return None
    owner, repo = match.group(1).strip(), match.group(2).strip()
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return owner, repo


def safe_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")


def is_expired(detected_at: Any, ttl_days: Any) -> bool:
    try:
        ttl = int(ttl_days) if ttl_days is not None else DEFAULT_TTL_DAYS
    except (TypeError, ValueError):
        ttl = DEFAULT_TTL_DAYS
    detected = datetime.fromisoformat(str(detected_at).replace("Z", "+00:00"))
    if detected.tzinfo is None:
        detected = detected.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - detected).total_seconds()
    return age_seconds > ttl * 86400


def build_context_text(profile: dict[str, Any], owner: str, repo: str) -> str | None:
    stack = profile.get("stack")
    if isinstance(stack, list):
        stack_text = ", ".join(str(item) for item in stack[:8] if str(item).strip())
    elif isinstance(stack, str):
        stack_text = stack.strip()
    else:
        stack_text = ""

    servers = profile.get("mcp")
    bits: list[str] = []
    if isinstance(servers, list):
        for server in servers[:5]:
            if isinstance(server, dict):
                name = str(server.get("server", "")).strip()
                use_for = str(server.get("use_for", "")).strip()
                if name and use_for:
                    bits.append(f"{name} ({use_for})")
                elif name:
                    bits.append(name)
            else:
                item = str(server).strip()
                if item:
                    bits.append(item)
    servers_text = "; ".join(bits)

    if not stack_text and not servers_text:
        return None

    parts = [f"pr-walkthrough cached profile for {owner}/{repo}."]
    if stack_text:
        parts.append(f"Stack: {stack_text}.")
    if servers_text:
        parts.append(f"MCP servers for grounding: {servers_text}.")
    parts.append(
        "These are READ-ONLY during review; confirming the profile is what clears "
        "the question, so do not ask the user again."
    )
    text = " ".join(parts)
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[: MAX_CONTEXT_CHARS - 1].rstrip() + "…"
    return text


def emit(text: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }))


def main() -> None:
    try:
        payload_raw = sys.stdin.read()
        payload = json.loads(payload_raw) if payload_raw.strip() else {}
        cwd = str(payload.get("cwd") or os.getcwd())

        result = subprocess.run(
            ["git", "-C", cwd, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode != 0:
            sys.exit(0)
        parsed = parse_github_remote(result.stdout)
        if parsed is None:
            sys.exit(0)
        owner, repo = parsed

        context_path = library_root() / "context" / f"{safe_segment(owner)}--{safe_segment(repo)}.json"
        if not context_path.is_file():
            sys.exit(0)
        profile = json.loads(context_path.read_text(encoding="utf-8"))
        if not isinstance(profile, dict):
            sys.exit(0)
        if not profile.get("confirmed_by_user"):
            sys.exit(0)
        if is_expired(profile.get("detected_at"), profile.get("ttl_days")):
            sys.exit(0)

        text = build_context_text(profile, owner, repo)
        if text:
            emit(text)
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
