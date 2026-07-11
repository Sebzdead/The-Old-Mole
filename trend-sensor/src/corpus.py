def format_corpus(corpus: list[dict]) -> str:
    """
    Formats the corpus as a structured plaintext block for the LLM.
    Groups by tier and limits total word count to approximately 80,000 words
    by dropping broad-tier entries first (oldest first), then oldest core entries.
    """
    core_entries = []
    broad_entries = []

    for video in corpus:
        video_id = video.get("video_id", "")
        channel_name = video.get("channel_name", "")
        title = video.get("title", "")
        published_at = video.get("published_at", "")
        tier = video.get("tier", "broad")

        if tier == "core":
            transcript_text = video.get("transcript_text") or ""
            content = f"--- {channel_name} | {title} | {published_at}\n{transcript_text}\n"
            word_count = len(content.split())
            core_entries.append(
                {
                    "video_id": video_id,
                    "published_at": published_at,
                    "content": content,
                    "word_count": word_count,
                }
            )
        else:
            description = video.get("description") or ""
            desc_words = description.split()
            truncated_desc = " ".join(desc_words[:150])
            content = f"--- {channel_name} | {title} | {published_at}\n{truncated_desc}\n"
            word_count = len(content.split())
            broad_entries.append(
                {
                    "video_id": video_id,
                    "published_at": published_at,
                    "content": content,
                    "word_count": word_count,
                }
            )

    # Sort both lists by published_at descending (newest first)
    core_entries.sort(key=lambda x: x["published_at"], reverse=True)
    broad_entries.sort(key=lambda x: x["published_at"], reverse=True)

    # Calculate total word count helper
    def get_total_words(cores, broads):
        return sum(x["word_count"] for x in cores) + sum(
            x["word_count"] for x in broads
        )

    initial_word_count = get_total_words(core_entries, broad_entries)
    dropped_broad = 0
    dropped_core = 0

    # Truncate if we exceed 80,000 words
    while get_total_words(core_entries, broad_entries) > 80000:
        if broad_entries:
            # Drop oldest broad-tier entry (from the end of descending sorted list)
            broad_entries.pop()
            dropped_broad += 1
        elif core_entries:
            # Drop oldest core-tier entry (from the end of descending sorted list)
            core_entries.pop()
            dropped_core += 1
        else:
            break

    if dropped_broad > 0 or dropped_core > 0:
        print(
            f"Warning: Corpus exceeded 80,000 words (initial: {initial_word_count}). "
            f"Truncated by dropping {dropped_broad} broad entries and {dropped_core} core entries."
        )

    # Reconstruct grouped corpus
    output_lines = []

    if core_entries:
        output_lines.append("=== CORE VIDEOS (FULL TRANSCRIPTS) ===")
        for entry in core_entries:
            output_lines.append(entry["content"])

    if broad_entries:
        output_lines.append("=== BROAD VIDEOS (METADATA ONLY) ===")
        for entry in broad_entries:
            output_lines.append(entry["content"])

    return "\n".join(output_lines)
