"""Stamp content-hash cache versions onto local JS/CSS refs in web/v3/*.html.

Why: pages reference assets as `./v3-foo.js?v=...` with a *static* version
string. After a rebuild regenerates the .js, returning visitors keep the
cached old file because the `?v=` didn't change. This script rewrites each
local asset's `?v=` to an 8-char hash of the file's current content, so the
URL changes iff the content changes — correct cache invalidation, idempotent.

Run as the LAST step of the v3 build chain (after all _v3_build_*.py).
CDN refs (http/https) are left untouched.

Usage:
    python scripts/_v3_stamp_asset_versions.py          # apply
    python scripts/_v3_stamp_asset_versions.py --check   # dry-run, report only
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V3 = ROOT / "web" / "v3"

# match src="..." / href="..." for local (./ or ../) .js/.css, optional ?v=...
REF_RE = re.compile(
    r'(?P<attr>\b(?:src|href)=")(?P<path>\.{1,2}/[^"?]+\.(?:js|css))(?:\?v=[^"]*)?(?P<close>")'
)

_hash_cache: dict[Path, str] = {}


def file_hash(path: Path) -> str | None:
    if path in _hash_cache:
        return _hash_cache[path]
    try:
        digest = hashlib.sha1(path.read_bytes()).hexdigest()[:8]
    except OSError:
        return None
    _hash_cache[path] = digest
    return digest


def process(html_path: Path, apply: bool) -> list[tuple[str, str]]:
    text = html_path.read_text(encoding="utf-8")
    changes: list[tuple[str, str]] = []

    def repl(m: re.Match) -> str:
        rel = m.group("path")
        target = (html_path.parent / rel).resolve()
        digest = file_hash(target)
        if digest is None:
            return m.group(0)  # missing target — leave ref untouched
        new = f'{m.group("attr")}{rel}?v={digest}{m.group("close")}'
        if new != m.group(0):
            changes.append((rel, digest))
        return new

    new_text = REF_RE.sub(repl, text)
    if apply and new_text != text:
        html_path.write_text(new_text, encoding="utf-8")
    return changes


def main() -> None:
    apply = "--check" not in sys.argv
    total = 0
    for html_path in sorted(V3.glob("*.html")):
        changes = process(html_path, apply)
        if changes:
            total += len(changes)
            print(f"{html_path.name}: {len(changes)} ref(s)")
    verb = "stamped" if apply else "would stamp"
    print(f"{verb} {total} asset ref(s) across web/v3/*.html")


if __name__ == "__main__":
    main()
