#!/usr/bin/env python3
"""YouTube demand miner. Uses the OFFICIAL YouTube Data API v3 only.
Finds recent 'I built X / making money' style videos, reads their public comments,
and surfaces comments where viewers ask for a tool, say they'd pay, or describe manual pain.
Env: YOUTUBE_API_KEY. Optional: MOCK=1 to run offline on sample data."""
import os, re, json, math, sys, datetime as dt, collections, urllib.parse, urllib.request, urllib.error
import time, random
START = time.time()

KEY = os.environ.get("YOUTUBE_API_KEY", "")
DAYS = int(os.environ.get("DAYS", "120"))
PER_QUERY = int(os.environ.get("PER_QUERY", "25"))
MIN_COMMENTS = int(os.environ.get("MIN_COMMENTS", "15"))
PAGES = int(os.environ.get("PAGES", "2"))
# category -> search queries. Categories rotate daily (CATS_PER_DAY) so the whole list is covered every few days.
CATEGORIES = {
  "AI tools & agents": ["AI tool I wish existed", "AI agent problems small business", "best AI tools people actually pay for"],
  "AI for small business": ["AI for small business owners", "AI receptionist for local business", "AI automation saving hours business"],
  "vibe coding & building apps": ["I built an app with AI", "vibe coding problems", "no code app builder problems"],
  "make money online methods": ["make money online with AI 2026", "side hustle that actually works", "passive income apps review"],
  "side hustles & selling online": ["side hustle UK", "digital products selling online", "faceless business ideas"],
  "AI automation services": ["AI automation agency clients", "selling AI services to local businesses", "n8n automation business"],
  "local trades & services": ["software for plumbers", "app for cleaning business", "quoting software for contractors"],
  "property & housing": ["software for landlords", "letting agent software", "renting a flat problems app"],
  "renters & home admin": ["tenant tools app", "household bills tracking app", "moving house checklist tool"],
  "home DIY & renovation": ["DIY renovation planning tool", "home repair cost estimator", "builder quote comparison"],
  "gardening & allotments": ["garden planning app", "allotment planner tool", "plant care reminder app"],
  "food & hospitality": ["software for restaurant owners", "home bakery business app", "cafe owner software problems"],
  "cooking & meal planning": ["meal planning app problems", "recipe organiser app", "grocery budget tool"],
  "health & fitness": ["fitness app I wish existed", "medication reminder app", "gym owner software"],
  "senior & elderly care": ["elderly parent care app", "care home admin software", "dementia care tools"],
  "parenting & family": ["app for parents organising family", "baby tracking app review", "school admin app for parents"],
  "weddings & events": ["wedding planning tool", "event planner software", "party planning app"],
  "pets": ["pet owner app idea", "dog walking business software", "pet care gadgets review"],
  "hobbies & collecting": ["hobby collectors tracking app", "trading card collection app", "model making tools"],
  "gaming & tabletop": ["tool for tabletop game masters", "gaming community tool built", "esports team admin tool"],
  "sports & clubs": ["sports club management software", "amateur football club admin app", "running club tools"],
  "outdoors & camping": ["camping planning app", "hiking route planning tool", "fishing app idea"],
  "cycling & running": ["cycling training tool", "running plan app problems", "bike maintenance tracker"],
  "cars & motoring": ["car maintenance tracker app", "used car buying checker tool", "driving instructor software"],
  "education & study": ["study app students actually use", "exam revision tool", "teacher admin tools"],
  "students & campus": ["student budgeting app", "university admin problems tool", "student accommodation tool"],
  "languages & translation": ["language learning app problems", "translation tool for small business", "learn english app"],
  "jobs & careers": ["job application tracker tool", "cv builder problems", "freelancer finding clients tool"],
  "personal finance & admin": ["budgeting app problems", "subscription tracker app", "debt payoff app"],
  "investing & crypto": ["portfolio tracker problems", "crypto tax tool", "dividend tracker app"],
  "freelancers & admin": ["invoicing software comparison", "freelancer admin tools", "time tracking app freelancers"],
  "creators & sellers": ["etsy seller tools", "amazon seller software", "print on demand automation tools"],
  "resellers & second-hand": ["vinted ebay reseller tools", "reselling inventory tracker", "car boot sale business tools"],
  "photography & video": ["photographer business software", "wedding photographer workflow tool", "video editor workflow tool"],
  "music & podcasting": ["musician gig admin tool", "podcast production tool", "music teacher software"],
  "writing & publishing": ["self publishing tools authors", "writer productivity app", "blogger monetisation tools"],
  "beauty & personal care": ["salon booking software", "nail tech business app", "barber shop software"],
  "fashion & clothing": ["small clothing brand tools", "sizing problems online clothes", "wardrobe organiser app"],
  "smart home & gadgets": ["smart home gadget I wish existed", "useful gadgets review problems", "cable and charger problems"],
  "travel & relocation": ["moving abroad checklist app", "travel planning app problems", "expat admin tools"],
  "faith & community": ["mosque or church admin software", "community group management app", "charity volunteer tool"],
  "small business software": ["scheduling software small business", "customer service tool small business", "inventory software small business"],
  "construction & trades admin": ["construction site paperwork app", "electrician certificate software", "builder invoicing tool"],
  "legal & bills admin": ["dispute a parking fine tool", "consumer rights complaint tool", "insurance claim help app"],
}
_q = os.environ.get("QUERIES", "")
if _q.strip():  # custom override: "cat::query|cat::query" or plain "query|query"
    CATEGORIES = collections.defaultdict(list)
    for item in [x.strip() for x in _q.split("|") if x.strip()]:
        c, _, q = item.partition("::")
        (CATEGORIES[c.strip()] if q else CATEGORIES["custom"]).append((q or c).strip())
PER_DAY = int(os.environ.get("CATS_PER_DAY", "7"))
_names = list(CATEGORIES)
if not _q.strip() and PER_DAY < len(_names):
    _start = (dt.date.today().toordinal() * PER_DAY) % len(_names)
    _today = [_names[(_start + k) % len(_names)] for k in range(PER_DAY)]
    CATEGORIES = {c: CATEGORIES[c] for c in _today}
QUERY_CAT = {q: c for c, qs in CATEGORIES.items() for q in qs}
QUERIES = list(QUERY_CAT)
ERRORS = []
QUOTA_HIT = False
SIGNALS = {
  "ask_for_tool": r"\b(what('?s| is) (the|this|that) (app|tool|software|website|site|extension)|is there (a|an|any) (app|tool|software|website|way|service)|does (this|anyone|something like) (exist|know)|what (app|tool|software) (is|was|do)|name of (the|this) (app|tool))\b",
  "would_pay": r"\b(i('d| would| will) (gladly |happily )?(pay|buy|subscribe)|take my money|shut up and take|where do i (sign|pay|buy)|what('s| is) the (price|pricing|cost) (of|for)|does it have a (free|paid))\b",
  "wish_build": r"\b(someone (should|needs to|please) (build|make|create)|why (isn'?t|doesn'?t) (there|anyone)|i wish (there was|there were|it (could|would|had)|this (could|would|had)|i (had|could) (a|an|something))|wish (there was|someone would) )",
  "manual_pain": r"(\btakes? (me )?(hours|forever|ages|so long)\b|\b(i|we)\b[^.!?]{0,60}\b(manually|by hand)\b|\b(i|we)\b[^.!?]{0,40}\b(in|on) (a |an )?(spreadsheet|excel)\b|\bi hate (doing|having to)\b|\bstruggling to (find|keep|track|manage|get)\b|\bnightmare (to|when)\b)",
  "result_report": r"(\bi (tried|made|earned|lost|spent|got)\b[^.!?]{0,60}(\u00a3|\$|\u20ac|\b\d+ ?(k|dollars|pounds|usd)\b)|\b(didn'?t|doesn'?t|did not|does not) work\b|\bscam\b|\bwaste of (time|money)\b|\bnot worth (it|the)\b|\bthis (works|worked) for me\b)",
  "link_ask": r"\b(where can i (get|find|download|buy)|can (you|i) (share|get) (the )?(link|app|tool))\b",
}
WEIGHT = {"result_report": 1.5, "would_pay": 3.0, "ask_for_tool": 2.5, "wish_build": 2.0, "manual_pain": 2.5, "link_ask": 0.3}
# comments that are requests to the CREATOR (make a video etc.) or non-English/spam are not product demand
NOISE = re.compile(r"(please make (a |another |more |the )?(video|tutorial|episode|post|content|part)|make (a |more )?video|video on |tutorial on|full (step|tutorial)|bhai|kaha|kha\b|ka link|link do|pls make|subscribe to my|check out my|whatsapp|telegram|@[a-z0-9_]{4,})", re.I)
def mostly_english(t):
    a = sum(1 for ch in t if ord(ch) < 128)
    return len(t) > 0 and a / len(t) > 0.95
STOP = set("the a an and or but to of in on for with is are was were be it this that i you we they my your our at as by from so if not no do does did can could would should have has had just very really like get got about what how why when there then than too its it's i'm i've don't can't dont cant im ive one out up all more some any".split())

def api(path, **p):
    p["key"] = KEY
    url = "https://www.googleapis.com/youtube/v3/%s?%s" % (path, urllib.parse.urlencode(p))
    global QUOTA_HIT
    BENIGN = ("commentsdisabled", "videonotfound", "processingfailure", "forbidden")  # normal for some videos, not a scan failure
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:300]
            low = body.lower()
            if "quota" in low: QUOTA_HIT = True
            elif e.code >= 500 and attempt == 1: continue          # one retry on server errors
            if not any(b in low for b in BENIGN) or "quota" in low:
                ERRORS.append("%s %s" % (e.code, body.replace("\n", " ")))
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == 1: continue                              # one retry on network blips
            ERRORS.append("network: %s" % e)
            raise

POP_CATS = {"1": "Film", "2": "Autos", "10": "Music", "15": "Pets", "17": "Sports", "19": "Travel", "20": "Gaming",
            "22": "People & Blogs", "23": "Comedy", "24": "Entertainment", "25": "News", "26": "Howto & Style",
            "27": "Education", "28": "Science & Tech"}
POP_REGIONS = [r for r in os.environ.get("POP_REGIONS", "GB,US").split(",") if r]

def discover_popular():
    """Trending videos per YouTube category (1 quota unit per call): covers the 'viral' side cheaply."""
    out = {}
    for region in POP_REGIONS:
        for cid, name in POP_CATS.items():
            if QUOTA_HIT: return out
            try:
                d = api("videos", part="snippet,statistics", chart="mostPopular", videoCategoryId=cid,
                        regionCode=region, maxResults=25)
            except Exception:
                continue
            for it in d.get("items", []):
                st = it.get("statistics", {})
                out[it["id"]] = {"id": it["id"], "title": it["snippet"]["title"], "channel": it["snippet"]["channelTitle"], "desc": it["snippet"].get("description", "")[:700].replace("\n", " "),
                                 "views": int(st.get("viewCount", 0)), "comments": int(st.get("commentCount", 0)),
                                 "query": "trending", "cat": "trending: %s (%s)" % (name, region)}
    return list(out.values())

def discover():
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DAYS)).strftime("%Y-%m-%dT00:00:00Z")
    ids = collections.OrderedDict()
    for q in QUERIES:
        if QUOTA_HIT: break
        try:
            d = api("search", part="snippet", q=q, type="video", order="viewCount",
                    publishedAfter=since, maxResults=PER_QUERY, relevanceLanguage="en")
        except Exception as e:
            print("search failed:", q, e, file=sys.stderr); continue
        for it in d.get("items", []): ids[it["id"]["videoId"]] = q
    vids = []
    keys = list(ids)
    for i in range(0, len(keys), 50):
        d = api("videos", part="snippet,statistics", id=",".join(keys[i:i+50]))
        for it in d.get("items", []):
            st = it.get("statistics", {})
            vids.append({"id": it["id"], "title": it["snippet"]["title"], "channel": it["snippet"]["channelTitle"], "desc": it["snippet"].get("description", "")[:700].replace("\n", " "),
                         "views": int(st.get("viewCount", 0)), "comments": int(st.get("commentCount", 0)),
                         "query": ids[it["id"]], "cat": QUERY_CAT.get(ids[it["id"]], "other")})
    vids += discover_popular() if os.environ.get("POPULAR", "1") == "1" else []
    seen_ids, uniq = set(), []
    for v in vids:
        if v["id"] in seen_ids: continue
        seen_ids.add(v["id"]); uniq.append(v)
    return [v for v in uniq if v["comments"] >= MIN_COMMENTS]

def comments(vid):
    out, tok = [], None
    for _ in range(PAGES):
        try:
            d = api("commentThreads", part="snippet", videoId=vid, order="relevance", maxResults=100,
                    textFormat="plainText", **({"pageToken": tok} if tok else {}))
        except Exception as e:
            print("comments failed:", vid, e, file=sys.stderr); break
        for it in d.get("items", []):
            s = it["snippet"]["topLevelComment"]["snippet"]
            out.append({"text": s["textDisplay"], "likes": s.get("likeCount", 0)})
        tok = d.get("nextPageToken")
        if not tok: break
    return out

def score(c):
    if NOISE.search(c["text"]) or not mostly_english(c["text"]) or len(c["text"]) < 25: return None
    hits = [k for k, rx in SIGNALS.items() if re.search(rx, c["text"], re.I)]
    if not hits: return None
    s = sum(WEIGHT[h] for h in hits) * (1 + math.log1p(c["likes"]))
    return hits, round(s, 2)

def phrases(texts, n=3):
    cnt = collections.Counter()
    for t in texts:
        w = [x for x in re.findall(r"[a-z][a-z']+", t.lower())]
        for i in range(len(w) - n + 1):
            g = w[i:i+n]
            if g[0] in STOP or g[-1] in STOP: continue
            cnt[" ".join(g)] += 1
    return [(g, c) for g, c in cnt.most_common(40) if c >= 2][:15]

def mock():
    vids = [{"id": "MOCK1", "title": "I built a $20K/mo invoice chaser", "channel": "Demo", "views": 90000, "comments": 400, "query": "mock", "cat": "small business software"}]
    cm = {"MOCK1": [
        {"text": "What's the app called? Is there a tool that does this for plumbers?", "likes": 40},
        {"text": "I would pay for this, I currently track it manually in a spreadsheet and it takes me hours", "likes": 12},
        {"text": "Someone should build this for dentists, I wish it existed", "likes": 8},
        {"text": "great video", "likes": 3}]}
    return vids, cm

def main():
    if os.environ.get("MOCK"): vids, cm = mock()
    else:
        if not KEY: sys.exit("Set YOUTUBE_API_KEY")
        vids = discover()
        random.shuffle(vids)
        vids = vids[:int(os.environ.get("MAX_VIDEOS", "120"))]
        cm = {}
        for v in vids:
            if time.time() - START > float(os.environ.get("BUDGET", "200")):
                print("time budget reached, saving partial results", file=sys.stderr)
                break
            cm[v["id"]] = comments(v["id"])
    rows, per_video = [], []
    for v in vids:
        n = 0
        for c in cm.get(v["id"], []):
            r = score(c)
            if r:
                n += 1; rows.append({"cat": v.get("cat", "other"), "video": v["title"], "url": "https://youtu.be/" + v["id"], "signals": r[0],
                                     "score": r[1], "likes": c["likes"], "text": c["text"][:400].replace("\n", " ")})
        per_video.append((n, v))
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda r: -r["score"]):
        k = re.sub(r"\W+", " ", r["text"].lower())[:120]
        if k in seen: continue
        seen.add(k); uniq.append(r)
    rows = uniq
    today = dt.date.today().isoformat()
    md = ["# YouTube demand report — %s" % today,
          "Videos scanned: %d | signal comments (all types): %d | window: last %d days" % (len(vids), len(rows), DAYS),
          "Categories scanned today: %s" % ", ".join(CATEGORIES),
          ("**WARNING: %d API errors%s. Report is incomplete. First error: %s**" % (len(ERRORS), " (QUOTA EXHAUSTED)" if QUOTA_HIT else "", ERRORS[0])) if ERRORS else "API errors: none", "",
          "## Recurring phrases in signal comments (candidate problems)"]
    md += ["- %s (%d)" % g for g in phrases([r["text"] for r in rows])] or ["- none"]
    DEMAND = ("ask_for_tool", "would_pay", "wish_build", "manual_pain")
    demand_rows = [r for r in rows if any(x in DEMAND for x in r["signals"])]
    bycat = collections.defaultdict(list)
    for r in demand_rows: bycat[r["cat"]].append(r)
    md += ["", "## Signals per category (top 6 each; a category with 0 means nothing found, not nothing exists)"]
    for cat in list(CATEGORIES) + ["trending"]:
        rs = [r for c2, x in bycat.items() for r in x if (c2 == cat or (cat == "trending" and c2.startswith("trending")))]
        vids_n = len({r["url"] for r in rs})
        md.append("### %s — %d signal comments across %d videos" % (cat, len(rs), vids_n))
        for r in rs[:6]:
            md.append("- [%s] score %s, %d likes — \"%s\" — _%s_ (%s)" % (",".join(r["signals"]), r["score"], r["likes"], r["text"], r["video"], r["url"]))
    md += ["", "## Same ask on 2+ different videos (strongest evidence of a real recurring need)"]
    grams = collections.defaultdict(set)
    for r in demand_rows:
        w = re.findall(r"[a-z][a-z']+", r["text"].lower())
        for i in range(len(w) - 2):
            g = w[i:i+3]
            if g[0] in STOP or g[-1] in STOP: continue
            grams[" ".join(g)].add(r["url"])
    rep = sorted(((g, len(u)) for g, u in grams.items() if len(u) >= 2), key=lambda x: -x[1])[:15]
    md += ["- %s (%d videos)" % x for x in rep] or ["- none yet"]
    md += ["", "## Money-method verdicts (what viewers say happened when they tried it; anecdotes, not proof)"]
    ver = [r for r in rows if "result_report" in r["signals"]][:12]
    for r in ver:
        md.append("- %d likes — \"%s\" — _%s_ (%s)" % (r["likes"], r["text"], r["video"], r["url"]))
    if not ver: md.append("- none yet")
    md += ["", "## Videos with most signal comments"]
    for n, v in sorted(per_video, key=lambda x: -x[0])[:15]:
        md.append("- %d signals — %s (%s, %d views) https://youtu.be/%s" % (n, v["title"], v["channel"], v["views"], v["id"]))
        if n and v.get("desc"): md.append("  - description: %s" % v["desc"][:500])
    os.makedirs("reports", exist_ok=True)
    open("reports/latest.md", "w").write("\n".join(md))
    open("reports/latest.json", "w").write(json.dumps({"date": today, "rows": rows[:200]}, indent=1))
    print("\n".join(md[:25]))

if __name__ == "__main__": main()
