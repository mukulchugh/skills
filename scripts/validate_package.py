#!/usr/bin/env python3
"""Validate the portable plugin package with the standard library only."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "pr-walkthrough"
SKILL = PLUGIN / "skills" / "pr-walkthrough"
NAME = "pr-walkthrough"
VERSION = "1.2.0"


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def hook_commands(node: object) -> list[str]:
    commands: list[str] = []
    if isinstance(node, dict):
        command = node.get("command")
        if isinstance(command, str):
            commands.append(command)
        for value in node.values():
            commands.extend(hook_commands(value))
    elif isinstance(node, list):
        for item in node:
            commands.extend(hook_commands(item))
    return commands


def main() -> None:
    codex_market = load(".agents/plugins/marketplace.json")
    claude_market = load(".claude-plugin/marketplace.json")
    cursor_market = load(".cursor-plugin/marketplace.json")
    codex_plugin = load("plugins/pr-walkthrough/.codex-plugin/plugin.json")
    claude_plugin = load("plugins/pr-walkthrough/.claude-plugin/plugin.json")
    cursor_plugin = load("plugins/pr-walkthrough/.cursor-plugin/plugin.json")

    assert codex_market["plugins"][0]["name"] == NAME
    assert claude_market["plugins"][0]["name"] == NAME
    assert cursor_market["plugins"][0]["name"] == NAME
    for manifest in (codex_plugin, claude_plugin, cursor_plugin):
        assert manifest["name"] == NAME
        assert manifest["version"] == VERSION

    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert skill_text.startswith("---\nname: pr-walkthrough\n")
    for relative in ("scripts/parse_diff.py", "scripts/render_review.py"):
        subprocess.run([sys.executable, str(SKILL / relative), "--self-check"], check=True)

    hooks_manifest = load("plugins/pr-walkthrough/hooks/hooks.json")
    for command in hook_commands(hooks_manifest):
        if "${CLAUDE_PLUGIN_ROOT}" not in command:
            continue
        # Extract the path before substituting: shlex is POSIX-mode by default and
        # eats the backslashes in a resolved Windows path, leaving nothing to check.
        match = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}(\S*)", command)
        assert match, f"hook command has no resolvable script path: {command}"
        script = PLUGIN.joinpath(*match.group(1).strip("/").split("/"))
        assert script.exists(), f"hook command references a missing file: {command}"
        # Windows has no executable bit; os.access(X_OK) there only restates exists().
        if os.name != "nt":
            assert os.access(script, os.X_OK), f"hook command is not executable: {command}"

    forbidden = (
        "guided" + "review",
        "artery" + "labs",
        "nshn" + "tarora",
        "abstrac" + "tions",
    )
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix not in {".md", ".json", ".yaml", ".yml", ".py"}:
            continue
        content = path.read_text(encoding="utf-8").casefold()
        assert not any(term in content for term in forbidden), f"forbidden attribution in {path}"

    print("package validation passed")


if __name__ == "__main__":
    main()
