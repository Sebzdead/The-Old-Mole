# Instagram Graph API Setup (one-time, ~45 min)

Prereqs: the Instagram account is a **Professional** account (Business or
Creator) linked to a Facebook Page you admin.

1. Link the accounts: Instagram app > Settings > Business tools > connect
   your Facebook Page (or via the Page's settings on Facebook).
2. Create a Meta app at https://developers.facebook.com/apps > Create App
   > type "Business".
3. In the app dashboard, add the **Instagram Graph API** product.
4. Get your IG Business user ID: in https://developers.facebook.com/tools/explorer
   select your app, request permissions `instagram_basic`,
   `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`,
   then query `me/accounts` → take the Page ID → query
   `{page-id}?fields=instagram_business_account` → the returned numeric ID
   goes into `trend-sensor/config/accounts.yml` as `instagram_user_id`.
5. **Token (recommended: System User — never expires):**
   - https://business.facebook.com/settings > Users > System users >
     Add (Admin system user).
   - Assign assets: the Facebook Page (full control not required — Insights
     access suffices) and the app.
   - Generate token: select the app; scopes `instagram_basic`,
     `instagram_manage_insights`, `pages_show_list`,
     `pages_read_engagement`; expiry "Never".
   - Put it in `.env` as `IG_ACCESS_TOKEN`.
   - Fallback if System Users are unavailable on your Business account
     tier: generate a 60-day long-lived user token in Graph API Explorer
     and expect to refresh it manually every ~2 months (the report's
     warning banner will tell you when it has expired).
6. Verify: `python trend-sensor/collect.py` → `run_meta.json` should show
   `"instagram": {"ok": true}`.
