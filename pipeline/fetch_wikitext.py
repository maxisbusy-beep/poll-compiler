"""Save the raw wikitext of a few pages as test fixtures (run on GitHub, which can reach Wikipedia).

python -m pipeline.fetch_wikitext "Title one" "Title two" ...
Writes tests/fixtures/wikitext/<slug>.wiki
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from pipeline.fetch_wikipedia import api

ROOT = Path(__file__).resolve().parent.parent


def main(titles: list[str]) -> None:
    out = ROOT / "tests" / "fixtures" / "wikitext"
    out.mkdir(parents=True, exist_ok=True)
    for t in titles:
        d = api({"action": "query", "prop": "revisions", "rvprop": "content|ids", "rvslots": "main",
                 "titles": t, "redirects": 1})
        page = d["query"]["pages"][0]
        text = page["revisions"][0]["slots"]["main"]["content"]
        fn = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_") + ".wiki"
        (out / fn).write_text(text)
        print(t, len(text))


if __name__ == "__main__":
    main(sys.argv[1:])
