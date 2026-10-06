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
  "ask_for_tool": r"\b(what('?s| is) (the|this|that)
