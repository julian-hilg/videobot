"""Minimal web interface: pick a story, click Make video."""

from __future__ import annotations

import gradio as gr

from . import config, db, stories
from .pipeline import make_video

NEXT = "Next unused story"
VOICES = ["en-US-ChristopherNeural", "en-US-AndrewNeural", "en-US-AvaNeural", "en-US-EmmaNeural",
          "en-GB-RyanNeural", "en-GB-SoniaNeural", "polly:Matthew"]


def _story_choices(channel: str) -> list[str]:
    con = db.connect()
    return [NEXT] + [f"{s.id}: {s.title}{'  (used)' if used else ''}" for s, used in db.list_stories(con, channel)]


def _make(choice: str, channel: str, voice: str, background: str, simulated: bool, progress=gr.Progress()):
    con = db.connect()
    ch = config.channel(channel)
    story = db.next_story(con, ch.id) if choice == NEXT else db.get_story(con, int(choice.split(":")[0]))
    steps = []

    def log(msg: str) -> None:
        steps.append(msg)
        progress(min(len(steps) / 6, 1.0), desc=msg)

    result = make_video(story, ch, background.lower(), voice or None, "simulated" if simulated else None, log=log)
    return str(result.video), result.description, gr.update(choices=_story_choices(channel), value=NEXT)


def _add(title: str, body: str, source: str, wiki: str, channel: str):
    con = db.connect()
    try:
        if wiki.strip():
            sid = db.add_story(con, **stories.wikipedia(wiki.strip()))
        elif title.strip() and body.strip():
            sid = db.add_story(con, title, body, source=source)
        else:
            return "Enter a title and text, or a Wikipedia article name.", gr.update()
    except Exception as e:
        return f"Could not add: {e}", gr.update()
    msg = f"Added story {sid}." if sid else "That story is already in the database."
    return msg, gr.update(choices=_story_choices(channel))


def build() -> gr.Blocks:
    channels = list(config.channels())
    with gr.Blocks(title="videobot") as app:
        gr.Markdown("## videobot")
        with gr.Tab("Make a video"):
            with gr.Row():
                with gr.Column():
                    channel = gr.Dropdown(channels, value=channels[0], label="Channel")
                    story = gr.Dropdown(_story_choices(channels[0]), value=NEXT, label="Story")
                    voice = gr.Dropdown(VOICES, value=config.channel(channels[0]).voice, label="Voice",
                                        allow_custom_value=True)
                    background = gr.Radio(["Auto", "Gradient", "Life"], value="Auto", label="Background",
                                          info="Auto uses your clip library, or a gradient if it's empty")
                    simulated = gr.Checkbox(False, label="Simulated stats on the title card",
                                            info="Made-up views, upvotes, comments and shares")
                    go = gr.Button("Make video", variant="primary")
                with gr.Column():
                    video = gr.Video(label="Video", height=560)
                    description = gr.Textbox(label="Description (with credits)", lines=5)
            channel.change(lambda c: gr.update(choices=_story_choices(c), value=NEXT), channel, story)
            go.click(_make, [story, channel, voice, background, simulated], [video, description, story])
        with gr.Tab("Add a story"):
            wiki = gr.Textbox(label="Wikipedia article", placeholder="e.g. Tulip mania  (imports the introduction)")
            gr.Markdown("…or your own text:")
            title = gr.Textbox(label="Title")
            body = gr.Textbox(label="Story", lines=8)
            source = gr.Textbox(label="Source / credit", placeholder="optional")
            add = gr.Button("Add story")
            status = gr.Markdown()
            add.click(_add, [title, body, source, wiki, channel], [status, story])
    return app


# blue accents, square corners
THEME = gr.themes.Default(primary_hue="blue", radius_size=gr.themes.sizes.radius_none)


def launch(share: bool = False) -> None:
    build().launch(share=share, theme=THEME, allowed_paths=[str(config.home() / "output")])
