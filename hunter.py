#!/usr/bin/env python3
"""YouTube demand miner. Uses the OFFICIAL YouTube Data API v3 only.
Finds recent 'I built X / making money' style videos, reads their public comments,
and surfaces comments where viewers ask for a tool, say they'd pay, or describe manual pain.
Env: YOUTUBE_API_KEY. Optional: MOCK=1 to run offline on sample data."""
import os, re, json, math, sys, datetime as dt, collections, urllib.parse, urllib.request

KEY = os.environ.get("YOUTUBE_API_KEY", "")
DAYS = int(os.environ.get("DAYS", "30"))
PER_QUERY = int(os.environ.get("PER_QUERY", "15"))
MIN_COMMENTS = int(os.environ.get("MIN_COMMENTS", "25"))
PAGES = int(os.environ.get("PAGES", "2"))
QUERIES = [q.strip() for q in os.environ.get("QUERIES", "").split("|") if q.strip()] or [
    "I built an app that makes money", "micro saas revenue breakdown", "simple app idea making money 2026",
    "boring business idea profitable", "I built a tool for", "side project MRR", "this didn't exist so I built it",
    "small business software problem", "automation business I built", "niche app idea validation",
]
SIGNALS = {
  "ask_for_tool": r"\b(what('?s| is) (the|this|that) (app|tool|software|website|site|extension)|is there (a|an|any) (app|tool|software|website|way|service)|does (this|anyone|something like) (exist|know)|what (app|tool|software) (is|was|do)|name of (the|this) (app|tool))\b",
  "would_pay": r"\b(i('d| would| will) (gladly |happily )?(pay|buy|subscribe)|take my money|shut up and take|where do i (sign|pay|buy)|how much (is|does|would)|what('s| is) the (price|cost))\b",
  "wish_build": r"\b(i wish|someone (should|needs to|please) (build|make|create)|why (isn'?t|doesn'?t) (there|anyone)|need(s)? (this|something like this)|please make)\b",
  "manual_pain": r"\b(takes? (me )?(hours|forever|ages|so long)|i (currently|still) (do|use|track).{0,30}(manually|spreadsheet|excel)|(manually|by hand)|i hate (doing|having to)|struggling with|nightmare)\b",
  "link_ask": r"\b(link\??|where can i (get|find|download|buy)|can (you|i) (share|get) (the )?(link|app|tool))\b",
}
WEIGHT = {"would_pay": 3.0, "ask_for_tool": 2.0, "wish_build": 2.0, "manual_pain": 2.0, "link_ask": 0.5}
STOP = set("the a an and or but to of in on for with is are was were be it this that i you we they my your our at as by from so if not no do does did can could would should have has had just very really like get got about what how why when there then than too its it's i'm i've don't can't dont cant im ive one out up all more some any".split())

def api(path, **p):
    p["key"] = KEY
    url = "https://www.googleapis.com/youtube/v3/%s?%s" % (path, urllib.parse.urlencode(p))
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)

def discover():
    since = (dt.datetime.utcnow() - dt.timedelta(days=DAYS)).strftime("%Y-%m-%dT00:00:00Z")
    ids = collections.OrderedDict()
    for q in QUERIES:
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
            vids.append({"id": it["id"], "title": it["snippet"]["title"], "channel": it["snippet"]["channelTitle"],
                         "views": int(st.get("viewCount", 0)), "comments": int(st.get("commentCount", 0)),
                         "query": ids[it["id"]]})
    return [v for v in vids if v["comments"] >= MIN_COMMENTS]

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
    hits = [k for k, rx in SIGNALS.items() if re.search(rx, c["text"], re.I)]
    if not hits: return None
    s = sum(WEIGHT[h] for h in hits) * (1 + math.log1p(c["likes"]))
    return hits, round(s, 2)

def phrases(texts, n=2):
    cnt = collections.Counter()
    for t in texts:
        w = [x for x in re.findall(r"[a-z][a-z']+", t.lower())]
        for i in range(len(w) - n + 1):
            g = w[i:i+n]
            if g[0] in STOP or g[-1] in STOP: continue
            cnt[" ".join(g)] += 1
    return [(g, c) for g, c in cnt.most_common(40) if c >= 3][:15]

def mock():
    vids = [{"id": "MOCK1", "title": "I built a $20K/mo invoice chaser", "channel": "Demo", "views": 90000, "comments": 400, "query": "mock"}]
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
        vids = discover(); cm = {v["id"]: comments(v["id"]) for v in vids}
    rows, per_video = [], []
    for v in vids:
        n = 0
        for c in cm.get(v["id"], []):
            r = score(c)
            if r:
                n += 1; rows.append({"video": v["title"], "url": "https://youtu.be/" + v["id"], "signals": r[0],
                                     "score": r[1], "likes": c["likes"], "text": c["text"][:400].replace("\n", " ")})
        per_video.append((n, v))
    rows.sort(key=lambda r: -r["score"])
    today = dt.date.today().isoformat()
    md = ["# YouTube demand report — %s" % today,
          "Videos scanned: %d | signal comments: %d | window: last %d days" % (len(vids), len(rows), DAYS), "",
          "## Recurring phrases in signal comments (candidate problems)"]
    md += ["- %s (%d)" % g for g in phrases([r["text"] for r in rows])] or ["- none"]
    md += ["", "## Top signal comments (would-pay / ask-for-tool / wish / manual pain)"]
    for r in rows[:40]:
        md.append("- [%s] score %s, %d likes — \"%s\" — _%s_ (%s)" % (",".join(r["signals"]), r["score"], r["likes"], r["text"], r["video"], r["url"]))
    md += ["", "## Videos with most signal comments"]
    for n, v in sorted(per_video, key=lambda x: -x[0])[:15]:
        md.append("- %d signals — %s (%s, %d views) https://youtu.be/%s" % (n, v["title"], v["channel"], v["views"], v["id"]))
    os.makedirs("reports", exist_ok=True)
    open("reports/latest.md", "w").write("\n".join(md))
    open("reports/latest.json", "w").write(json.dumps({"date": today, "rows": rows[:200]}, indent=1))
    print("\n".join(md[:25]))

if __name__ == "__main__": main()
