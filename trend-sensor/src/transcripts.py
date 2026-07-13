import time

from youtube_transcript_api import IpBlocked, RequestBlocked, YouTubeTranscriptApi

from src.cache import is_transcript_cached, save_transcript


class TranscriptsBlocked(Exception):
    """YouTube is rate-limiting/blocking transcript requests from this IP."""


def fetch_transcript(video_id: str) -> str | None:
    """
    Fetches transcript for a YouTube video ID in English.
    Prefers manual and falls back to auto-generated transcripts.
    Truncates result to the first 2000 words.

    Returns None when the video genuinely has no English transcript.
    Raises TranscriptsBlocked when YouTube blocks this IP, so the caller
    can stop hammering and leave the videos uncached for a later retry.
    """
    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
        transcript = transcript_list.find_transcript(["en"])
        data = transcript.fetch()
        full_text = " ".join(snippet.text for snippet in data)

        words = full_text.split()
        return " ".join(words[:2000])
    except (IpBlocked, RequestBlocked) as e:
        raise TranscriptsBlocked(str(e)) from e
    except Exception:
        # No transcript available for this video; fail silently.
        return None


def fetch_transcripts_for_corpus(videos: list[dict]) -> None:
    """
    Fetches transcripts for core-tier videos that do not already have
    a cached transcript, pausing between requests. Stops (without caching)
    as soon as YouTube blocks the IP, so uncached videos are retried on
    the next run.
    """
    for video in videos:
        # Check if video is core tier
        if video.get("tier") == "core":
            video_id = video["video_id"]
            title = video["title"]

            if not is_transcript_cached(video_id):
                try:
                    text = fetch_transcript(video_id)
                except TranscriptsBlocked:
                    print(
                        "Warning: YouTube is blocking transcript requests from "
                        "this IP. Skipping remaining transcript fetches this "
                        "run; uncached videos will be retried next run."
                    )
                    return
                if text is not None:
                    save_transcript(video_id, text)
                    word_count = len(text.split())
                    print(f"Transcript: {title} ({word_count} words)")
                else:
                    # Save a blank transcript so we don't try to fetch again next time
                    save_transcript(video_id, "")
                    print(f"Transcript: No English transcript found for '{title}'")
                time.sleep(3)
            else:
                # Transcript is already cached
                pass
