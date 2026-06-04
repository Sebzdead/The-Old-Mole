# Left YouTube Trend Scraper & Digest Generator

An automated weekly pipeline that monitors recent video uploads from left/Marxist YouTube channels, retrieves transcripts, caches data in SQLite, analyzes structural themes using the DeepSeek API, and outputs formatted Markdown digests for podcast topic planning.

---

## Features

1. **Smart Crawling**: Automatically checks the uploads of configured YouTube channels using the YouTube Data API v3.
2. **Tiered Analysis**:
   - **Core Tier**: Fetches full English transcripts (via the `youtube-transcript-api` scraper) and performs deep content/structural theme analysis.
   - **Broad Tier**: Inspects titles and descriptions only to minimize API cost and token usage.
3. **SQLite Caching**: Stores videos and transcripts in a local SQLite cache database (`trend-sensor/data/cache.db`) to avoid redundant API requests.
4. **DeepSeek Theme Extraction**: Analyzes the weekly video corpus to identify deep structural contradictions of capitalism, Marxist/materialist themes, and suggests podcast angles instead of basic news summaries.
5. **Weekly Automation**: Runs automatically every Monday at 08:00 UTC via GitHub Actions, committing the resulting Markdown digests back to the repository.

---

## Directory Structure

```text
The Old Mole/
├── .github/
│   └── workflows/
│       └── weekly_digest.yml   # GitHub Actions cron workflow
├── trend-sensor/
│   ├── config/
│   │   └── channels.yml        # Channel configuration (IDs, names, and tiers)
│   ├── digests/
│   │   └── 2026-06-03.md       # Generated weekly Markdown digests
│   ├── src/
│   │   ├── __init__.py
│   │   ├── fetcher.py          # YouTube Data API interaction
│   │   ├── transcripts.py      # Transcript scraper & word count truncator
│   │   ├── cache.py            # SQLite cache management
│   │   ├── analyzer.py         # Formatting corpus & DeepSeek API prompt
│   │   └── digest.py           # Markdown generator & formatting output
│   ├── main.py                 # Core pipeline orchestrator
│   └── requirements.txt        # Python package dependencies
├── .gitignore                  # Repository gitignore (excludes DB, venv, secrets)
├── .gitattributes              # Line endings configuration
└── README.md                   # Project documentation
```

---

## Setup & Local Usage

### Prerequisites
* Python 3.11 or newer
* YouTube Data API Key (from Google Cloud Console)
* DeepSeek API Key (from platform.deepseek.com)

### 1. Installation
Clone the repository, create a virtual environment, and install dependencies:

```bash
# Clone the repository
git clone <your-repo-url>
cd "The Old Mole"

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r trend-sensor/requirements.txt
```

### 2. Configure Channels
Edit `trend-sensor/config/channels.yml` to customize the list of monitored channels. Assign a tier to each channel:
* `core`: Full transcripts are scraped and analyzed (recommended for main channels).
* `broad`: Only titles and descriptions are analyzed (recommended for secondary channels to stay within token quotas).

```yaml
channels:
  - id: UCOzMAa6IhV6uwYQATYG_2kg
    name: "Novara Media"
    tier: core
  - id: UC-3jIAlnQmbbVMV6gR7K8aQ
    name: "The Majority Report"
    tier: core
  - id: UCJm2TgUqtK1_NLBrjNQ1P-w
    name: "Second Thought"
    tier: core
  - id: UC-AQKm7HUNMmxjdS371MSwg
    name: "Channel 5 with Andrew Callaghan"
    tier: core
  - id: UCERIQ0-dth5XhyPnLfVFa2A
    name: "Democracy Now!"
    tier: core
  - id: UC_K47kgAn0E6m6tAMeD00_g
    name: "Hakim"
    tier: core
  - id: UCSmOl7Hau-YX2VKfz1CMAZQ
    name: "Current Affairs"
    tier: broad
```

### 3. Run the Pipeline
Export your API keys as environment variables and run the script:

```bash
export YOUTUBE_API_KEY="your_youtube_api_key_here"
export DEEPSEEK_API_KEY="your_deepseek_api_key_here"

python trend-sensor/main.py
```

The SQLite cache will be created under `trend-sensor/data/cache.db`, and the output digest will be saved in `trend-sensor/digests/YYYY-MM-DD.md`.

---

## GitHub Actions Hosting & Setup

The project is configured to run automatically once a week and commit the generated digests back to the repository.

### 1. Add Repository Secrets
In your GitHub Repository, navigate to **Settings** > **Secrets and variables** > **Actions** and add the following two secrets under **Repository secrets**:
* `YOUTUBE_API_KEY`: Your YouTube API Key.
* `DEEPSEEK_API_KEY`: Your DeepSeek API Key.

### 2. Enable Write Permissions
Because the GitHub Actions bot commits new digests to the `trend-sensor/digests/` folder, you must grant write permissions to the Actions workflow:
1. Navigate to **Settings** > **Actions** > **General**.
2. Scroll to the bottom to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

### 3. Triggering Manually
You can test the GitHub Actions workflow manually without waiting for Monday morning:
1. Go to the **Actions** tab of your GitHub repository.
2. Select **Weekly Trend Digest** under Actions.
3. Click the **Run workflow** dropdown, and click **Run workflow**.
