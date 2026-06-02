#!/usr/bin/env python3
"""Fail when tracked top-level Python modules are missing from Dockerfile COPYs."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def tracked_root_python_modules(repo_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        path
        for path in result.stdout.splitlines()
        if path.endswith(".py") and "/" not in path
    }


def dockerfile_copy_sources(dockerfile: Path) -> set[str]:
    sources: set[str] = set()
    for raw_line in dockerfile.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parts = shlex.split(line)
        except ValueError:
            continue
        if not parts or parts[0].upper() != "COPY":
            continue
        copy_args = [part for part in parts[1:] if not part.startswith("--")]
        if len(copy_args) < 2:
            continue
        sources.update(source.rstrip("/") for source in copy_args[:-1])
    return sources


def missing_dockerfile_copies(repo_root: Path, dockerfile_name: str) -> list[str]:
    dockerfile = repo_root / dockerfile_name
    modules = tracked_root_python_modules(repo_root)
    copied = dockerfile_copy_sources(dockerfile)
    return sorted(module for module in modules if module not in copied)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that tracked top-level Python modules are copied into the "
            "Docker image."
        )
    )
    parser.add_argument(
        "--dockerfile",
        default="Dockerfile",
        help="Dockerfile path relative to the repository root.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    missing = missing_dockerfile_copies(repo_root, args.dockerfile)
    if not missing:
        print("Dockerfile copies all tracked top-level Python modules.")
        return 0

    print("Dockerfile is missing COPY entries for tracked root Python modules:")
    for module in missing:
        print(f"- {module}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
