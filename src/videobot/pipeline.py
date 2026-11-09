"""Story -> finished vertical video.

    story ──> voice (audio + transcript) ──> captions (.ass) ──┐
          └─> title card (.png)                               ├──> ffmpeg ──> video.mp4
              background (library clip / generated) ──────────┘

Every video gets its own folder in ~/Videobot/output/ with all intermediate files, so any
step can be inspected or redone:

    2026-11-09_default_tulip-mania/
      video.mp4  description.txt  transcript.json  captions.ass  card.png  voice.mp3
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from autcaptions import CaptionStyle, Transcript, captions_from_transcript, fonts_dir, to_ass

from . import backgrounds, db, voice
from .card import make_card, simulated_stats
from .config import Channel, home

FPS, W, H = 30, 1080, 1920


@dataclass
class Result:
    video: Path
    description: str
    folder: Path


def make_video(story: db.Story, ch: Channel, background: str | None = None, voice_name: str | None = None,
               stats: str | None = None, log=print) -> Result:
    con = db.connect()
    folder = home() / "output" / f"{dt.date.today()}_{ch.id}_{_slug(story.title)}"
    folder.mkdir(parents=True, exist_ok=True)

    log(f"1/4 voice: {voice_name or ch.voice}")
    transcript = voice.speak(story.script, folder / "voice.mp3", voice_name or ch.voice, ch.rate)
    transcript.save(folder / "transcript.json")
    length = voice.duration(folder / "voice.mp3") + 0.6

    log("2/4 title card and captions")
    title_end = _title_end(transcript, story.title)
    info, numbers = story.source or ch.handle, None
    if (stats or ch.stats) == "simulated":
        views, numbers = simulated_stats(story.id)
        info = f"{info} · {views}"
    make_card(story.title, ch.name, info, ch.avatar, numbers).save(folder / "card.png")
    after_title = [w for w in transcript.words if w.start >= title_end]
    caps = captions_from_transcript(transcript, start_at=after_title[0].start if after_title else 0)
    style = CaptionStyle()
    if ch.caption_font:  # e.g. your own licensed font file
        style.font_file = ch.caption_font
        style.font = ch.caption_font_name or Path(ch.caption_font).stem
    (folder / "captions.ass").write_text(to_ass(caps, style), encoding="utf-8")

    log("3/4 background")
    bg = backgrounds.choose(con, ch.id, length, background or ch.background, seed=story.id)
    log(f"    {bg.label}")

    log("4/4 rendering")
    out = folder / "video.mp4"
    _render(folder, bg, length, title_end + 0.25, out, ch, fonts_dir(style))

    description = f"{story.title}\n\n{ch.hashtags}\n\nCredits: {story.credit}\n"
    if bg.credit:
        description += f"Background: {bg.credit}\n"
    (folder / "description.txt").write_text(description, encoding="utf-8")
    db.mark_used(con, ch.id, "story", story.id, str(out))
    backgrounds.remember(con, ch.id, bg, str(out))
    log(f"done: {out}")
    return Result(out, description, folder)


def _title_end(t: Transcript, title: str) -> float:
    """When the narrator finishes reading the title (spoken words may cover several tokens)."""
    need, seen = len(title.split()), 0
    for w in t.words:
        seen += len(w.text.split())
        if seen >= need:
            return w.end
    return 0.0


def _render(folder: Path, bg: backgrounds.Background, length: float, card_until: float, out: Path, ch: Channel,
            fontsdir: Path) -> None:
    music = Path(ch.music).expanduser() if ch.music else None
    inputs = [*bg.args, "-loop", "1", "-i", "card.png", "-i", "voice.mp3"]
    audio = "[2:a]apad[a]"
    if music and music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        audio = f"[3:a]volume={ch.music_volume}[m];[2:a]apad[v0];[v0][m]amix=inputs=2:duration=first:normalize=0[a]"
    graph = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}[bg];"
        f"[1:v]format=rgba[card];"
        f"[bg][card]overlay=(W-w)/2:(H-h)/2:enable='lt(t,{card_until:.2f})'[v1];"
        f"[v1]ass=captions.ass:fontsdir={_esc(fontsdir)}[v];{audio}"
    )
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
           "-t", f"{length:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out.name]
    subprocess.run(cmd, cwd=folder, check=True)


def _esc(p) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'").replace(" ", "\\ ")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "story"
