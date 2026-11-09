"""videobot command line.

    videobot make                          next unused story -> video (default channel)
    videobot make --story 4 --background life --channel science
    videobot stories list | show ID | add | import-wikipedia "Title" ... | import-fables
    videobot library add ~/Movies/clips | list | pexels "rain window" --count 5
    videobot card --story 4 -o card.png    just the title card
    videobot voices                        English voices (use --lang de for German, ...)
    videobot ui                            web interface (needs: pip install "videobot[ui]")
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import backgrounds, config, db, stories, voice


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="videobot", description="Stories -> narrated, captioned vertical videos.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    mk = sub.add_parser("make", help="render a video")
    mk.add_argument("--story", type=int, help="story id (default: next one this channel hasn't used)")
    mk.add_argument("--channel", default="default")
    mk.add_argument("--background", help="auto | gradient | life | path to a clip")
    mk.add_argument("--voice", help="voice name, e.g. en-GB-RyanNeural or polly:Matthew")
    mk.add_argument("--count", type=int, default=1, help="make several videos in a row")
    mk.add_argument("--stats", choices=["none", "simulated"], help="engagement numbers on the title card")

    st = sub.add_parser("stories", help="the story database").add_subparsers(dest="action", required=True)
    ls = st.add_parser("list")
    ls.add_argument("--channel", default="default")
    st.add_parser("show").add_argument("id", type=int)
    add = st.add_parser("add", help="add your own story")
    add.add_argument("--title", required=True)
    add.add_argument("--body", help="text (or use --file)")
    add.add_argument("--file", help="read the story text from a file")
    for f in ("author", "source", "url", "license"):
        add.add_argument(f"--{f}", default="")
    wiki = st.add_parser("import-wikipedia", help="import Wikipedia article introductions (CC BY-SA)")
    wiki.add_argument("titles", nargs="+")
    st.add_parser("import-fables", help="import public-domain Aesop's fables from Project Gutenberg")

    lib = sub.add_parser("library", help="background clips").add_subparsers(dest="action", required=True)
    la = lib.add_parser("add", help="register a folder of videos")
    la.add_argument("folder")
    la.add_argument("--license", default="", help="clip credit, added to video descriptions")
    lib.add_parser("list")
    px = lib.add_parser("pexels", help="download free stock clips (needs PEXELS_API_KEY)")
    px.add_argument("query")
    px.add_argument("--count", type=int, default=5)

    cd = sub.add_parser("card", help="render only the title card")
    cd.add_argument("--story", type=int, required=True)
    cd.add_argument("--channel", default="default")
    cd.add_argument("-o", "--output", default="card.png")

    vo = sub.add_parser("voices", help="list voices")
    vo.add_argument("--lang", default="en")
    ui = sub.add_parser("ui", help="start the web interface")
    ui.add_argument("--share", action="store_true", help="also create a temporary public link")

    a = ap.parse_args(argv)
    con = db.connect()

    if a.cmd == "make":
        from .pipeline import make_video

        ch = config.channel(a.channel)
        for _ in range(a.count):
            story = db.get_story(con, a.story) if a.story else db.next_story(con, ch.id)
            print(f"[{story.id}] {story.title}")
            make_video(story, ch, a.background, a.voice, a.stats)
            if a.story:
                break

    elif a.cmd == "stories":
        if a.action == "list":
            for s, used in db.list_stories(con, a.channel):
                print(f"{s.id:4d}  {'used' if used else '    '}  {len(s.body.split()):4d}w  {s.source:<17.17}  {s.title}")
        elif a.action == "show":
            s = db.get_story(con, a.id)
            print(f"{s.title}\n\n{s.body}\n\n{s.credit}")
        elif a.action == "add":
            body = Path(a.file).read_text(encoding="utf-8") if a.file else a.body
            if not body:
                ap.error("give the story text with --body or --file")
            sid = db.add_story(con, a.title, body, a.author, a.source, a.url, a.license)
            print(f"added story {sid}" if sid else "a story with this title and source already exists")
        elif a.action == "import-wikipedia":
            for t in a.titles:
                try:
                    sid = db.add_story(con, **stories.wikipedia(t))
                    print(f"{'added ' + str(sid) if sid else 'exists'}: {t}")
                except Exception as e:  # keep going with the other titles
                    print(f"skipped {t}: {e}")
        elif a.action == "import-fables":
            n = sum(db.add_story(con, **f) is not None for f in stories.aesop_fables())
            print(f"added {n} fables")

    elif a.cmd == "library":
        if a.action == "add":
            print(f"added {backgrounds.add_folder(con, Path(a.folder), a.license)} clips")
        elif a.action == "pexels":
            print(f"added {backgrounds.pexels(con, a.query, a.count)} clips")
        else:
            for r in con.execute("SELECT * FROM clips ORDER BY id"):
                print(f"{r['id']:4d}  {r['duration']:6.0f}s  {r['width']}x{r['height']}  {r['path']}")

    elif a.cmd == "card":
        from .card import make_card

        s, ch = db.get_story(con, a.story), config.channel(a.channel)
        make_card(s.title, ch.name, s.source or ch.handle, ch.avatar).save(a.output)
        print(a.output)

    elif a.cmd == "voices":
        print("\n".join(voice.voices(a.lang)))

    elif a.cmd == "ui":
        from .ui import launch

        launch(share=a.share)
    return 0


if __name__ == "__main__":
    sys.exit(main())
