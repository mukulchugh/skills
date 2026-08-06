#!/usr/bin/env python3
"""Poll for a finished manual PR walkthrough and wake the session to report it."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POLL_INTERVAL_SECONDS = 5
MAX_WALL_SECONDS = 8 * 60 * 60


def library_root() -> Path:
    configured = os.environ.get("PR_REVIEW_QUIZ_HOME")
    if configured:
        return Path(configured).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home).expanduser() / "pr-review-quiz"
    return Path.home() / ".local" / "share" / "pr-review-quiz"


def iter_progress_paths(root: Path) -> list[Path]:
    found: list[Path] = []
    for latest_path in root.glob("reviews/*/*/pr-*/latest.json"):
        try:
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            snapshot = str(latest.get("snapshot", "")).strip()
            if not snapshot or "/" in snapshot or snapshot in (".", ".."):
                continue
            progress_path = latest_path.parent / snapshot / "progress.json"
            if progress_path.is_file():
                found.append(progress_path)
        except Exception:
            continue
    return found


def check_and_stamp(progress_path: Path) -> str | None:
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(progress, dict) or "reported_at" in progress:
        return None
    total = progress.get("total")
    reviewed = progress.get("reviewed")
    if not isinstance(total, int) or not isinstance(reviewed, int):
        return None
    if total <= 0 or reviewed < total:
        return None

    progress["reported_at"] = datetime.now(timezone.utc).isoformat()
    try:
        temp_path = progress_path.with_name(f".progress-{os.getpid()}.tmp")
        temp_path.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
        temp_path.chmod(0o600)
        os.replace(temp_path, progress_path)
    except Exception:
        return None

    repository = progress.get("repository", "unknown/unknown")
    pr = progress.get("pr", "?")
    return f"pr-review-quiz: manual walkthrough finished for {repository}#{pr} ({reviewed}/{total} units reviewed)."


def main() -> None:
    try:
        root = library_root()
        if not root.is_dir():
            sys.exit(0)
        deadline = time.monotonic() + MAX_WALL_SECONDS
        while time.monotonic() < deadline:
            for progress_path in iter_progress_paths(root):
                message = check_and_stamp(progress_path)
                if message:
                    print(message, file=sys.stderr)
                    sys.exit(2)
            time.sleep(POLL_INTERVAL_SECONDS)
        sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
