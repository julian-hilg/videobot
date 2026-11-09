import pytest
from autcaptions import Transcript, Word

from videobot import db, pipeline, stories
from videobot.card import make_card


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEOBOT_HOME", str(tmp_path))
    return db.connect()


def test_fresh_database_is_seeded_with_open_licence_stories(con):
    rows = db.list_stories(con)
    assert len(rows) >= 20
    assert {s.license for s, _ in rows} == {"CC BY-SA 4.0", "Public domain"}


def test_stories_are_used_once_per_channel(con):
    first = db.next_story(con, "a")
    db.mark_used(con, "a", "story", first.id)
    assert db.next_story(con, "a").id != first.id
    assert db.next_story(con, "b").id == first.id  # other channels are independent


def test_script_and_credit():
    s = db.Story(1, "Emu War", "Soldiers fought emus.", "Wikipedia contributors", "Wikipedia",
                 "https://en.wikipedia.org/wiki/Emu_War", "CC BY-SA 4.0")
    assert s.script == "Emu War. Soldiers fought emus."
    assert "CC BY-SA 4.0" in s.credit and s.credit.endswith("Emu_War")


def test_title_end_handles_merged_tokens():
    t = Transcript([Word("Tulip", 0, .3), Word("mania in 1637.", .3, 1.1), Word("Prices", 1.4, 1.8)])
    assert pipeline._title_end(t, "Tulip mania in 1637") == 1.1


def test_text_helpers():
    assert stories._cut("One two. Three four. Five six.", 4) == "One two. Three four."
    assert stories._fix_drop_cap("A LION was awake").startswith("A Lion was")
    assert stories._title_case("The Wolf And The Lamb") == "The Wolf and the Lamb"


def test_card_is_transparent_png_sized_for_the_frame():
    img = make_card("A title that is long enough to wrap onto a second line", "Channel", "Source")
    assert img.mode == "RGBA" and 860 < img.width < 1080 and img.getpixel((0, 0))[3] == 0


def test_simulated_stats_are_reproducible_and_plausible():
    from videobot.card import compact, simulated_stats

    views, stats = simulated_stats(7)
    assert (views, stats) == simulated_stats(7)
    assert views.endswith(" views") and set(stats) == {"up", "comment", "share"}
    assert compact(999) == "999" and compact(12_345) == "12.3k" and compact(1_200_000) == "1.2M"
