"""Fail if a relative link in a Markdown file points at a file that does not exist.

    python scripts/check_links.py [root]

Checks inline links and images, ignores URLs, mailto links and in-page anchors.
"""

import re
import sys
from pathlib import Path

LINK = re.compile(r"(?<!\\)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SKIP = ("http://", "https://", "mailto:", "#")


def main(root="."):
    root = Path(root)
    bad = []
    for md in sorted(root.rglob("*.md")):
        if any(p in md.parts for p in (".git", ".venv", "node_modules", "results")):
            continue
        in_code = False
        for no, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
            if in_code:
                continue
            for target in LINK.findall(line):
                if target.startswith(SKIP):
                    continue
                path = target.split("#", 1)[0]
                if path and not (md.parent / path).exists():
                    bad.append(f"{md}:{no}: {target}")
    for b in bad:
        print(b)
    print(f"{len(bad)} broken relative link(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
