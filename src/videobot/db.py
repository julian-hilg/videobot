"""SQLite database: stories, background clips and per-channel usage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from importlib import resources

from .config import home

SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    id       INTEGER PRIMARY KEY,
    title    TEXT NOT NULL,
    body     TEXT NOT NULL,
    author   TEXT DEFAULT '',
    source   TEXT DEFAULT '',     -- e.g. "Wikipedia", "Project Gutenberg"
    url      TEXT DEFAULT '',
    license  TEXT DEFAULT '',     -- e.g. "CC BY-SA 4.0", "Public domain"
    tags     TEXT DEFAULT '',
    added    TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (title, source)
);
CREATE TABLE IF NOT EXISTS clips (
    id       INTEGER PRIMARY KEY,
    path     TEXT NOT NULL UNIQUE,
    duration REAL NOT NULL,
    width    INTEGER, height INTEGER,
    license  TEXT DEFAULT '',
    added    TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS usage (
    channel  TEXT NOT NULL,
    kind     TEXT NOT NULL CHECK (kind IN ('story', 'clip')),
    item_id  INTEGER NOT NULL,
    video    TEXT DEFAULT '',
    used     TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (channel, kind, item_id)
);
"""


@dataclass
class Story:
    id: int
    title: str
    body: str
    author: str = ""
    source: str = ""
    url: str = ""
    license: str = ""
    tags: str = ""

    @property
    def script(self) -> str:
        """What the narrator reads: the title, then the story."""
        title = self.title if self.title.rstrip()[-1:] in ".!?" else self.title + "."
        return f"{title} {self.body}"

    @property
    def credit(self) -> str:
        parts = [f"\"{self.title}\""]
        if self.author:
            parts.append(f"by {self.author}")
        if self.source:
            parts.append(f"({self.source})")
        line = " ".join(parts)
        if self.license:
            line += f", {self.license}"
        if self.url:
            line += f" - {self.url}"
        return line


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(home() / "videobot.db")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM stories LIMIT 1").fetchone():
        seed(con)  # first run: start with the bundled open-licence stories
    return con


def seed(con: sqlite3.Connection) -> int:
    data = json.loads(resources.files("videobot.data").joinpath("seed_stories.json").read_text(encoding="utf-8"))
    return sum(add_story(con, **s) is not None for s in data)


# ------------------------------------------------------------------ stories

def add_story(con, title, body, author="", source="", url="", license="", tags="") -> int | None:
    cur = con.execute(
        "INSERT OR IGNORE INTO stories (title, body, author, source, url, license, tags) VALUES (?,?,?,?,?,?,?)",
        (title.strip(), " ".join(body.split()), author, source, url, license, tags),
    )
    con.commit()
    return cur.lastrowid if cur.rowcount else None


def get_story(con, story_id: int) -> Story:
    row = con.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
    if not row:
        raise SystemExit(f"No story with id {story_id}")
    return _story(row)


def list_stories(con, channel: str | None = None, unused_only: bool = False) -> list[tuple[Story, bool]]:
    rows = con.execute(
        """SELECT s.*, u.item_id IS NOT NULL AS used FROM stories s
           LEFT JOIN usage u ON u.kind = 'story' AND u.item_id = s.id AND u.channel = ?
           ORDER BY s.id""",
        (channel or "",),
    ).fetchall()
    out = [(_story(r), bool(r["used"])) for r in rows]
    return [x for x in out if not x[1]] if unused_only else out


def next_story(con, channel: str) -> Story:
    unused = list_stories(con, channel, unused_only=True)
    if not unused:
        raise SystemExit(f"Channel '{channel}' has used every story. Add more: videobot stories add / import-wikipedia")
    return unused[0][0]


def _story(row) -> Story:
    return Story(**{k: row[k] for k in ("id", "title", "body", "author", "source", "url", "license", "tags")})


# -------------------------------------------------------------------- usage

def mark_used(con, channel: str, kind: str, item_id: int, video: str = "") -> None:
    con.execute("INSERT OR REPLACE INTO usage (channel, kind, item_id, video) VALUES (?,?,?,?)",
                (channel, kind, item_id, video))
    con.commit()
