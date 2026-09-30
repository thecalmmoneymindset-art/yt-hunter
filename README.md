# YouTube demand miner (official API only)
Runs daily on GitHub Actions, no input from you. Finds recent "I built / making money" videos, reads their comments, and flags people asking for a tool, saying they'd pay, or describing manual pain. Writes reports/latest.md.

## Setup (about 10 minutes, once)
1. console.cloud.google.com -> new project -> enable "YouTube Data API v3" -> Credentials -> Create API key. Free.
2. Create a PUBLIC GitHub repo, upload these files (keep the .github folder).
3. Repo Settings -> Secrets and variables -> Actions -> New secret: YOUTUBE_API_KEY = your key.
4. Actions tab -> "daily-youtube-demand-scan" -> Run workflow (tests it). It then runs every day 06:00 UTC.
5. Send Claude the repo URL. The daily Opportunity Hunter reads reports/latest.md via raw.githubusercontent.com and does competitor/pricing checks on the top signals.

Quota: ~10 searches (1,000 units) + ~200 comment pages (~200 units) per day, well under the free 10,000.
Tune with env vars QUERIES ("a|b|c"), DAYS, PER_QUERY, MIN_COMMENTS.
