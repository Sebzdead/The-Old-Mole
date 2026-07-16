DESCRIPTION_WORD_LIMIT = 150
COMMENT_WORD_LIMIT = 40
WORD_BUDGET = 80000


def _truncate(text: str | None, limit: int) -> str:
    words = (text or "").split()
    return " ".join(words[:limit])


def format_corpus(corpus: list[dict]) -> str:
    """
    Formats the competitor corpus as a structured plaintext block for the
    LLM: title, truncated description, and (for core-tier videos) top
    audience comments. No transcripts. Limits total size to approximately
    80,000 words by dropping oldest broad-tier entries first, then oldest
    core entries.
    """
    core_entries = []
    broad_entries = []

    for video in corpus:
        channel_name = video.get("channel_name", "")
        title = video.get("title", "")
        published_at = video.get("published_at", "")
        tier = video.get("tier", "broad")
        description = _truncate(video.get("description"), DESCRIPTION_WORD_LIMIT)

        lines = [f"--- {channel_name} | {title} | {published_at}", description]
        if tier == "core":
            comments = video.get("comments") or []
            if comments:
                lines.append("TOP COMMENTS:")
                for comment in comments:
                    text = _truncate(comment.get("text"), COMMENT_WORD_LIMIT)
                    lines.append(f"- ({comment.get('like_count', 0)} likes) {text}")
        content = "\n".join(lines) + "\n"

        entry = {
            "published_at": published_at,
            "content": content,
            "word_count": len(content.split()),
        }
        (core_entries if tier == "core" else broad_entries).append(entry)

    # Sort both lists by published_at descending (newest first)
    core_entries.sort(key=lambda x: x["published_at"], reverse=True)
    broad_entries.sort(key=lambda x: x["published_at"], reverse=True)

    def get_total_words():
        return sum(x["word_count"] for x in core_entries) + sum(
            x["word_count"] for x in broad_entries
        )

    initial_word_count = get_total_words()
    dropped_broad = 0
    dropped_core = 0

    while get_total_words() > WORD_BUDGET:
        if broad_entries:
            # Drop oldest broad-tier entry (end of descending sorted list)
            broad_entries.pop()
            dropped_broad += 1
        elif core_entries:
            core_entries.pop()
            dropped_core += 1
        else:
            break

    if dropped_broad > 0 or dropped_core > 0:
        print(
            f"Warning: Corpus exceeded {WORD_BUDGET} words (initial: {initial_word_count}). "
            f"Truncated by dropping {dropped_broad} broad entries and {dropped_core} core entries."
        )

    output_lines = []

    if core_entries:
        output_lines.append("=== CORE VIDEOS (METADATA + TOP COMMENTS) ===")
        for entry in core_entries:
            output_lines.append(entry["content"])

    if broad_entries:
        output_lines.append("=== BROAD VIDEOS (METADATA ONLY) ===")
        for entry in broad_entries:
            output_lines.append(entry["content"])

    return "\n".join(output_lines)
