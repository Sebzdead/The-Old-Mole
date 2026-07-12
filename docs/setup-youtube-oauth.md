# YouTube Analytics OAuth Setup (one-time, ~30 min)

The Analytics API needs OAuth as the channel owner (an API key is not
enough). Result: three values in `.env`.

1. Go to https://console.cloud.google.com/ — use the same project as your
   existing YouTube API key (or create one).
2. **APIs & Services > Library**: enable "YouTube Analytics API" and
   "YouTube Data API v3".
3. **APIs & Services > OAuth consent screen**: configure (External is
   fine), add your Google account as a Test user. The app can stay in
   Testing mode — but note Google expires refresh tokens for Testing-mode
   apps after 7 days. To avoid weekly re-consent, publish the app
   ("In production" — no verification needed for these read-only scopes
   used by only you).
4. **APIs & Services > Credentials > Create credentials > OAuth client
   ID**, type **Desktop app**. Download the JSON as `client_secret.json`
   into the repo root (it is gitignored).
5. Run `python scripts/get_yt_refresh_token.py`, complete consent in the
   browser **as the account that owns the channel**, and copy the three
   printed lines into `.env`.
6. Fill `own_youtube_channel_id` in `trend-sensor/config/accounts.yml`
   (find it at https://www.youtube.com/account_advanced).
7. Verify: `python trend-sensor/collect.py` → `run_meta.json` should show
   `"own_youtube": {"ok": true}`.

Known limitation: impressions and thumbnail CTR are not exposed by the
Analytics API (Studio-only). The report covers views, watch time, average
view duration/percentage, subs gained/lost, likes/comments/shares, and
traffic sources.
