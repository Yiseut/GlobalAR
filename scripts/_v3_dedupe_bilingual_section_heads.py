"""Strip duplicate consecutive `<span class="en">...</span>` blocks that the
previous inject pass produced (regex bug — see git history). Idempotent.

Matches:
    <span class="en">XYZ</span>SPACE<span class="en">[anything]</span>
…and keeps only the FIRST occurrence (the one immediately glued to the cn span).

Run: PYTHONUTF8=1 python scripts/_v3_dedupe_bilingual_section_heads.py
"""
from __future__ import annotations
import re
from pathlib import Path

V3 = Path(__file__).resolve().parent.parent / "web" / "v3"

# Two consecutive .en spans separated only by whitespace → keep first, drop second.
DUP_PAT = re.compile(
    r'(<span\s+class="en">[^<]*</span>)'
    r'\s*'
    r'<span\s+class="en">[^<]*</span>',
    re.S,
)

def main() -> None:
    total = 0
    for f in sorted(V3.glob("*.html")):
        if f.name.startswith("_"):
            continue
        text = f.read_text(encoding="utf-8")
        n = 0
        while True:
            new_text, k = DUP_PAT.subn(r"\1", text)
            if k == 0:
                break
            n += k
            text = new_text
        if n:
            f.write_text(text, encoding="utf-8")
            print(f"  {f.name:30s}  -{n} duplicate en span(s)")
            total += n
    print()
    print(f"removed {total} duplicate EN spans")

if __name__ == "__main__":
    main()
