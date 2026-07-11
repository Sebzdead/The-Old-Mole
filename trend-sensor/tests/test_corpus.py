from src import corpus


def _video(tier, channel, title, published, transcript=None, description=""):
    return {
        "video_id": "vid_" + title,
        "channel_name": channel,
        "title": title,
        "published_at": published,
        "tier": tier,
        "transcript_text": transcript,
        "description": description,
    }


def test_format_corpus_groups_core_and_broad():
    videos = [
        _video("core", "Novara", "A", "2026-07-01", transcript="hello world"),
        _video("broad", "Current Affairs", "B", "2026-07-02", description="desc here"),
    ]
    out = corpus.format_corpus(videos)
    assert "=== CORE VIDEOS (FULL TRANSCRIPTS) ===" in out
    assert "=== BROAD VIDEOS (METADATA ONLY) ===" in out
    assert "hello world" in out
    assert "desc here" in out


def test_format_corpus_truncates_over_word_budget():
    # One giant core video plus one broad video; broad gets dropped first.
    videos = [
        _video("core", "Novara", "big", "2026-07-02", transcript="word " * 80001),
        _video("broad", "CA", "small", "2026-07-01", description="droppable"),
    ]
    out = corpus.format_corpus(videos)
    assert "droppable" not in out
