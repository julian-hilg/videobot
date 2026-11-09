"""Rebuild src/videobot/data/seed_stories.json (the stories a fresh install starts with).

    uv run python scripts/build_seed.py
"""

import json
import time
from pathlib import Path

from videobot import stories

WIKIPEDIA = [
    "Tulip mania", "Great Molasses Flood", "Dancing plague of 1518", "Emu War",
    "Mississippi Company", "Phineas Gage", "Tunguska event", "Great Stink",
    "Charles Ponzi", "Radium Girls", "South Sea Company", "Kowloon Walled City",
]
N_FABLES = 15

seed = []
for title in WIKIPEDIA:
    s = stories.wikipedia(title)
    print(f"wikipedia  {len(s['body'].split()):4d} words  {s['title']}")
    seed.append(s)
    time.sleep(1.5)  # be polite to the Wikipedia API
for f in stories.aesop_fables()[:N_FABLES]:
    print(f"fable      {len(f['body'].split()):4d} words  {f['title']}")
    seed.append(f)

out = Path(__file__).parents[1] / "src/videobot/data/seed_stories.json"
out.write_text(json.dumps(seed, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(seed)} stories -> {out}")
