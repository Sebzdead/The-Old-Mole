import time
from youtube_transcript_api import YouTubeTranscriptApi
from src.cache import is_transcript_cached, save_transcript


def fetch_transcript(video_id: str) -> str | None:
    """
    Fetches transcript for a YouTube video ID in English.
    Prefers manual and falls back to auto-generated transcripts.
    Truncates result to the first 2000 words.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(["en"])
        data = transcript.fetch()
        text_segments = [entry.get("text", "") for entry in data]
        full_text = " ".join(text_segments)

        words = full_text.split()
        return " ".join(words[:2000])
    except Exception as e:
        # Fail silently and return None as per specification
        return None


def fetch_transcripts_for_corpus(videos: list[dict]) -> None:
    """
    Fetches transcripts for core-tier videos that do not already have
    a cached transcript, pausing for 1 second between requests.
    """
    for video in videos:
        # Check if video is core tier
        if video.get("tier") == "core":
            video_id = video["video_id"]
            title = video["title"]

            if not is_transcript_cached(video_id):
                text = fetch_transcript(video_id)
                if text is not None:
                    save_transcript(video_id, text)
                    word_count = len(text.split())
                    print(f"Transcript: {title} ({word_count} words)")
                else:
                    # Save a blank or None transcript so we don't try to fetch again next time
                    save_transcript(video_id, "")
                    print(f"Transcript: No English transcript found for '{title}'")
                time.sleep(1)
            else:
                # Transcript is already cached
                pass
