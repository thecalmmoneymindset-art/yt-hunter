#!/usr/bin/env python3
"""Stack Exchange unmet-need miner. Uses the OFFICIAL public API (api.stackexchange.com). No key needed (optional STACKEXCHANGE_KEY raises quota).
Finds popular questions that got NO answers in the last year = people asking for things nobody has solved. Output: reports/stackexchange.md
Env: MOCK=1 offline sample, DAYS (default 365), SITES_PER_DAY (default 6)."""
import os, re, json, gzip, time, collections, html, datetime as dt, urllib.parse, urllib.request, urllib.error

DAYS = int(os.environ.get("DAYS", "365"))
SITES_PER_DAY = int(os.environ.get("SITES_PER_DAY", "6"))
KEY = os.environ.get("STACKEXCHANGE_KEY", "")
SITES = ["softwarerecs", "money", "diy", "pets", "gardening", "cooking", "parenting", "travel", "workplace", "expatriates",
         "bicycles", "mechanics", "outdoors", "law", "photo", "music", "fitness", "lifehacks", "webapps", "academia", "islam", "sports", "homebrew", "interpersonal"]
STOP = set("the a an and or but to of in on for with is are was were be it this that i you we they my your our at as by from so if not no do does did can could would should have has had just how what why when there than its it's i'm one out up all more some any get use using".split())
ERRORS = []

def get(url):
    last = None
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "opportunity-hunter/1.0", "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip": raw = gzip.decompress(raw)
                return json.loads(raw)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = e; time.sleep(3)
    raise last

def unanswered(site, fetch=get):
    since = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DAYS)).timestamp())
    p = {"site": site, "order": "desc", "sort": "votes", "fromdate": since, "pagesize": 30}
    if KEY: p["key"] = KEY
    d = fetch("https://api.stackexchange.com/2.3/questions/no-answers?" + urllib.parse.urlencode(p))
    if d.get("backoff"): time.sleep(int(d["backoff"]) + 1)
    return d

def todays_sites():
    if SITES_PER_DAY >= len(SITES): return SITES
    start = (dt.date.today().toordinal() * SITES_PER_DAY) % len(SITES)
    return [SITES[(start + k) % len(SITES)] for k in range(SITES_PER_DAY)]

def ngrams(titles, n=2, minc=3):
    c = collections.Counter()
    for t in titles:
        w = re.findall(r"[a-z][a-z']+", t.lower())
        for i in range(len(w) - n + 1):
            g = w[i:i+n]
            if g[0] in STOP or g[-1] in STOP: continue
            c[" ".join(g)] += 1
    return [(g, k) for g, k in c.most_common(20) if k >= minc][:8]

def main(fetch=get):
    sites = todays_sites()
    lines = ["# Stack Exchange unmet-needs report — %s" % dt.date.today().isoformat(), "Sites today: %s | window: last %d days | questions with zero answers, ranked by votes" % (", ".join(sites), DAYS), ""]
    body = []
    for s in sites:
        try:
            d = MOCK if os.environ.get("MOCK") else unanswered(s, fetch)
        except Exception as e:
            ERRORS.append("%s: %s" % (s, e)); continue
        items = d.get("items", [])
        body.append("## %s (%d unanswered popular questions; API quota left: %s)" % (s, len(items), d.get("quota_remaining", "?")))
        titles = [html.unescape(i.get("title", "")) for i in items]
        rep = ngrams(titles)
        body.append("Repeated phrases: " + ("; ".join("%s (%d)" % x for x in rep) if rep else "none"))
        body.append("")
        for i in sorted(items, key=lambda i: -(i.get("view_count", 0)))[:10]:
            body.append("- %d votes, %d views — [%s](%s) — tags: %s" % (i.get("score", 0), i.get("view_count", 0), html.unescape(i.get("title", "")), i.get("link", ""), ", ".join(i.get("tags", [])[:4])))
        body.append("")
        time.sleep(1)
    lines.append(("**WARNING: %d fetch errors (report may be incomplete). First: %s**" % (len(ERRORS), ERRORS[0])) if ERRORS else "Fetch errors: none")
    lines.append("")
    os.makedirs("reports", exist_ok=True)
    open("reports/stackexchange.md", "w").write("\n".join(lines + body))
    print("\n".join((lines + body)[:24]))

MOCK = {"items": [{"title": "Is there software to track rent &amp; repairs for a small landlord?", "link": "https://softwarerecs.stackexchange.com/q/1", "score": 12, "view_count": 3400, "answer_count": 0, "tags": ["landlord", "tracking"]},
                  {"title": "Software to track rent for landlords", "link": "https://softwarerecs.stackexchange.com/q/2", "score": 5, "view_count": 900, "answer_count": 0, "tags": ["landlord"]}],
        "quota_remaining": 290}

if __name__ == "__main__": main()
