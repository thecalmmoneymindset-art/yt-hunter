#!/usr/bin/env python3
"""App Store review miner. Uses Apple's PUBLIC iTunes Search API and public customer-review RSS feeds (no key, no login).
Rotates keyword groups daily. For each keyword: finds top apps, reads recent 1-3 star reviews, and reports
what paying users complain about (missing features, price/subscription, bugs). Output: reports/appstore.md
Env: MOCK=1 (offline sample), COUNTRIES (default gb,us), GROUPS_PER_DAY (default 4), APPS_PER_TERM (default 5), PAGES (default 2)."""
import os, re, json, time, math, collections, datetime as dt, urllib.parse, urllib.request, urllib.error

COUNTRIES = [c for c in os.environ.get("COUNTRIES", "gb,us").split(",") if c]
GROUPS_PER_DAY = int(os.environ.get("GROUPS_PER_DAY", "4"))
APPS_PER_TERM = int(os.environ.get("APPS_PER_TERM", "5"))
PAGES = int(os.environ.get("PAGES", "2"))
SLEEP = float(os.environ.get("SLEEP", "3"))   # polite: Apple rate-limits search (~20/min)
GROUPS = {
  "money & budgeting": ["budget planner", "debt payoff", "subscription tracker", "bill reminder", "expense tracker"],
  "small business & freelance": ["invoice maker", "quote estimate contractor", "job scheduling small business", "timesheet freelancer", "receipt scanner"],
  "property & home": ["landlord rent tracker", "home maintenance", "moving checklist", "house hunting", "tenant repairs"],
  "family & parenting": ["family organiser", "baby tracker", "chore chart kids", "school calendar parents", "elderly care"],
  "health & fitness": ["medication reminder", "sleep tracker", "habit tracker", "workout planner", "meal planner"],
  "pets": ["pet care reminder", "dog training", "pet health tracker", "dog walker"],
  "study & work": ["flashcards exam revision", "study planner", "job application tracker", "time tracking", "note taking"],
  "hobbies & collecting": ["collection tracker", "board game companion", "fishing log", "garden planner", "recipe organiser"],
  "travel & relocation": ["trip planner", "packing list", "expat", "currency converter", "visa documents"],
  "creators & sellers": ["etsy seller", "ebay reseller inventory", "social media scheduler", "print on demand", "photo editor for business"],
  "cars & transport": ["car maintenance log", "fuel expenses mileage", "driving theory test", "parking reminder"],
  "events & community": ["wedding planner", "event tickets organiser", "club membership", "volunteer scheduling"],
}
COMPLAIN = re.compile(r"(\bwish\b|should (have|add|let)|please add|missing|no way to|can'?t (even )?(add|export|edit|sync|delete|change|find)|cannot|doesn'?t (let|allow|sync|work|save|support)|used to|too expensive|paywall|subscription|ridiculous(ly)? (price|priced)|rip.?off|crash|bug(gy|s)?\b|lost (all )?my|freezes|not worth|scam|useless|(no|need) (offline|export|backup|dark mode|widget|sync))", re.I)
STOP = set("the a an and or but to of in on for with is are was were be it this that i you we they my your our at as by from so if not no do does did can could would should have has had just very really like get got about what how why when there then than too its it's i'm i've don't can't dont cant im ive one out up all more some any app apps".split())

def get_json(url):
    last = None
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "opportunity-hunter/1.0 (personal research)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = e; time.sleep(SLEEP * 2)
    raise last

def search_apps(term, country):
    q = urllib.parse.urlencode({"term": term, "entity": "software", "country": country, "limit": 25})
    res = get_json("https://itunes.apple.com/search?" + q).get("results", [])
    res = [r for r in res if r.get("userRatingCount")]
    res.sort(key=lambda r: -r.get("userRatingCount", 0))
    return res[:APPS_PER_TERM]

def reviews(app_id, country):
    out = []
    for page in range(1, PAGES + 1):
        d = get_json("https://itunes.apple.com/%s/rss/customerreviews/page=%d/id=%s/sortby=mostrecent/json" % (country, page, app_id))
        entries = d.get("feed", {}).get("entry", [])
        if isinstance(entries, dict): entries = [entries]
        for e in entries:
            if "im:rating" not in e: continue          # first entry is often the app itself
            try:
                out.append({"rating": int(e["im:rating"]["label"]), "title": e.get("title", {}).get("label", ""),
                            "text": e.get("content", {}).get("label", ""), "votes": int(e.get("im:voteSum", {}).get("label", 0) or 0)})
            except (KeyError, ValueError): continue
        time.sleep(SLEEP)
        if not entries: break
    return out

def ngrams(texts, n=3, minc=3):
    c = collections.Counter()
    for t in texts:
        w = re.findall(r"[a-z][a-z']+", t.lower())
        for i in range(len(w) - n + 1):
            g = w[i:i+n]
            if g[0] in STOP or g[-1] in STOP: continue
            c[" ".join(g)] += 1
    return [(g, k) for g, k in c.most_common(30) if k >= minc][:8]

def todays_groups():
    names = list(GROUPS)
    if GROUPS_PER_DAY >= len(names): return names
    start = (dt.date.today().toordinal() * GROUPS_PER_DAY) % len(names)
    return [names[(start + k) % len(names)] for k in range(GROUPS_PER_DAY)]

def analyse(group, fetch_search=search_apps, fetch_reviews=reviews):
    apps = {}
    for term in GROUPS[group]:
        for country in COUNTRIES:
            try:
                for a in fetch_search(term, country):
                    apps.setdefault((a["trackId"], country), {**a, "country": country, "term": term})
            except Exception as e:
                ERRORS.append("search %s/%s: %s" % (term, country, e))
            time.sleep(SLEEP)
    rows = []
    for (aid, country), a in sorted(apps.items(), key=lambda kv: -kv[1].get("userRatingCount", 0))[:14]:
        try:
            rv = fetch_reviews(aid, country)
        except Exception as e:
            ERRORS.append("reviews %s/%s: %s" % (a.get("trackName"), country, e)); rv = []
        low = [r for r in rv if r["rating"] <= 3]
        comp = [r for r in low if COMPLAIN.search(r["title"] + " " + r["text"])]
        rows.append({"name": a.get("trackName", "?"), "country": country, "seller": a.get("sellerName", ""),
                     "avg": a.get("averageUserRating"), "count": a.get("userRatingCount", 0), "price": a.get("formattedPrice", ""),
                     "url": a.get("trackViewUrl", ""), "n_rev": len(rv), "n_low": len(low), "complaints": comp})
    return rows

ERRORS = []

def main():
    groups = todays_groups()
    lines = ["# App Store review report — %s" % dt.date.today().isoformat(), "Keyword groups today: %s | countries: %s" % (", ".join(groups), ", ".join(COUNTRIES)), ""]
    all_rows = []
    if os.environ.get("MOCK"):
        rows_by_group = {"money & budgeting": mock_rows()}
        groups = list(rows_by_group)
    else:
        rows_by_group = {g: analyse(g) for g in groups}
    for g in groups:
        rows = rows_by_group[g]
        lines.append("## %s" % g)
        lines.append("Read the table as: many ratings = proven demand; a low average = unhappy customers = room for a better, cheaper or simpler product.")
        lines.append("")
        lines.append("| App | Ratings | Avg | Price | Low-star reviews read | Complaints found |")
        lines.append("| --- | ---: | ---: | --- | ---: | ---: |")
        for r in sorted(rows, key=lambda r: (r["avg"] or 5) - math.log10(r["count"] + 1) * 0.2):
            lines.append("| [%s](%s) (%s) | %d | %s | %s | %d | %d |" % (r["name"][:40], r["url"], r["country"], r["count"], r["avg"], r["price"], r["n_low"], len(r["complaints"])))
        texts = [c["title"] + ". " + c["text"] for r in rows for c in r["complaints"]]
        rep = ngrams(texts)
        lines.append("")
        lines.append("Repeated complaint phrases: " + ("; ".join("%s (%d)" % x for x in rep) if rep else "none yet"))
        lines.append("")
        best = sorted([(c["votes"], r["name"], c) for r in rows for c in r["complaints"]], key=lambda x: -x[0])[:6]
        for v, name, c in best:
            lines.append("- %s, %d star: \"%s\"" % (name, c["rating"], (c["title"] + " - " + c["text"])[:300].replace("\n", " ")))
        lines.append("")
        all_rows += rows
    if ERRORS:
        lines.insert(2, "**WARNING: %d fetch errors (report may be incomplete). First: %s**" % (len(ERRORS), ERRORS[0]))
    else:
        lines.insert(2, "Fetch errors: none")
    os.makedirs("reports", exist_ok=True)
    open("reports/appstore.md", "w").write("\n".join(lines))
    print("\n".join(lines[:30]))

def mock_rows():
    return [{"name": "BudgetPal", "country": "gb", "seller": "x", "avg": 3.4, "count": 12000, "price": "Free", "url": "https://apps.apple.com/x", "n_rev": 100, "n_low": 30,
             "complaints": [{"rating": 2, "title": "Wish it synced", "text": "No way to export my data and the subscription is too expensive", "votes": 9}] * 4}]

if __name__ == "__main__": main()
