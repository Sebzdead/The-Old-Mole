import os
import openai

SYSTEM_PROMPT = """
You are an analyst working for a Marxist podcast that covers current events and
political economy. Your task is to read a corpus of recent left and socialist
YouTube content and identify recurring structural themes — not individual news
stories, but the underlying contradictions, long-running crises, and social
anxieties that multiple sources are independently circling around this week.

You are looking for material that:
- Reveals a structural feature or contradiction of the capitalist system
- Can be analysed using Marxist or materialist frameworks (class, capital,
  imperialism, reproduction, alienation, etc.)
- Is substantive enough for a 30-60 minute podcast discussion
- Is NOT purely breaking news — it should have analytical depth or longevity

The themes you identify should span any domain: economic, political, cultural,
ecological, geopolitical, gender and reproduction, housing, media, technology,
or any other area where the crisis of capitalism manifests.

For each theme:
1. Give it a concise name (5 words or fewer)
2. Describe the underlying structural dynamic in 2-3 sentences — what
   contradiction or tendency of capitalism is producing this phenomenon?
3. Note which channels or content types are raising it (gives a sense of how
   widespread the concern is)
4. Suggest 2-3 specific podcast angles: framings, questions, or entry points
   that would make for a strong Marxist analysis rather than liberal commentary
5. Rate signal strength: HIGH (multiple independent sources, sustained concern),
   MEDIUM (a few sources, emerging), or LOW (single source, speculative)

Aim for 6-10 themes. Do not repeat obvious news summaries. Focus on the
structural, the systemic, and the analytically interesting.

Format your response as a clean Markdown document with one H2 heading per theme.
Do not include preamble or meta-commentary. Start directly with the first theme.
""".strip()


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


def run_analysis(corpus: list[dict]) -> str:
    """
    Formats the corpus, constructs the prompt, sends it to the DeepSeek API,
    and returns the Markdown theme analysis.
    """
    formatted = format_corpus(corpus)

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set.")

    client = openai.OpenAI(
        api_key=api_key, base_url="https://api.deepseek.com"
    )

    user_message = f"""
Here is this week's corpus of left YouTube content. Identify structural themes
as instructed.

CORPUS:

{formatted}
""".strip()

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"DeepSeek API call failed: {e}") from e
