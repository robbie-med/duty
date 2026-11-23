#!/usr/bin/env python3
"""Mine the source texts (sources/**/*.md) for duties between family roles, with DeepSeek.

  python3 mine.py plan                     passages, characters and a cost estimate; spends nothing
  python3 mine.py extract [--only GROUP] [--limit N]
                                           read each passage, write way/mined/extract/*.jsonl (resumable)
  python3 mine.py consolidate              per role pair: attach each finding to an existing duty as an
                                           attestation, or gather it into a new duty (way/mined/consolidated.json)
  python3 mine.py seed                     append new duties and attestations to way/duties.json, and write
                                           way/mined/review.md (every addition with its source)

Key, base URL and model come from .env (DEEPSEEK_API_KEY, DEEPSEEK_BASE, DEEPSEEK_MODEL), read at call time.
The run stops before the DeepSeek balance falls below RESERVE dollars.
Rites the house does not keep (offerings to the dead, the cult of saints, divination) are not skipped:
they come in retired, each with the house's reason and the commands against it (RETIRE below)."""
import glob
import http.client
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(ROOT, "way", "duties.json")
OUT = os.path.join(ROOT, "way", "mined")
RESERVE = 0.60                    # dollars left untouched on the DeepSeek account
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")

# Why the house does not keep these, and what stands against them. Written by hand; the model only sorts into them.
RETIRE = {
    "ancestral_rite": (
        "We give the living gifts and bows, and that is honor rightly given (Gen 23:7; 1 Kgs 2:19). The dead cannot "
        "receive it: they know nothing of what is done here (Eccl 9:5-6; Job 14:21), and they are with the Lord or "
        "awaiting judgment, beyond our reach (Luke 16:26; 2 Cor 5:8; Heb 9:27). Food set before them, and bows made to "
        "their tablet, portrait or body as part of the rite, only make sense if they are present to receive it and able "
        "to bless in return, and the jesa liturgy says so itself: it calls the spirit down (강신 降神), urges it to eat "
        "(유식 侑食), closes the door for it (합문 闔門), sends it off (사신 辭神), and drinks its blessing (음복 飮福). "
        "Treating the dead as present to receive and to bless is what Scripture forbids: inquiring of the dead "
        "(Deut 18:11; Isa 8:19), giving food to the dead (Deut 26:14), eating sacrifices offered to the dead (Ps 106:28). "
        "Our own tradition drew the same line: every civil respect at a burial is kept, but kneeling or praying toward "
        "the dead is laid aside as superstitious and of no benefit to the dead (Westminster Directory, Of Burial, 1645). "
        "So we bow to the mourners and keep every civil courtesy, and we honor our dead in the ways they never needed to "
        "receive: we bury them well, mourn them, keep their names, stories and graves, carry out their just wishes, and "
        "care for those they left.",
        "Deut 18:10-12; Deut 26:14; Ps 106:28; Isa 8:19-20; Eccl 9:5-6; Job 14:21; Luke 16:26; 1 Cor 10:19-21; "
        "Westminster Directory, Of Burial of the Dead (1645); WCF 21.1-2; WLC 105, 108-109"),
    "saint_cult": (
        "We honor the faithful dead as examples and give thanks to God for them (Heb 11; 12:1; 13:7). We do not pray to "
        "them, ask their intercession, or bow before their images and relics: prayer is made to God alone through the "
        "one Mediator (Matt 6:9; 1 Tim 2:5), the dead are not ours to call on (Isa 8:19), and bowing before images to "
        "give them religious honor is what the second commandment forbids (Ex 20:4-5).",
        "Ex 20:3-5; Matt 4:10; 1 Tim 2:5; Col 2:18; Rev 19:10; 22:8-9; WCF 21.2; WLC 105, 108-109; Heidelberg 94, 97-98"),
    "divination": (
        "Seeking guidance or blessing from spirits, fate, omens, lucky days or the siting of graves is forbidden. The "
        "house is ordered by God's word and his providence.",
        "Lev 19:26, 31; Deut 18:10-14; Isa 8:19-20; Acts 16:16-18; WLC 105"),
}


# ---------- the model ----------
def env():
    """Read .env at call time, never at import, so a stale or missing value can't send the key to the wrong place."""
    e = {}
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                e[k] = v
    e.update({k: v for k, v in os.environ.items() if k.startswith("DEEPSEEK_")})
    if not e.get("DEEPSEEK_API_KEY"):
        sys.exit("No DEEPSEEK_API_KEY in .env")
    return e["DEEPSEEK_API_KEY"], e.get("DEEPSEEK_BASE", "https://api.deepseek.com").rstrip("/"), e.get("DEEPSEEK_MODEL", "deepseek-v4-pro")


def _http(method, path, body=None, timeout=300):
    key, base, _ = env()
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def balance():
    info = _http("GET", "/user/balance")["balance_infos"]
    return sum(float(b["total_balance"]) for b in info if b["currency"] == "USD")


USAGE = {"in": 0, "out": 0, "calls": 0}
AUTHORS = {}
FAILS = {}


def ask(system, user, max_tokens=24000, effort="high"):
    offpeak_wait()
    """One JSON-mode chat call; returns the parsed object (or {} after three failures).
    The model reasons before it answers, so the allowance is large enough that reasoning can't crowd out the answer."""
    _, _, model = env()
    for attempt in range(3):
        r = None
        try:
            body = {"model": model, "temperature": 0.1, "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            body["reasoning_effort"] = effort
            r = _http("POST", "/chat/completions", body)
            u = r.get("usage", {})
            USAGE["in"] += u.get("prompt_tokens", 0); USAGE["out"] += u.get("completion_tokens", 0); USAGE["calls"] += 1
            return json.loads(r["choices"][0]["message"]["content"])
        except Exception as e:                   # network drops, bad or empty bodies: retry, never kill the run
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 402, 403):
                sys.exit("DeepSeek refused the request (%s): check the key and balance." % e.code)
            FAILS[type(e).__name__] = FAILS.get(type(e).__name__, 0) + 1
            if isinstance(r, dict):
                why = "finish:%s" % ((r.get("choices") or [{}])[0].get("finish_reason"),)
                FAILS[why] = FAILS.get(why, 0) + 1
            time.sleep(4 * (attempt + 1))
    return {}


def offpeak_wait():
    """DeepSeek charges double 01:00-04:00 and 06:00-10:00 UTC, Monday to Friday: wait those hours out."""
    while True:
        t = time.gmtime()
        peak = t.tm_wday < 5 and (1 <= t.tm_hour < 4 or 6 <= t.tm_hour < 10)
        if not peak:
            return
        time.sleep(300)


class Budget:
    """Checks the real balance every few calls and stops while there is still room for the calls already in
    flight (they are billed even if their answer is never used)."""
    def __init__(self, in_flight=1):
        self.in_flight = in_flight
        self.start = balance(); self.n = 0
        print("DeepSeek balance $%.2f; will stop at $%.2f" % (self.start, RESERVE))
        if self.start <= RESERVE:
            sys.exit("Balance is already at or below the reserve.")

    def check(self):
        self.n += 1
        if self.n % 5 == 0:
            b = balance()
            if self.n % 15 == 0:
                print("   … balance $%.3f (spent $%.3f, %d calls, %d tokens in, %d out; retried %s)" % (b, self.start - b, USAGE["calls"], USAGE["in"], USAGE["out"], FAILS or "none"), flush=True)
            if b <= RESERVE + 0.04 * self.in_flight:
                sys.exit("Stopped near the reserve ($%.2f left). Top up and re-run: it continues where it left off." % b)


# ---------- the texts ----------
def front(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    meta = {k: v.strip().strip('"').strip("'") for k, v in re.findall(r"^(\w+):[ \t]*(.*)$", m.group(1), flags=re.M)} if m else {}
    return meta, text[m.end():] if m else text


def works():
    """Every source file, skipping a Chinese original when its English translation sits beside it."""
    files = sorted(glob.glob(os.path.join(ROOT, "sources", "**", "*.md"), recursive=True))
    have = set(files)
    out = []
    for f in files:
        if re.search(r"\.(zh|ko)\.md$", f) and re.sub(r"\.(zh|ko)\.md$", ".en.md", f) in have:
            continue
        meta, body = front(open(f, encoding="utf-8").read())
        if meta.get("tradition") == "research" or re.search(r"/sources/(scripture|adjudication)/", f):
            continue                                   # briefs, the Bible and the adjudication texts are evidence, not mined for duties
        out.append((f, meta, body))
    return out


def passages(body, cjk):
    """(heading path, text) pieces of a few thousand characters, cut at ## sections."""
    limit = 2600 if cjk else 7000
    h1 = h2 = ""
    cur, cur_heads, size, out = [], [], 0, []

    def flush():
        nonlocal cur, cur_heads, size
        if cur and sum(len(x) for x in cur) > 200:
            label = cur_heads[0] if len(cur_heads) == 1 else "%s … %s" % (cur_heads[0], cur_heads[-1].split(" · ")[-1])
            out.append((label, "\n\n".join(cur)))
        cur, cur_heads, size = [], [], 0

    for block in re.split(r"\n(?=#{1,2} )", body):
        m = re.match(r"^(#{1,2}) +(.*)", block)
        text = block[m.end():].strip() if m else block.strip()
        if m and m.group(1) == "#":
            flush(); h1 = m.group(2).strip(); h2 = ""
        elif m:
            h2 = m.group(2).strip()
        head = " · ".join(x for x in (h1, h2) if x) or "(opening)"
        if not text:
            continue
        if size + len(text) > limit:
            flush()
        while len(text) > limit * 1.5:                # one very long section: cut it
            cut = text.rfind("\n\n", 0, limit) or limit
            cur.append(text[:cut]); cur_heads.append(head); flush(); text = text[cut:].strip()
        cur.append(text); cur_heads.append(head); size += len(text)
    flush()
    return out


def short_work(meta, path):
    t = meta.get("title") or os.path.basename(path)
    return re.sub(r"\s*\(.*?\)", "", t)[:80]


# ---------- extract ----------
def vocab():
    seed = json.load(open(SEED, encoding="utf-8"))
    return seed


def extract_prompt(seed):
    roles = "; ".join("%s = %s" % kv for kv in seed["roles"].items())
    spheres = "; ".join("%s = %s" % kv for kv in seed["spheres"].items())
    examples = "\n".join('- %s → %s: "%s"' % (d[0], d[1], d[5]) for d in seed["duties"][:: max(1, len(seed["duties"]) // 8)][:8])
    return f"""You read source texts for an app that manages a family clan: who heads each house, and who owes what to whom.
From the passage you are given, list each distinct OBLIGATION that one family role owes another (or owes the household or the clan) which the passage states or plainly implies.

Roles (use these keys only): {roles}
Spheres (use these keys only): {spheres}

Rules:
- from_role and to_role must be keys from the role list. If no key fits, use the nearest one and name the missing role in "needs_role" (for example "lineage heir (宗子/종손)", "adopted heir", "widow", "lineage elder"). Otherwise "needs_role" is "".
- Duties toward someone who has died (burial, mourning, memory, their wishes, their grave) use to_role "departed".
- "text": one plain sentence in American English spelling (honor, labor, behavior, neighbor), in the imperative, in the voice of these examples:
{examples}
- "citation": the work's short title plus the section from the heading you are given, e.g. "Liji, Nei Ze 12" or "Gouge, Domesticall Duties 3.12". Be exact; never invent a section number.
- "quote": at most 30 words from the passage that carry the obligation; if the passage is in Chinese or Korean, give the original words then " — " and your English rendering.
- "category": "duty" for ordinary obligations; "ancestral_rite" for offerings, bows, prayers, tablets or rites addressed to ancestors or the dead (祭, 祠堂, 제사, 차례); "saint_cult" for praying to or venerating saints, Mary, angels, images or relics, or praying for the dead; "divination" for omens, lucky days, geomancy (風水), spirits or shamans; "contested" for a practice a Bible-believing Reformed Christian household would likely question or reject even though this tradition commends it (for example concubinage or secondary wives, polygamy, the "seven grounds" for putting away a wife, forbidding a widow to remarry or praising widow suicide, selling, pledging or exposing children, self-mutilation for a parent, a parent ruling a married son's household over his wife, vows of celibacy, caste or bondage rules). Do not skip any of these: list them with their category, and for anything not "duty" say in "conflict" what it conflicts with (a Scripture or a teaching), in a few words.
- Leave out ceremonial minutiae (dress, bowing angles, dishes) unless they carry an obligation between people, and leave out mere narrative.
- At most 12 items. If the passage holds no obligation between family roles, return an empty list.

Answer with JSON only: {{"items": [{{"from_role": "...", "to_role": "...", "sphere": "...", "text": "...", "citation": "...", "quote": "...", "category": "duty", "conflict": "", "needs_role": ""}}]}}"""


def done_keys(path):
    if not os.path.exists(path):
        return set()
    return {json.loads(l)["key"] for l in open(path, encoding="utf-8") if l.strip()}


def cmd_plan(args):
    tot_chars = tot_pass = 0
    rows = []
    for f, meta, body in works():
        cjk = len(CJK.findall(body[:4000])) > 400
        ps = passages(body, cjk)
        chars = sum(len(t) for _, t in ps)
        tot_chars += chars; tot_pass += len(ps)
        rows.append((os.path.relpath(f, ROOT), meta.get("tradition", "?"), len(ps), chars, cjk))
    for r in rows:
        print("%-62s %-11s %4d passages %9d chars%s" % (r[0][:62], r[1], r[2], r[3], "  (CJK)" if r[4] else ""))
    cjk_chars = sum(r[3] for r in rows if r[4])
    tokens_in = (tot_chars - cjk_chars) / 4 + cjk_chars * 1.1 + tot_pass * 900        # + the instructions on every call
    tokens_out = tot_pass * 550
    print("\n%d works, %d passages, %d characters (%d CJK)." % (len(rows), tot_pass, tot_chars, cjk_chars))
    tokens_out = tot_pass * 3000                    # answers plus the model's reasoning
    print("About %.1fM tokens in, %.1fM out (reasoning included). At about $0.50/M in and $1.00/M out (V4 Pro): about $%.2f."
          % (tokens_in / 1e6, tokens_out / 1e6, tokens_in / 1e6 * 0.5 + tokens_out / 1e6 * 1.0))


def cmd_extract(args):
    """Passages run in parallel (the model reasons for a minute or more on each); each answer is appended to its
    work's .jsonl as it arrives, so an interrupted run resumes where it stopped."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    only = args[args.index("--only") + 1] if "--only" in args else None
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 12
    effort = args[args.index("--effort") + 1] if "--effort" in args else "low"   # reading one passage needs little deliberation
    seed = vocab()
    system = extract_prompt(seed)
    budget = Budget(in_flight=workers)
    os.makedirs(os.path.join(OUT, "extract"), exist_ok=True)
    lock, jobs = threading.Lock(), []
    for f, meta, body in works():
        rel = os.path.relpath(f, os.path.join(ROOT, "sources"))
        if only and not rel.startswith(only + "/"):
            continue
        out = os.path.join(OUT, "extract", rel.replace("/", "__").replace(".md", ".jsonl"))
        have = done_keys(out)
        cjk = len(CJK.findall(body[:4000])) > 400
        work = short_work(meta, f)
        todo = [(h, t) for h, t in passages(body, cjk) if hashlib.sha1((h + t[:200]).encode()).hexdigest()[:16] not in have]
        if not todo:
            continue
        for head, text in todo:
            jobs.append((out, rel, work, meta, head, text))
    if limit is not None:
        jobs = jobs[:limit]
    apath = os.path.join(OUT, "authors.json")     # anthologies: passage -> [author, dates, tradition]
    AUTHORS.update(json.load(open(apath, encoding="utf-8")) if os.path.exists(apath) else {})
    print("%d passages to read, %d at a time" % (len(jobs), workers), flush=True)
    stop = threading.Event()

    def one(job):
        out, rel, work, meta, head, text = job
        offpeak_wait()
        if stop.is_set():
            return
        user = "Work: %s\nTradition: %s\n%sHeading: %s\n\nPassage:\n%s" % (work, meta.get("tradition", ""),
               "About this work: %s\n" % meta["note"] if meta.get("note") else "", head, text)   # e.g. scholarship: report its customs, not its analysis
        res = ask(system, user, max_tokens=16000, effort=effort)
        if not res:
            return                                     # unanswered: left for the next run
        items = [i for i in res.get("items", []) if isinstance(i, dict) and i.get("text")]
        key = hashlib.sha1((head + text[:200]).encode()).hexdigest()[:16]
        author, _, trad = AUTHORS.get("%s|%s" % (rel, key), (None, None, meta.get("tradition", "")))
        for i in items:
            i["tradition"] = trad                      # an anthology essay counts under its own author's tradition
            if author and author != "the editors":
                i["author"] = author
                i["citation"] = "%s, in %s" % (author, i.get("citation", ""))
            if i.get("from_role") not in seed["roles"] or i.get("to_role") not in seed["roles"]:
                i["needs_role"] = i.get("needs_role") or "%s → %s" % (i.get("from_role"), i.get("to_role"))
                i["from_role"] = i["from_role"] if i.get("from_role") in seed["roles"] else "kin"
                i["to_role"] = i["to_role"] if i.get("to_role") in seed["roles"] else "kin"
            if i.get("sphere") not in seed["spheres"]:
                i["sphere"] = "honour"
        with lock:
            with open(out, "a", encoding="utf-8") as w:
                w.write(json.dumps({"key": hashlib.sha1((head + text[:200]).encode()).hexdigest()[:16], "work": work,
                                    "file": rel, "heading": head, "items": items}, ensure_ascii=False) + "\n")
            try:
                budget.check()
            except SystemExit as e:
                print(e, flush=True); stop.set()

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, jobs))
    report(budget)


def report(budget):
    b = balance()
    print("Done: %d calls, %d tokens in, %d out, spent $%.3f; balance $%.2f." % (USAGE["calls"], USAGE["in"], USAGE["out"], budget.start - b, b))


# ---------- consolidate ----------
def findings():
    out = []
    for path in sorted(glob.glob(os.path.join(OUT, "extract", "*.jsonl"))):
        for line in open(path, encoding="utf-8"):
            rec = json.loads(line)
            for i in rec["items"]:
                i["work"] = rec["work"]; i["file"] = rec["file"]
                out.append(i)
    return out


CONSOLIDATE = """You keep the list of duties for a family clan. For ONE pair of roles you are given the duties already on the list (with ids) and new findings from source texts (numbered).
For each finding decide:
- if it states the same obligation as a duty already on the list (same substance, even in other words or from another tradition), answer {"finding": n, "existing": id};
- otherwise put it in a new group with the findings that state the same new obligation: {"finding": n, "group": g}.
Then give every new group one plain imperative sentence in American English spelling, in the voice of the existing duties, faithful to its findings: "groups": [{"group": g, "text": "..."}].
Be strict: only match when the substance is truly the same; a narrower or different obligation is a new group.
Answer with JSON only: {"decisions": [...], "groups": [...]}"""


def cmd_consolidate(args):
    seed = vocab()
    found = findings()
    by_pair = {}                                       # flagged practices go to the rulings (cmd_cases), never to duties
    for k, i in enumerate(found):
        if i.get("category", "duty") != "duty":
            continue
        by_pair.setdefault((i["from_role"], i["to_role"], False), []).append(k)
    existing = {}
    for ix, d in enumerate(seed["duties"]):
        existing.setdefault((d[0], d[1]), []).append((ix, d[5]))
    budget = Budget()
    result = {"attest": [], "new": []}
    for (fr, to, rite), ks in sorted(by_pair.items(), key=lambda kv: -len(kv[1])):
        for start in range(0, len(ks), 40):            # at most 40 findings per call
            part = ks[start:start + 40]
            ex = [] if rite else existing.get((fr, to), [])
            user = "Roles: %s → %s\n\nOn the list already:\n%s\n\nNew findings:\n%s" % (
                fr, to, "\n".join("[%d] %s" % e for e in ex) or "(none)",
                "\n".join("%d. %s  (%s, %s)" % (n, found[k]["text"], found[k]["tradition"], found[k]["citation"]) for n, k in enumerate(part)))
            res = ask(CONSOLIDATE, user, max_tokens=32000)
            texts = {g.get("group"): g.get("text") for g in res.get("groups", []) if isinstance(g, dict)}
            groups = {}
            valid = {e[0] for e in ex}
            for dcs in res.get("decisions", []):
                if not isinstance(dcs, dict) or not isinstance(dcs.get("finding"), int) or not 0 <= dcs["finding"] < len(part):
                    continue
                f = found[part[dcs["finding"]]]
                if dcs.get("existing") in valid:
                    result["attest"].append({"seed_ix": dcs["existing"], "finding": f})
                else:
                    groups.setdefault(dcs.get("group", "x%d" % dcs["finding"]), []).append(f)
            for g, fs in groups.items():
                result["new"].append({"from_role": fr, "to_role": to, "text": texts.get(g) or fs[0]["text"], "findings": fs})
            print("%-28s %3d findings → %d attestations so far, %d new duties so far" % (fr + " → " + to, len(part), len(result["attest"]), len(result["new"])), flush=True)
            budget.check()
    os.makedirs(OUT, exist_ok=True)
    json.dump(result, open(os.path.join(OUT, "consolidated.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    report(budget)


# ---------- seed ----------
def cmd_seed(args):
    sys.path.insert(0, os.path.join(ROOT, "way"))
    from _write_seed import dump
    seed = vocab()
    res = json.load(open(os.path.join(OUT, "consolidated.json"), encoding="utf-8"))
    n_dut, n_att = len(seed["duties"]), len(seed.get("attest", []))
    seen = {(a[0], a[1], a[2]) for a in seed.get("attest", [])}
    for a in res["attest"]:
        f = a["finding"]
        key = (a["seed_ix"], f["tradition"], f["citation"])
        d = seed["duties"][a["seed_ix"]]
        nums = lambda c: set(re.findall(r"\d+", c))
        if f["tradition"] == d[3] and nums(f["citation"]) & nums(d[4]):
            continue                                   # the duty already cites this very place
        if key not in seen and f["tradition"] in seed["traditions"]:
            seen.add(key)
            seed.setdefault("attest", []).append([a["seed_ix"], f["tradition"], f["citation"], f.get("quote", "")])
    review = ["# Mined from the sources (%s)\n" % time.strftime("%Y-%m-%d"),
              "New duties arrive as drafts; rites the house does not keep arrive retired, with the reason and the commands against them.\n"]
    for nd in sorted(res["new"], key=lambda x: (x["from_role"], x["to_role"])):
        fs = [f for f in nd["findings"] if f["tradition"] in seed["traditions"] and f.get("category", "duty") == "duty"]
        if not fs:
            continue
        cats = [f.get("category", "duty") for f in fs]
        cat = next((c for c in ("ancestral_rite", "saint_cult", "divination") if c in cats), "duty")
        first = fs[0]
        sphere = nd.get("sphere") or max(set(f["sphere"] for f in fs), key=[f["sphere"] for f in fs].count)
        extra = {"attest": [[f["tradition"], f["citation"], f.get("quote", "")] for f in fs[1:]]}
        if cat != "duty":
            extra.update(status="retired", reason=RETIRE[cat][0], counter=RETIRE[cat][1])
        needs = sorted({f["needs_role"] for f in fs if f.get("needs_role")})
        if needs:
            extra["needs_role"] = needs
        seed["duties"].append([nd["from_role"], nd["to_role"], sphere if cat == "duty" else "rites", first["tradition"], first["citation"], nd["text"],
                               {k: v for k, v in extra.items() if v}])
        review.append("- **%s → %s** %s%s  \n  %s" % (nd["from_role"], nd["to_role"], nd["text"], " *(retired: %s)*" % cat.replace("_", " ") if cat != "duty" else "",
                      "; ".join("%s: %s" % (seed["traditions"][f["tradition"]], f["citation"]) for f in fs)) + ("  \n  needs a role: " + ", ".join(needs) if needs else ""))
    review.append("\n## Attestations added to existing duties\n")
    for ix, trad, cite, *_ in seed["attest"][n_att:]:
        d = seed["duties"][ix]
        review.append("- %s → %s: %s  \n  %s: %s" % (d[0], d[1], d[5], seed["traditions"][trad], cite))
    dump(seed, SEED)
    open(os.path.join(OUT, "review.md"), "w", encoding="utf-8").write("\n".join(review) + "\n")
    print("Appended %d duties and %d attestations to way/duties.json; see way/mined/review.md"
          % (len(seed["duties"]) - n_dut, len(seed["attest"]) - n_att))


# ---------- rulings: the case against practices the house questions ----------
EVIDENCE = ("scripture", "westminster", "puritan", "english", "newengland", "catholic", "modern", "adjudication")
FLAGGED = ("ancestral_rite", "saint_cult", "divination", "contested")
CATS = {"ancestral_rite": "rites addressed to ancestors or the dead", "saint_cult": "praying to or venerating saints, images or relics, or praying for the dead",
        "divination": "divination, omens, geomancy and spirits", "contested": "practices a Reformed Christian household would question"}


def evidence(every=False):
    """An in-memory search over the evidence texts: one row per ## section (long sections cut into pieces).
    every=True takes every tradition (translations of the Confucian texts too), for judging the house's own protocols."""
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE ev USING fts5(work, heading, body, tradition UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
    for f in sorted(glob.glob(os.path.join(ROOT, "sources", "**", "*.md"), recursive=True)):
        rel = os.path.relpath(f, os.path.join(ROOT, "sources"))
        meta, body = front(open(f, encoding="utf-8").read())
        if rel.endswith((".zh.md", ".ko.md")) or meta.get("tradition") == "research":
            continue
        if not every and not (rel.split("/")[0] in EVIDENCE or meta.get("tradition") in EVIDENCE[:-1]):
            continue
        work = short_work(meta, f)
        if meta.get("tradition") == "scripture":       # the Bible in windows of four verses, each verse kept for exact citation
            verses = re.findall(r"^## (.+?)\n+(.*?)(?=\n#|\Z)", body, flags=re.M | re.S)
            for k in range(0, len(verses), 4):
                win = [(ref.strip(), re.sub(r"\s+", " ", txt).strip()) for ref, txt in verses[k:k + 4]]
                cur = con.execute("INSERT INTO ev VALUES(?,?,?,?)", ("The Bible (KJV)", "%s–%s" % (win[0][0], win[-1][0].split(" ")[-1]) if len(win) > 1 else win[0][0],
                                                                 " ".join(t for _, t in win), "scripture"))
                VERSES[cur.lastrowid] = win
            continue
        for head, text in passages(body, False):
            for k in range(0, len(text), 1800):
                con.execute("INSERT INTO ev VALUES(?,?,?,?)", (work, head, text[k:k + 2000], meta.get("tradition", "")))
    return con


VERSES = {}


def cite_of(p, quote):
    """The citation for a verified quotation: for the Bible, the exact verse or verses it comes from."""
    win = VERSES.get(p.get("rowid"))
    if not win:
        return "%s, %s" % (p["work"], p["heading"].split(" · ")[-1])
    parts = [norm(x) for x in re.split(r"\.\.\.|…", quote) if norm(x)]
    hit = [ref for ref, txt in win if any(q in norm(txt) or norm(txt) in q or (len(q.split()) > 3 and " ".join(q.split()[:4]) in norm(txt))
                                          or (len(q.split()) > 3 and " ".join(q.split()[-4:]) in norm(txt)) for q in parts)]
    if not hit:
        return p["heading"]
    first, last = hit[0], hit[-1]
    return first if first == last else "%s–%s" % (first, last.split(":")[-1] if last.rsplit(" ", 1)[0].split(":")[0] == first.rsplit(" ", 1)[0].split(":")[0] else last)


def search(con, query, n=6):
    words = [w for w in re.findall(r"[A-Za-z]{3,}", query)][:8]
    if not words:
        return []
    for joiner in (" ", " OR "):
        try:
            rows = con.execute("SELECT rowid, work, heading, body, tradition FROM ev WHERE ev MATCH ? ORDER BY bm25(ev, 2.0, 3.0, 1.0) LIMIT ?",
                               (joiner.join('"%s"' % w for w in words), n)).fetchall()
        except Exception:
            rows = []
        if rows:
            return rows
    return []


def norm(t):
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("ſ", "s")
    return re.sub(r"\s+", " ", re.sub(r"[^\w'\s]", " ", t.lower())).strip()


def verified(quote, body):
    """A quotation counts only if its words appear, in order and contiguously, in the passage
    (an ellipsis may join two such runs)."""
    nb = norm(body)
    parts = [norm(p) for p in re.split(r"\.\.\.|…", quote) if norm(p)]
    if not parts or sum(len(p.split()) for p in parts) < 6:
        return False
    pos = 0
    for p in parts:
        i = nb.find(p, pos)
        if i < 0:
            return False
        pos = i + len(p)
    return True


GROUP = """You sort findings from source texts into CASES for a family's book of rulings. Each finding is a practice that some tradition commends and that a Reformed Christian household may not keep.
Group findings that describe the same practice (e.g. all findings about keeping the ancestral shrine and offering seasonal rites form one case; mourning-dress rules for the dead are a different case from offering food to them).
For each case give: "topic" (a short title), "question" (the question the family must answer, one sentence), "practice" (the practice stated as one plain imperative sentence in American English, as its tradition would command it), "from_role" and "to_role" (keys from the findings), "members" (the finding numbers).
Answer with JSON only: {"cases": [{"topic": "...", "question": "...", "practice": "...", "from_role": "...", "to_role": "...", "members": [0, 3]}]}"""

MERGE = """You are given case titles produced in separate batches for one kind of practice. Some name the same practice. Merge duplicates: return {"groups": [[indices of cases that are the same practice], ...]} covering every index exactly once. JSON only."""

QUERIES = """For a case in a family's book of rulings, give the search queries that would find what Scripture (King James Version), the Westminster standards and Directory, Calvin and the Puritans, English and New England law and custom, the Catholic documents, and the missionary and church deliberations on these questions say about it. Each query is 2 to 5 plain English words likely to appear in those old texts (e.g. "offered to the dead", "praying towards the dead corpse", "familiar spirits", "second wife concubine"). Give 10 queries. JSON only: {"queries": ["...", "..."]}"""

DRAFT = """You draft one case for a family's book of rulings. The family is American, Reformed Protestant, with Korean and Confucian roots. A tradition they come from commends the practice below. You are given numbered passages from Scripture and from the stronger traditions they hold to. Using ONLY these passages, set out the case.

Rules:
- Every ground must rest on a quotation copied EXACTLY, word for word, from one passage (8 to 60 words, contiguous; you may join two contiguous runs from the same passage with "..."). Never paraphrase inside a quotation. Never cite a passage for what it does not say.
- "point": one sentence in your words saying what that quotation establishes for this case.
- Be honest. If the passages do not show the practice to be wrong, or show only part of it to be wrong, say so in "verdict" ("set aside", "keep", or "keep in part") and write the resolution accordingly. Distinguish what is set aside from what remains permitted (for instance civil honor to the living, or a duty of memory) in "allowed".
- "resolution": the house's position in 2 to 5 sentences, in American English, plain and firm, built on the grounds.
- Use between 3 and 8 grounds, the strongest first; prefer Scripture, then the Westminster standards, then Calvin and the Puritans and the other sources.

Answer with JSON only: {"verdict": "...", "resolution": "...", "allowed": "...", "grounds": [{"passage": 0, "quote": "...", "point": "..."}]}"""


def cmd_cases(args):
    seed = vocab()
    found = [f for f in findings() if f.get("category") in FLAGGED]
    print("%d flagged findings" % len(found))
    budget = Budget()
    ev = evidence()
    print("evidence: %d passages" % ev.execute("SELECT COUNT(*) FROM ev").fetchone()[0], flush=True)
    path = os.path.join(ROOT, "way", "rulings.json")
    book = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"_about": (
        "Cases for the Rulings tab: practices the house questions or will not keep. Append-only: each case is offered "
        "to the database once and the user's decision stands. Written by mine.py cases; every quotation in 'grounds' "
        "was checked word for word against the source file it cites."), "rulings": []}
    have = {r["topic"].lower() for r in book["rulings"]}
    for cat in FLAGGED:
        fs = [f for f in found if f["category"] == cat]
        if not fs:
            continue
        cases = []
        for start in range(0, len(fs), 60):            # group in batches, then merge across batches
            part = fs[start:start + 60]
            res = ask(GROUP, "Kind: %s\n\nFindings:\n%s" % (CATS[cat], "\n".join(
                "%d. %s → %s: %s (%s, %s)%s" % (n, f["from_role"], f["to_role"], f["text"], f["tradition"], f["citation"],
                                                "  [conflicts with: %s]" % f["conflict"] if f.get("conflict") else "") for n, f in enumerate(part))),
                      max_tokens=32000)
            for c in res.get("cases", []):
                c["findings"] = [part[m] for m in c.get("members", []) if isinstance(m, int) and 0 <= m < len(part)]
                if c["findings"] and c.get("practice"):
                    cases.append(c)
            budget.check()
        if len(fs) > 60 and len(cases) > 1:
            res = ask(MERGE, "\n".join("%d. %s: %s" % (n, c.get("topic"), c.get("practice")) for n, c in enumerate(cases)), max_tokens=16000)
            merged, used = [], set()
            for grp in res.get("groups", []):
                grp = [g for g in grp if isinstance(g, int) and 0 <= g < len(cases) and g not in used]
                if not grp:
                    continue
                used.update(grp)
                head = dict(cases[grp[0]]); head["findings"] = [f for g in grp for f in cases[g]["findings"]]
                merged.append(head)
            merged += [c for n, c in enumerate(cases) if n not in used]
            cases = merged
        print("%s: %d findings → %d cases" % (cat, len(fs), len(cases)), flush=True)
        for c in cases:
            if c["topic"].lower() in have:
                continue
            qs = ask(QUERIES, "Case: %s\nPractice: %s\nWhy questioned: %s" % (c["topic"], c["practice"],
                     "; ".join(sorted({f.get("conflict", "") for f in c["findings"] if f.get("conflict")}))[:600]), max_tokens=8000).get("queries", [])
            seen, pas = set(), []
            per_work = {}
            for q in qs[:12]:
                for rowid, work, head, body, trad in search(ev, q):
                    if rowid in seen or per_work.get(work, 0) >= 5:
                        continue
                    seen.add(rowid); per_work[work] = per_work.get(work, 0) + 1
                    pas.append({"work": work, "heading": head, "body": body, "tradition": trad, "rowid": rowid})
            pas = pas[:36]
            if not pas:
                continue
            held = [{"tradition": f["tradition"], "citation": f["citation"], "quote": f.get("quote", "")} for f in c["findings"]][:20]
            user = "Practice: %s\nTopic: %s\nQuestion: %s\nWhere it is taught: %s\n\nPassages:\n%s" % (
                c["practice"], c["topic"], c.get("question", ""), "; ".join("%s (%s)" % (h["citation"], h["tradition"]) for h in held[:8]),
                "\n\n".join("[%d] %s · %s (%s)\n%s" % (n, p["work"], p["heading"], p["tradition"], p["body"]) for n, p in enumerate(pas)))
            grounds, dropped = [], 0
            for attempt in range(2):
                d = ask(DRAFT, user, max_tokens=32000)
                grounds, dropped = [], 0
                for g in d.get("grounds", []):
                    k = g.get("passage")
                    if isinstance(k, int) and 0 <= k < len(pas) and g.get("quote") and verified(g["quote"], pas[k]["body"]):
                        p = pas[k]
                        grounds.append({"tradition": p["tradition"], "citation": cite_of(p, g["quote"]),
                                        "quote": g["quote"].strip(), "point": american(g.get("point", ""))})
                    else:
                        dropped += 1
                if len(grounds) >= 2:
                    break
                user += "\n\nYour last draft's quotations did not match the passages word for word. Copy them exactly."
            budget.check()
            roles = [f["from_role"] for f in c["findings"]], [f["to_role"] for f in c["findings"]]
            book["rulings"].append({
                "topic": c["topic"], "category": cat, "question": c.get("question", ""), "practice": american(c["practice"]),
                "from_role": c.get("from_role") if c.get("from_role") in seed["roles"] else max(set(roles[0]), key=roles[0].count),
                "to_role": c.get("to_role") if c.get("to_role") in seed["roles"] else max(set(roles[1]), key=roles[1].count),
                "sphere": "rites" if cat != "contested" else max(set(f["sphere"] for f in c["findings"]), key=[f["sphere"] for f in c["findings"]].count),
                "held_by": held, "grounds": grounds, "allowed": american(d.get("allowed", "")),
                "resolution": american(d.get("resolution", "")), "verdict": d.get("verdict", ""), "unverified_dropped": dropped})
            have.add(c["topic"].lower())
            with open(path, "w", encoding="utf-8") as w:
                json.dump(book, w, ensure_ascii=False, indent=1)
            print("  %-60s %d grounds (%d dropped) %s" % (c["topic"][:60], len(grounds), dropped, d.get("verdict", "")), flush=True)
    report(budget)


JUDGE = """You judge one PROTOCOL drafted for a family. It is not received tradition: it was drafted for them, and it has the lowest weight of all. You are given numbered passages from Scripture and from the traditions the family holds, which weigh in this order: Scripture; the Westminster standards; the Puritans and Calvin; English custom and New England law; Catholic teaching; the classical authors; Confucian and Korean custom.

Judge strictly: a protocol is supported only where a passage teaches it or plainly implies it, not because it sounds sensible.
- "verdict": "supported", "partly supported" (part of it is taught; the rest is the drafter's addition), "unsupported" (no passage teaches it), or "contradicted" (a weightier source teaches against it).
- "grounds": 2 to 8 quotations copied EXACTLY, word for word, from one passage each (8 to 60 words, contiguous; two contiguous runs from the same passage may be joined with "..."), each with "stance" ("support" or "against") and a one-sentence "point". Never paraphrase inside a quotation; never cite a passage for what it does not say.
- "action": "keep" if supported as written; "revise" if partly supported or if the sources support a clearer or truer form, giving "revision": one plain imperative sentence in American English saying only what the sources support; "retire" if contradicted, or if unsupported and not a fair inference from the sources.
- "resolution": 2 to 4 sentences in American English explaining the judgment.

Answer with JSON only: {"verdict": "...", "action": "...", "revision": "...", "resolution": "...", "grounds": [{"passage": 0, "quote": "...", "stance": "support", "point": "..."}]}"""

HOUSE_QUERIES = """For a protocol a family has drafted for itself, give the search queries that would find what Scripture (King James Version), the Westminster standards, Calvin and the Puritan household manuals (Gouge, Baxter, Perkins), English and New England law and custom, Catholic teaching, the classical authors and the Confucian classics (in Legge's English) say on the same matter, for or against it. Each query is 2 to 5 plain English words likely to appear in those old texts. Give 10 queries. JSON only: {"queries": ["..."]}"""


def is_house(row):
    return row[3] == "clan" or "Covenant Home" in row[4] or row[4] == "Our house"


def cmd_house(args):
    """Judge every 'Our house' protocol against the literature; each becomes a case in the Rulings tab."""
    seed = vocab()
    path = os.path.join(ROOT, "way", "rulings.json")
    book = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"_about": "Cases for the Rulings tab (see mine.py).", "rulings": []}
    done = {r.get("duty_seed_ix") for r in book["rulings"] if r.get("category") == "house"}
    todo = [(ix, row) for ix, row in enumerate(seed["duties"]) if is_house(row) and ix not in done]
    print("%d protocols to judge" % len(todo), flush=True)
    if not todo:
        return
    budget = Budget()
    ev = evidence(every=True)
    print("evidence: %d passages" % ev.execute("SELECT COUNT(*) FROM ev").fetchone()[0], flush=True)
    for ix, row in todo:
        fr, to, sphere, trad, cite, text = row[:6]
        qs = ask(HOUSE_QUERIES, "Protocol (%s → %s): %s" % (fr, to, text), max_tokens=8000).get("queries", [])
        seen, pas, per_work = set(), [], {}
        for q in qs[:12]:
            for rowid, work, head, body, tr in search(ev, q):
                if rowid in seen or per_work.get(work, 0) >= 4:
                    continue
                seen.add(rowid); per_work[work] = per_work.get(work, 0) + 1
                pas.append({"work": work, "heading": head, "body": body, "tradition": tr, "rowid": rowid})
        pas = pas[:36]
        user = "Protocol (%s → %s): %s\n(drafted as: %s)\n\nPassages:\n%s" % (fr, to, text, cite, "\n\n".join(
            "[%d] %s · %s (%s)\n%s" % (n, p["work"], p["heading"], p["tradition"], p["body"]) for n, p in enumerate(pas)))
        for attempt in range(2):
            d = ask(JUDGE, user, max_tokens=32000)
            grounds, dropped = [], 0
            for g in d.get("grounds", []):
                k = g.get("passage")
                if isinstance(k, int) and 0 <= k < len(pas) and g.get("quote") and verified(g["quote"], pas[k]["body"]):
                    p = pas[k]
                    grounds.append({"tradition": p["tradition"], "citation": cite_of(p, g["quote"]),
                                    "quote": g["quote"].strip(), "stance": "against" if g.get("stance") == "against" else "support",
                                    "point": american(g.get("point", ""))})
                else:
                    dropped += 1
            if grounds or not d.get("grounds"):
                break
            user += "\n\nYour last answer's quotations did not match the passages word for word. Copy them exactly."
        budget.check()
        book["rulings"].append({
            "topic": text if len(text) <= 90 else text[:88] + "…", "category": "house",
            "question": "Our house protocol (%s): does the literature support it?" % cite,
            "practice": text, "from_role": fr, "to_role": to, "sphere": sphere,
            "held_by": [{"tradition": "clan", "citation": cite, "quote": ""}], "grounds": grounds,
            "verdict": d.get("verdict", ""), "action": d.get("action", "") if d.get("action") in ("keep", "revise", "retire") else "",
            "revision": american(d.get("revision", "")), "resolution": american(d.get("resolution", "")),
            "allowed": "", "duty_seed_ix": ix, "unverified_dropped": dropped})
        with open(path, "w", encoding="utf-8") as w:
            json.dump(book, w, ensure_ascii=False, indent=1)
        print("  %-70s %-18s %-7s %d grounds (%d dropped)" % (text[:70], d.get("verdict", ""), d.get("action", ""), len(grounds), dropped), flush=True)
    report(budget)


def american(t):
    sys.path.insert(0, ROOT)
    import db
    return db.american(t or "")


if __name__ == "__main__":
    a = sys.argv[1:]
    {"plan": cmd_plan, "extract": cmd_extract, "consolidate": cmd_consolidate, "seed": cmd_seed, "cases": cmd_cases, "house": cmd_house}.get(a[0] if a else "", lambda _: print(__doc__))(a[1:])
