from src import corpus


def _video(tier, channel, title, published, description="", comments=None):
    return {
        "video_id": "vid_" + title,
        "channel_name": channel,
        "title": title,
        "published_at": published,
        "tier": tier,
        "description": description,
        "comments": comments,
    }


def test_format_corpus_renders_metadata_and_core_comments():
    videos = [
        _video(
            "core",
            "Novara",
            "A",
            "2026-07-01",
            description="core desc here",
            comments=[{"text": "great video", "like_count": 12}],
        ),
        _video(
            "broad", "Current Affairs", "B", "2026-07-02", description="broad desc here"
        ),
    ]
    out = corpus.format_corpus(videos)
    assert "=== CORE VIDEOS (METADATA + TOP COMMENTS) ===" in out
    assert "=== BROAD VIDEOS (METADATA ONLY) ===" in out
    assert "core desc here" in out
    assert "broad desc here" in out
    assert "TOP COMMENTS:" in out
    assert "- (12 likes) great video" in out
    assert "TRANSCRIPTS" not in out


def test_format_corpus_handles_core_without_comments():
    out = corpus.format_corpus(
        [_video("core", "Novara", "A", "2026-07-01", description="just desc")]
    )
    assert "just desc" in out
    assert "TOP COMMENTS:" not in out


def test_format_corpus_truncates_long_comments_and_descriptions():
    videos = [
        _video(
            "core",
            "Novara",
            "A",
            "2026-07-01",
            description="d " * 200 + "DESCTAIL",
            comments=[{"text": "c " * 60 + "COMMENTTAIL", "like_count": 1}],
        ),
    ]
    out = corpus.format_corpus(videos)
    assert "d d" in out  # truncated description IS rendered for core videos
    assert "DESCTAIL" not in out
    assert "(1 likes) c c" in out  # truncated comment IS rendered
    assert "COMMENTTAIL" not in out


def test_format_corpus_drops_broad_first_over_word_budget():
    many_comments = [{"text": "word " * 40, "like_count": 1} for _ in range(2100)]
    videos = [
        _video("core", "Novara", "big", "2026-07-02", comments=many_comments),
        _video("broad", "CA", "small", "2026-07-01", description="droppable"),
    ]
    out = corpus.format_corpus(videos)
    assert "droppable" not in out
