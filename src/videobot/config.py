"""Where videobot keeps its files, and per-channel settings.

Everything lives in one folder (default `~/Videobot`, override with `VIDEOBOT_HOME`):

    ~/Videobot/
      videobot.db        stories, background clips, what each channel already used
      channels.toml      channel settings (created on first run)
      library/           background clips (your own or downloaded)
      output/            finished videos + description files
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

DEFAULT_CHANNELS = """\
# One [channels.<id>] block per channel. Videos, stories and clips are tracked per channel,
# so two channels never get the same story or background clip.

[channels.default]
name = "Story Time"                # shown on the title card
handle = "@storytime"              # small grey line under the name
avatar = ""                        # optional image file for the round profile picture
voice = "en-US-ChristopherNeural"  # see `videobot voices`
rate = "+15%"                      # speaking speed
background = "auto"                # auto | gradient | life | path/to/clip.mp4
music = ""                         # optional music file, mixed in quietly
music_volume = 0.04
hashtags = "#story #shorts"
stats = "none"                     # none | simulated (made-up views/upvotes/comments/shares on the card)
caption_font = ""                  # optional font file for captions (default: bundled Montserrat ExtraBold)
caption_font_name = ""             # its font name, e.g. "The Bold Font"
"""


@dataclass
class Channel:
    id: str = "default"
    name: str = "Story Time"
    handle: str = "@storytime"
    avatar: str = ""
    voice: str = "en-US-ChristopherNeural"
    rate: str = "+15%"
    background: str = "auto"
    music: str = ""
    music_volume: float = 0.04
    hashtags: str = "#story #shorts"
    stats: str = "none"
    caption_font: str = ""
    caption_font_name: str = ""


def home() -> Path:
    path = Path(os.environ.get("VIDEOBOT_HOME", Path.home() / "Videobot")).expanduser()
    for sub in ("library", "output"):
        (path / sub).mkdir(parents=True, exist_ok=True)
    return path


def channels() -> dict[str, Channel]:
    path = home() / "channels.toml"
    if not path.exists():
        path.write_text(DEFAULT_CHANNELS, encoding="utf-8")
    data = tomllib.loads(path.read_text(encoding="utf-8")).get("channels", {})
    known = {f.name for f in fields(Channel)}
    return {cid: Channel(id=cid, **{k: v for k, v in cfg.items() if k in known}) for cid, cfg in data.items()}


def channel(cid: str = "default") -> Channel:
    all_ = channels()
    if cid not in all_:
        raise SystemExit(f"Unknown channel '{cid}'. Channels: {', '.join(all_)} (edit {home() / 'channels.toml'})")
    return all_[cid]
