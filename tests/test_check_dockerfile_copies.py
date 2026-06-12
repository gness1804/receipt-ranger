"""Tests for scripts/check_dockerfile_copies.py (CFS feature #15 / GH #87)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_dockerfile_copies as checker  # noqa: E402


class TestLocalTargets:
    def test_separates_root_modules_and_packages(self):
        tracked = [
            "app.py",
            "main.py",
            "README.md",
            "validation/__init__.py",
            "validation/detector.py",
            "validation/README.md",
            "assets/logo.svg",
        ]
        modules, packages = checker.local_targets(tracked)
        assert modules == {"app": "app.py", "main": "main.py"}
        assert packages == {
            "validation": ["validation/__init__.py", "validation/detector.py"]
        }

    def test_dir_without_init_is_not_a_package(self):
        modules, packages = checker.local_targets(["scripts/helper.py"])
        assert modules == {}
        assert packages == {}


class TestImportsInFile:
    def test_finds_lazy_function_level_imports(self, tmp_path):
        source = tmp_path / "mod.py"
        source.write_text(
            "import os\n"
            "from validation.detector import Detector\n"
            "def f():\n"
            "    from session import decrypt_api_key\n"
            "    import sheets\n"
        )
        names = checker.imports_in_file(source)
        assert {"os", "validation", "session", "sheets"} <= names

    def test_ignores_relative_imports(self, tmp_path):
        source = tmp_path / "mod.py"
        source.write_text("from . import sibling\nfrom .other import thing\n")
        assert checker.imports_in_file(source) == set()


class TestRuntimeModules:
    def _make_repo(self, tmp_path):
        (tmp_path / "app.py").write_text("import helper\n")
        (tmp_path / "helper.py").write_text("from pkg.sub import x\n")
        (tmp_path / "dev_only.py").write_text("import helper\n")
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "sub.py").write_text("import deep\n")
        (tmp_path / "deep.py").write_text("import os\n")
        return [
            "app.py",
            "helper.py",
            "dev_only.py",
            "deep.py",
            "pkg/__init__.py",
            "pkg/sub.py",
        ]

    def test_walks_transitive_imports_from_entrypoints(self, tmp_path):
        tracked = self._make_repo(tmp_path)
        modules, packages = checker.local_targets(tracked)
        required = checker.runtime_modules(tmp_path, modules, packages, ("app.py",))
        assert set(required) == {"app", "helper", "pkg", "deep"}
        assert required["app"] == "entrypoint"
        assert required["helper"] == "app.py"
        assert required["deep"] == "pkg/sub.py"

    def test_unimported_module_is_not_required(self, tmp_path):
        tracked = self._make_repo(tmp_path)
        modules, packages = checker.local_targets(tracked)
        required = checker.runtime_modules(tmp_path, modules, packages, ("app.py",))
        assert "dev_only" not in required


class TestDockerfileCopied:
    def test_parses_sources_and_normalizes(self):
        text = (
            "FROM python:3.11-slim\n"
            "COPY requirements.txt .\n"
            "COPY app.py .\n"
            "COPY ./main.py .\n"
            "COPY validation/ validation/\n"
            "COPY --chown=app:app session.py sheets.py /app/\n"
        )
        copied = checker.dockerfile_copied(text)
        assert copied == {
            "requirements.txt",
            "app.py",
            "main.py",
            "validation",
            "session.py",
            "sheets.py",
        }

    def test_joins_backslash_continuations(self):
        text = "COPY app.py \\\n    main.py \\\n    /app/\n"
        assert checker.dockerfile_copied(text) == {"app.py", "main.py"}

    def test_non_copy_lines_ignored(self):
        text = "RUN pip install x\nEXPOSE 8501\n"
        assert checker.dockerfile_copied(text) == set()


class TestFindMissing:
    MODULES = {"app": "app.py", "image_conversion": "image_conversion.py"}

    def test_flags_missing_module_with_suggested_fix(self):
        required = {"app": "entrypoint", "image_conversion": "main.py"}
        missing = checker.find_missing(required, {"app.py"}, self.MODULES)
        assert missing == [
            (
                "image_conversion.py",
                "main.py",
                "COPY image_conversion.py .",
            )
        ]

    def test_flags_missing_package_with_suggested_fix(self):
        required = {"validation": "main.py"}
        missing = checker.find_missing(required, set(), self.MODULES)
        assert missing == [("validation/", "main.py", "COPY validation/ validation/")]

    def test_copy_dot_covers_everything(self):
        required = {"app": "entrypoint", "validation": "main.py"}
        assert checker.find_missing(required, {"."}, self.MODULES) == []

    def test_nothing_missing(self):
        required = {"app": "entrypoint"}
        assert checker.find_missing(required, {"app.py"}, self.MODULES) == []


class TestMainAgainstRealRepo:
    def test_current_repo_passes(self, capsys):
        """Acceptance: the repo's actual Dockerfile covers all runtime modules."""
        assert checker.main([]) == 0
        assert "✅" in capsys.readouterr().out

    def test_missing_copy_line_fails(self, tmp_path, capsys):
        """Acceptance: dropping a COPY line fails with a message naming it."""
        repo_root = Path(__file__).resolve().parent.parent
        real = (repo_root / "Dockerfile").read_text()
        broken = tmp_path / "Dockerfile"
        broken.write_text(real.replace("COPY image_conversion.py .\n", ""))
        assert checker.main(["--dockerfile", str(broken)]) == 1
        out = capsys.readouterr().out
        assert "image_conversion.py" in out
        assert "COPY image_conversion.py ." in out
