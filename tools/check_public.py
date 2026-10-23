"""Fail when anything internal would be published: in the built wheel, the source distribution,
the public documents, or the whole public repository tree.

This package is installed by customers, and its source and documents are read by them. Nothing in
them may cite the team's internal designs, decisions, work items or test cases, or name an internal
repository or a private customer.

    uv build && uv run python tools/check_public.py dist     # the wheel, the sdist, the documents
    uv run python tools/check_public.py --tree <directory>   # every text file under a directory

Two kinds of check:

* **Patterns** for internal identifiers whose *shape* is the giveaway: work-item, decision and
  architecture-record ids, test-case ids, internal design paths and section references.
* **Names** of private customers, internal repositories and other products, read from
  ``tools/internal-names.txt``. A list of words a public repository must never contain cannot be
  published in it, so that file stays in the private repository and the export leaves it out; the
  public repository runs the pattern check alone, and every release is checked with both before it
  is exported. Hyphenated tokens are checked whole and part by part.
"""

from __future__ import annotations

import re
import sys
import tarfile
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Identifiers that are internal by their shape.
INTERNAL = re.compile(
    # Written so that these lines do not match themselves when this file is scanned.
    r"design[/]|\bDEC-\d+|AB#\d+|\bADR-\d+|TC-S[1]-|§ ?\d"
    # A tracker area path is upper case - MFX, a backslash, a capital. A lower-case file path that
    # starts the same way is not one.
    r"|(?-i:MFX[\\]{1,2}[A-Z])|\bLane \d|-intern[a]l\b",
    re.IGNORECASE,
)

#: Where the names live: one lower-case name a line, ``#`` starts a comment. Absent in the public
#: repository, where the check runs on patterns alone.
NAMES_FILE = REPO / "tools" / "internal-names.txt"


def load_names(path: Path = NAMES_FILE) -> frozenset[str]:
    """The names in ``path``, lower case; none when the file is absent."""
    if not path.is_file():
        return frozenset()
    lines = (line.split("#", 1)[0].strip().lower() for line in path.read_text("utf-8").splitlines())
    return frozenset(line for line in lines if line)


NAMES = load_names()

#: The documents published beside the package.
DOCUMENTS = (
    "README.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "LICENSE",
)
_TEXT = (
    ".py",
    ".pyi",
    ".md",
    ".txt",
    ".toml",
    ".cfg",
    ".json",
    ".yaml",
    ".yml",
    ".typed",
    ".lock",
    ".ini",
)
_TEXT_NAMES = ("METADATA", "PKG-INFO", "LICENSE", "CODEOWNERS", "SOURCE", ".gitignore")
#: Directories a tree scan never enters: git's own files, environments, caches and build output,
#: none of which is committed.
_SKIP = frozenset(
    {".git", ".venv", "dist", "build", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)
_TOKEN = re.compile(r"[a-z0-9][a-z0-9-]*")


def _text(name: str) -> bool:
    return name.endswith(_TEXT) or name.endswith(_TEXT_NAMES)


def _archive(path: Path) -> Iterator[tuple[str, str]]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as wheel:
            for name in wheel.namelist():
                if _text(name):
                    yield f"{path.name}:{name}", wheel.read(name).decode("utf-8", "replace")
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path) as sdist:
            for member in sdist.getmembers():
                handle = sdist.extractfile(member) if member.isfile() else None
                if handle is not None and _text(member.name):
                    yield f"{path.name}:{member.name}", handle.read().decode("utf-8", "replace")


def _tree(root: Path) -> Iterator[tuple[str, str]]:
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if _SKIP.intersection(relative.parts) or not path.is_file() or not _text(path.name):
            continue
        yield relative.as_posix(), path.read_text(encoding="utf-8", errors="replace")


def match(line: str, names: frozenset[str] = NAMES) -> str | None:
    """What in ``line`` is internal, or None. A name is reported by the token that carried it."""
    found = INTERNAL.search(line)
    if found:
        return found.group(0)
    for token in _TOKEN.findall(line.lower()):
        for word in (token, *token.split("-")):
            if word in names:
                return token
    return None


def scan(sources: Iterable[tuple[str, str]], names: frozenset[str] = NAMES) -> list[str]:
    """Every line of ``sources`` that is internal, as ``where:line: match``."""
    out: list[str] = []
    for where, text in sources:
        for number, line in enumerate(text.splitlines(), 1):
            hit = match(line, names)
            if hit:
                out.append(f"{where}:{number}: {hit}")
    return out


def findings(dist: Path, repo: Path = REPO, names: frozenset[str] = NAMES) -> list[str]:
    """Every line that would ship something internal in ``dist`` or the documents."""
    sources: list[tuple[str, str]] = []
    for path in sorted(dist.iterdir()):
        sources.extend(_archive(path))
    for name in DOCUMENTS:
        if (repo / name).is_file():
            sources.append((name, (repo / name).read_text(encoding="utf-8")))
    return scan(sources, names)


def tree_findings(root: Path, names: frozenset[str] = NAMES) -> list[str]:
    """Every line under ``root`` that would publish something internal."""
    return scan(_tree(root), names)


def main(argv: list[str] | None = None) -> int:
    """Run the check; 0 when clean, 1 when something internal was found, 2 when nothing to scan."""
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--tree"]:
        root = Path(args[1]) if len(args) > 1 else REPO
        if not root.is_dir():
            sys.stderr.write(f"no directory at {root}\n")
            return 2
        found, what = tree_findings(root), f"the tree at {root}"
    else:
        dist = Path(args[0]) if args else REPO / "dist"
        if not dist.is_dir() or not any(dist.iterdir()):
            sys.stderr.write(f"nothing built in {dist}: run `uv build` first\n")
            return 2
        found, what = findings(dist), "the wheel, the sdist or the documents"
    for line in found:
        sys.stdout.write(line + "\n")
    if found:
        sys.stderr.write(f"{len(found)} internal reference(s) would be published\n")
        return 1
    sys.stdout.write(f"nothing internal in {what}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
