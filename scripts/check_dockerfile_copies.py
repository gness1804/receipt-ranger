#!/usr/bin/env python3
"""Check that every Python module imported at runtime is COPY'd into the Docker image.

This repo's production app runs from a Docker image whose Dockerfile copies
application files one by one. Twice now, a new root-level module was added and
imported but never COPY'd, so local dev and pytest passed while the container
crashed at startup with ModuleNotFoundError (validation/ in issue #60,
image_conversion.py in issue #85 / v0.13.2). See CFS feature #15 / GH #87.

The check is pure static analysis (no Docker build):

1. Enumerate tracked root-level ``*.py`` modules and top-level packages
   (directories with a tracked ``__init__.py``) via ``git ls-files``.
2. Walk the import graph from the runtime entrypoints (``app.py``,
   ``main.py``) using ``ast``, including imports nested inside functions,
   to find which local modules are actually needed at runtime.
3. Parse the Dockerfile's COPY instructions and fail (exit 1) naming any
   required module that is never copied into the image.

Exits 0 when every runtime module is covered.
"""

import argparse
import ast
import subprocess
import sys
from pathlib import Path

ENTRYPOINTS = ("app.py", "main.py")


def tracked_files(repo_root):
    """Return the list of git-tracked file paths (relative, POSIX-style)."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def local_targets(tracked):
    """Map importable top-level names to their repo paths.

    Returns (modules, packages): ``modules`` maps a root-level module name
    to its ``*.py`` file; ``packages`` maps a top-level package name to the
    list of tracked ``*.py`` files inside it.
    """
    modules = {}
    packages = {}
    package_names = {
        path.split("/", 1)[0]
        for path in tracked
        if path.count("/") == 1 and path.endswith("/__init__.py")
    }
    for path in tracked:
        if "/" not in path and path.endswith(".py"):
            modules[path[: -len(".py")]] = path
        else:
            top = path.split("/", 1)[0]
            if top in package_names and path.endswith(".py"):
                packages.setdefault(top, []).append(path)
    return modules, packages


def imports_in_file(path):
    """Return top-level names of absolute imports anywhere in the file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        sys.exit(f"error: cannot parse {path}: {exc}")
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def runtime_modules(repo_root, modules, packages, entrypoints):
    """Walk the import graph from the entrypoints.

    Returns a dict mapping each required local name to the file that first
    imported it (or "entrypoint" for the entrypoints themselves).
    """
    required = {}
    queue = []
    for entry in entrypoints:
        name = entry[: -len(".py")]
        if name in modules:
            required[name] = "entrypoint"
            queue.append(name)
    while queue:
        name = queue.pop()
        files = [modules[name]] if name in modules else packages[name]
        for rel_path in files:
            for imported in imports_in_file(repo_root / rel_path):
                if imported in required:
                    continue
                if imported in modules or imported in packages:
                    required[imported] = rel_path
                    queue.append(imported)
    return required


def dockerfile_copied(text):
    """Return the set of normalized COPY source paths from a Dockerfile."""
    # Join backslash line continuations so multi-line COPY parses as one line.
    text = text.replace("\\\n", " ")
    sources = set()
    for line in text.splitlines():
        tokens = line.split()
        if not tokens or tokens[0].upper() != "COPY":
            continue
        args = [t for t in tokens[1:] if not t.startswith("--")]
        for src in args[:-1]:  # last token is the destination
            src = src.strip("'\"")
            sources.add(src.removeprefix("./").rstrip("/"))
    return sources


def find_missing(required, copied, modules):
    """Return [(path, importer, suggested fix)] for modules not copied."""
    if "." in copied:  # COPY . . covers everything
        return []
    missing = []
    for name, importer in sorted(required.items()):
        is_module = name in modules
        path = modules[name] if is_module else name + "/"
        if path.removesuffix("/") not in copied:
            fix = f"COPY {path} ." if is_module else f"COPY {path} {path}"
            missing.append((path, importer, fix))
    return missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repo root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--dockerfile",
        type=Path,
        default=None,
        help="Dockerfile path (default: <root>/Dockerfile)",
    )
    args = parser.parse_args(argv)
    repo_root = args.root
    dockerfile = args.dockerfile or repo_root / "Dockerfile"

    modules, packages = local_targets(tracked_files(repo_root))
    required = runtime_modules(repo_root, modules, packages, ENTRYPOINTS)
    copied = dockerfile_copied(dockerfile.read_text(encoding="utf-8"))
    missing = find_missing(required, copied, modules)

    if missing:
        print(f"❌ {dockerfile.name} is missing COPY lines for runtime modules:")
        for path, importer, fix in missing:
            via = (
                "a runtime entrypoint"
                if importer == "entrypoint"
                else f"imported by {importer}"
            )
            print(f"   - {path} ({via}) — add: {fix}")
        print(
            "Without these, the container crashes at startup with "
            "ModuleNotFoundError even though local dev and pytest pass."
        )
        return 1

    names = ", ".join(sorted(required))
    print(f"✅ All runtime modules are COPY'd into the Docker image: {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
