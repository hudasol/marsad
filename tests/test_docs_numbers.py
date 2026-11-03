"""Documents must quote the numbers in the result files.

A document marks a figure with an HTML comment placed right after it:

    <!-- claim docs/results/real_corpus/summary.json R1_all_trusted.k 54 -->

The comment names a JSON file, a dotted path (list items by index) and the value quoted in the text. The test fails if
the file is missing, the path does not resolve, or the value differs. This keeps the headline numbers from drifting
away from the committed results.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PATTERN = re.compile(r"<!--\s*claim\s+(\S+)\s+(\S+)\s+(\S+)\s*-->")


def _claims():
    files = (
        [ROOT / "README.md"] + sorted((ROOT / "docs").glob("*.md")) + sorted((ROOT / "docs" / "research").glob("*.md"))
    )
    out = []
    for f in files:
        for m in PATTERN.finditer(f.read_text(encoding="utf-8")):
            out.append((f.relative_to(ROOT).as_posix(), *m.groups()))
    return out


def _resolve(obj, path: str):
    for part in path.split("."):
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


CLAIMS = _claims()


@pytest.mark.skipif(not CLAIMS, reason="no claims marked yet")
@pytest.mark.parametrize("doc,file,path,value", CLAIMS)
def test_claim_matches_result(doc, file, path, value):
    target = ROOT / file
    assert target.exists(), f"{doc}: result file {file} is missing"
    got = _resolve(json.loads(target.read_text(encoding="utf-8")), path)
    if isinstance(got, bool):
        assert str(got).lower() == value.lower(), f"{doc}: {file}:{path} is {got}, text says {value}"
    elif isinstance(got, (int, float)):
        assert (
            abs(float(got) - float(value)) <= 0.5 * 10 ** -(len(value.split(".")[1]) if "." in value else 0) + 1e-9
        ), f"{doc}: {file}:{path} is {got}, text says {value}"
    else:
        assert str(got) == value, f"{doc}: {file}:{path} is {got}, text says {value}"


def test_at_least_the_headline_claims_exist():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert PATTERN.search(readme), "README has no marked claim"
