def fetch_comments(youtube, video_id: str, max_comments: int = 100) -> list[dict]:
    """
    Fetches top-level comments for a video, ordered by relevance,
    capped at max_comments. Returns [] on any API error (e.g. comments
    disabled) — a missing comment section must not fail the run.
    """
    comments = []
    page_token = None
    try:
        while len(comments) < max_comments:
            response = (
                youtube.commentThreads()
                .list(
                    part="snippet",
                    videoId=video_id,
                    order="relevance",
                    textFormat="plainText",
                    maxResults=min(100, max_comments - len(comments)),
                    pageToken=page_token,
                )
                .execute()
            )
            for item in response.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                comments.append(
                    {
                        "text": top.get("textDisplay", ""),
                        "like_count": top.get("likeCount", 0),
                        "author": top.get("authorDisplayName", ""),
                        "published_at": top.get("publishedAt", ""),
                    }
                )
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        print(f"Warning: comment fetch failed for {video_id}: {e}")
    return comments[:max_comments]
