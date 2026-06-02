"""Tests for the Dockerfile static copy check."""

import subprocess
from pathlib import Path

from scripts.check_dockerfile_copies import (
    dockerfile_copy_sources,
    missing_dockerfile_copies,
)


def test_dockerfile_copies_current_root_modules():
    dockerfile = Path("Dockerfile")
    root_modules = {
        path.name
        for path in Path(".").glob("*.py")
        if path.is_file()
    }

    assert root_modules <= dockerfile_copy_sources(dockerfile)


def test_missing_dockerfile_copies_reports_tracked_root_module(tmp_path):
    (tmp_path / "app.py").write_text("import image_conversion\n")
    (tmp_path / "image_conversion.py").write_text("")
    (tmp_path / "Dockerfile").write_text(
        "\n".join(
            [
                "FROM python:3.11-slim",
                "COPY app.py .",
            ]
        )
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "add", "app.py", "image_conversion.py", "Dockerfile"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    assert missing_dockerfile_copies(tmp_path, "Dockerfile") == [
        "image_conversion.py"
    ]
