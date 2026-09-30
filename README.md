# Daily demand scanners (official / public APIs only)
Runs every day on GitHub Actions with no input from you and writes reports to `reports/`:
- `reports/latest.md`          YouTube comments: people asking for tools, saying they'd pay, describing manual pain (44 categories rotate, 7/day + trending in 10 regions). Needs YOUTUBE_API_KEY.
- `reports/appstore.md`        App Store reviews: what paying users of existing apps complain about, by keyword group (4 of 12 groups/day, GB + US). No key.
- `reports/stackexchange.md`   Popular Stack Exchange questions with ZERO answers (unmet needs), 6 of 24 sites/day. No key required (optional STACKEXCHANGE_KEY secret raises the limit).

Each step is independent (continue-on-error), so one failing source never blocks the others. Every report starts with a fetch/API error line: "none" or a WARNING.

## Setup (once)
1. Repo secret YOUTUBE_API_KEY (Settings -> Secrets and variables -> Actions). Optional: STACKEXCHANGE_KEY.
2. Upload hunter.py, appstore.py, stackx.py, README.md. Edit .github/workflows/daily.yml (pencil icon) and paste the new contents.
3. Actions tab -> daily-demand-scan -> Run workflow to test. Then it runs daily 06:00 UTC.

Env knobs: hunter.py (CATS_PER_DAY, DAYS, POP_REGIONS), appstore.py (GROUPS_PER_DAY, COUNTRIES, APPS_PER_TERM, PAGES), stackx.py (SITES_PER_DAY, DAYS).
The daily Opportunity Hunter reads the three reports from raw.githubusercontent.com and runs competitor/pricing checks on the strongest signals.
