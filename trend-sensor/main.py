#!/usr/bin/env python3
"""
Weekly left YouTube trend-sensing pipeline.
Run directly or via GitHub Actions cron.
"""

import os
import sys
import yaml
from datetime import date

# Add the project root to sys.path to handle imports when run from other directories
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import cache, fetcher, transcripts, analyzer, digest


def main():
    print("Starting Weekly Left YouTube Trend-Sensing Pipeline...")

    # 1. Load config/channels.yml
    config_path = os.path.join(PROJECT_ROOT, "config", "channels.yml")
    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found at {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
        except Exception as e:
            print(f"Error parsing YAML config: {e}")
            sys.exit(1)

    channels = config.get("channels", [])
    if not channels:
        print("Warning: No channels configured in config/channels.yml")

    # 2. Call cache.init_db()
    cache.init_db()

    # 3. Call fetcher.fetch_all_channels(channels, days_back=7)
    new_videos = fetcher.fetch_all_channels(channels, days_back=7)

    # 4. Save all new videos to cache
    for video in new_videos:
        cache.save_video(video)

    # 5. Call transcripts.fetch_transcripts_for_corpus for core-tier new videos
    # Only pass new_videos as per orchestrator spec
    transcripts.fetch_transcripts_for_corpus(new_videos)

    # 6. Call cache.get_corpus_since(days=7)
    corpus = cache.get_corpus_since(days=7)

    # 7. If corpus is empty, print "No new videos this week. Exiting." and exit 0
    if not corpus:
        print("No new videos this week. Exiting.")
        sys.exit(0)

    # 8. Call analyzer.run_analysis(corpus)
    print(
        f"Corpus retrieved: {len(corpus)} videos. Running DeepSeek theme analysis..."
    )
    analysis = analyzer.run_analysis(corpus)

    # 9. Call digest.save_digest(analysis, run_date)
    run_date = date.today().isoformat()
    unique_channels = len(set(v["channel_name"] for v in corpus))
    filepath = digest.save_digest(
        analysis, run_date, len(corpus), unique_channels
    )

    # 10. Call digest.print_summary(analysis)
    digest.print_summary(analysis)

    # 11. Print "Digest saved to {filepath}"
    print(f"Digest saved to {filepath}")
    print("Pipeline run completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback

        print(f"Pipeline failed with an error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
