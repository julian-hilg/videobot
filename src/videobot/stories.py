"""Import open-licence stories into the database.

* Wikipedia article summaries - CC BY-SA 4.0 (credit + licence go into the video description)
* Aesop's Fables (Project Gutenberg #21, Townsend translation) - public domain
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.error
import urllib.request

USER_AGENT = "videobot/0.1 (open-source story video tool)"
AESOP_URL = "https://www.gutenberg.org/cache/epub/21/pg21.txt"


def _get(url: str, tries: int = 4) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            time.sleep(float(e.headers.get("Retry-After") or 2 ** (attempt + 1)))  # rate limited
    raise RuntimeError("unreachable")


def wikipedia(title: str, lang: str = "en", max_words: int = 160) -> dict:
    """The introduction of a Wikipedia article (cut at a sentence end), ready for `db.add_story`."""
    query = urllib.parse.urlencode({
        "action": "query", "format": "json", "prop": "extracts|info", "exintro": 1,
        "explaintext": 1, "inprop": "url", "redirects": 1, "titles": title,
    })
    page = next(iter(json.loads(_get(f"https://{lang}.wikipedia.org/w/api.php?{query}"))["query"]["pages"].values()))
    if "missing" in page or not page.get("extract"):
        raise ValueError(f"'{title}' was not found on Wikipedia")
    body = re.sub(r"\s*\([^()]*\)", "", page["extract"])  # drop (pronunciations, dates in brackets)
    body = _cut(" ".join(body.split()), max_words)
    return {
        "title": page["title"],
        "body": body,
        "author": "Wikipedia contributors",
        "source": "Wikipedia",
        "url": page["fullurl"],
        "license": "CC BY-SA 4.0",
        "tags": "wikipedia",
    }


def aesop_fables(min_words: int = 50, max_words: int = 220) -> list[dict]:
    """Aesop's fables that fit a short video (by length)."""
    text = _get(AESOP_URL).replace("\r", "")
    text = text.split("*** START OF", 1)[1].split("*** END OF", 1)[0]
    first = "\n\n\nThe Lion And The Mouse\n\n\n"   # the first fable (after contents and preface)
    text = text[text.rfind(first):]
    # blocks are separated by blank lines; a title is one short line without end punctuation
    blocks = [b.strip() for b in re.split(r"\n{3,}", text) if b.strip()]
    pairs, title, body = [], None, []
    for b in blocks:
        if "\n" not in b and len(b) < 70 and b[-1] not in ".!?:”\"’":
            if title and body:
                pairs.append((title, " ".join(body)))
            title, body = b, []
        else:
            body.append(b)
    if title and body:
        pairs.append((title, " ".join(body)))
    fables = []
    for title, body in pairs:
        body = _fix_drop_cap(" ".join(body.split()))
        if min_words <= len(body.split()) <= max_words:
            fables.append({
                "title": _title_case(title),
                "body": body,
                "author": "Aesop (tr. George Fyler Townsend)",
                "source": "Project Gutenberg",
                "url": "https://www.gutenberg.org/ebooks/21",
                "license": "Public domain",
                "tags": "fable",
            })
    return fables


def _cut(text: str, max_words: int) -> str:
    """Keep whole sentences up to about `max_words` words."""
    out, n = [], 0
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        n += len(sentence.split())
        if out and n > max_words:
            break
        out.append(sentence)
    return " ".join(out)


def _title_case(t: str) -> str:
    small = {"and", "the", "of", "in", "a", "an", "his", "her", "to", "with"}
    words = t.split()
    return " ".join(w if i == 0 or w.lower() not in small else w.lower() for i, w in enumerate(words))


def _fix_drop_cap(body: str) -> str:
    """'A LION was awakened' -> 'A Lion was awakened' (the book sets first words in capitals)."""
    m = re.match(r"((?:[A-Z’']{1,}[,]? ){1,3})", body)
    if not m:
        return body
    head = " ".join(w if len(w.strip(",")) == 1 else w.capitalize() for w in m.group(1).split())
    return head + " " + body[m.end():]
