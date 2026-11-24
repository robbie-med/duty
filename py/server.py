#!/usr/bin/env python3
"""The Way — server. Python standard library only.

Local mode (default): binds 127.0.0.1 and serves only loopback Host names, with editing on.
Public mode: set PUBLIC_HOST to the public host name (and FAMILY_HOST=0.0.0.0, or put it behind a reverse proxy).
Requests for PUBLIC_HOST are read-only: anyone can browse, no one can change anything. READ_ONLY=1 makes
local use read-only too."""
import http.cookies
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import db
import kin
import library

ROOT = os.path.dirname(os.path.abspath(__file__))
HOST = os.environ.get("FAMILY_HOST", "127.0.0.1")
PORT = int(os.environ.get("FAMILY_PORT", "3517"))
PUBLIC_HOST = (os.environ.get("PUBLIC_HOST") or "").strip().lower()
READ_ONLY = os.environ.get("READ_ONLY", "") not in ("", "0", "false")
LOCK = threading.Lock()

with open(os.path.join(ROOT, "way", "duties.json"), encoding="utf-8") as _f:
    _seed = json.load(_f)
META = {k: _seed[k] for k in ("spheres", "traditions", "roles", "standings")}

PERSON_F = ("name", "ko_name", "sex", "birth", "death", "household_id", "notes",
            "standing", "standing_date", "standing_note", "headship", "headship_date", "headship_note",
            "carried_by", "carried_note", "birth_order", "burial", "guardian_id")
MATTER_F = ("person_id", "other_id", "kind", "title", "status", "outcome")
STEP_F = ("matter_id", "step", "day", "by_ids", "text")
MATTER_KINDS = {"fault": "a fault", "dispute": "a dispute between kin", "drifting": "one drifting from the family", "cut_off": "whether to cut one off"}
MATTER_STATES = {"open": "open", "restored": "restored", "settled": "settled", "cut_off": "cut off"}
STEPS = {"private": "spoken to privately", "witnesses": "with one or two witnesses", "family": "brought before the family",
         "decision": "decided", "restored": "restored", "note": "note"}
BACKGROUNDS = {      # a family's background: which example family is shown, and which kinship terms appear beside the English
    "anglo": {"label": "Anglo", "langs": []},
    "korean": {"label": "Korean", "langs": ["ko"]},
    "chinese": {"label": "Chinese", "langs": ["zh"]},
    "korean_anglo": {"label": "Korean-Anglo", "langs": ["ko"]},
    "korean_chinese": {"label": "Korean-Chinese", "langs": ["ko", "zh"]},
    "anglo_chinese": {"label": "Anglo-Chinese", "langs": ["zh"]},
}
DEFAULT_BG = "korean_anglo"


def background(con):
    v = db.get_setting(con, "background")
    return v if v in BACKGROUNDS else DEFAULT_BG


def family_duties(con):
    """Every tradition binds every family, whatever its background: together they are what the centuries have
    learned of the duties of kin, weighed in the order of the traditions under Scripture."""
    return db.rows(con, "SELECT * FROM duty")


HEADSHIP = {"": "holds his headship", "renounced": "has stepped down", "abandoned": "has abandoned his family"}
UNION_F = ("a_id", "b_id", "status", "start", "end")
DUTY_F = ("from_role", "to_role", "sphere", "tradition", "citation", "text", "status", "reason", "counter")
ATTEST_F = ("duty_id", "tradition", "citation", "quote", "note")
HOUSE_F = ("name", "head_id", "place")
UNION_STATES = ("married", "separated", "widowed", "divorced", "paramour")
BOND_STATES = ("kept", "strained", "broken", "severed", "unset")
MARK_STATES = ("kept", "poorly", "failing", "na", "unset")     # poorly = kept, but not doing well


class Bad(Exception):
    pass


def graph(con):
    people, unions, links = db.load_graph(con)
    households = db.rows(con, "SELECT id, head_id FROM household")
    return kin.Graph(people, unions, links, households, BACKGROUNDS[background(con)]["langs"]), people, unions, links


def acting_map(g, people):
    """{pid: (acting head, head by right)} for everyone living; a headless house gets the man
    bound to it by kinship as its acting head."""
    out = {}
    for pid in people:
        if not g.alive(pid):
            continue
        r, a = g.house_heads(pid)
        if a is None:
            a = g.bound(pid)[0]
        out[pid] = (a, r)
    return out


def with_standing(r, people, a, b, acting=None, g=None, heir=None, the_head=None):
    """A person's standing (entering / estranged / cut_off / outside), a headship he has left
    (abandoned / renounced), and acting headship are roles too, so duties can be written for them."""
    def tag(side, t):
        if t and t not in r[side]["tags"]:
            r[side]["tags"].append(t)
    for side, pid in (("them", b), ("me", a)):
        st = people[pid].get("standing") or "member"
        tag(side, st if st != "member" else None)
        tag(side, people[pid].get("headship") or None)
        for t in (g.status_tags(pid, heir) if g else []):   # departed, minor, fatherless, aged, widow, heir of the line
            tag(side, t)
    if acting:
        for head, ward, hs, ws in ((a, b, "me", "them"), (b, a, "them", "me")):
            act, right = acting.get(ward, (None, None))
            if act == head and right != head:     # acting in another's place, or bound by kinship
                tag(hs, "acting_head"); tag(ws, "in_keeping")
                if "minor" in r[ws]["tags"]:
                    tag(hs, "guardian"); tag(ws, "ward")
    if g:
        for side, pid, other in (("me", a, b), ("them", b, a)):
            if not g.alive(pid):
                continue
            if (people[pid].get("standing") or "member") == "member":
                tag(side, "member")              # the "one another" duties hold between members of the family
            if pid != other and g.alive(other) and g.house_head(other) == pid:
                tag(side, "household_head")      # he acts at the head of the other's house
            if the_head is not None and pid == the_head and pid != other:
                tag(side, "clan_elder")          # the Head of the family, toward each member
        path = r["them"]["path"]
        if path == "P" and g.sex(a) == "f" and any(g.alive(x) for x in g.spouses.get(a, [])):
            tag("me", "married_daughter")        # a married daughter, toward her own parents
        if path == "P" and g.kind.get((b, a)) == "adopted":       # an heir taken in, and the father who took him
            tag("them", "adoptive_parent"); tag("me", "adopted_child")
        if path == "C" and g.kind.get((a, b)) == "adopted":
            tag("them", "adopted_child"); tag("me", "adoptive_parent")
        if path == "C" and g.sex(b) == "f" and any(g.alive(x) for x in g.spouses.get(b, [])):
            tag("them", "married_daughter")
    return r


def family_head(con, g, people):
    """There is always one man at the head of the family, the same whoever you stand as.
    A named Head stands while he lives; otherwise the rule: the senior living man of your own
    father's line ("This is me"), or, before that is set, of the largest male line in the tree.
    Returns (person id or None if the tree holds no living man, named?)."""
    named = db.get_setting(con, "clan_elder")
    if named in people and g.holds(named):
        return named, True
    me = db.get_setting(con, "me")
    h = g.main_head(me) if me in people else None
    return h or g.main_line_head(), False


def succession(con, g, people, head):
    """Order of succession to the Head of the family (first 8), with who still holds."""
    me = db.get_setting(con, "me")
    base = me if me in people else head
    line = g.line_succession(base) if base in people else []
    named = db.get_setting(con, "clan_elder")
    if named in people and g.alive(named) and named in line:
        line.remove(named)
    if named in people and g.alive(named):
        line.insert(0, named)
    return [{"id": i, "holds": g.holds(i)} for i in line[:8]]


def house_line(g, pid):
    line = [{"id": i, "why": why, "holds": g.holds(i)} for i, why in g.house_line(pid)]
    if g.alive(pid) and not any(x["holds"] for x in line):
        man, via, _ = g.bound(pid)
        if man is not None:
            how = g.relation(pid, via)["them"]["en"]
            line.append({"id": man, "holds": True, "bound": True,
                         "why": "bound by kinship: " + ("nearest kinsman (%s)" % how if man == via else
                                                        "head of the house of %s (%s)" % (g.people[via]["name"], how))})
    return line


def of_the_family(g, people, head):
    """The living who are of the family, and so under the Head's authority: related to him by kinship (blood or
    marriage), not as a paramour, and not set outside it. The database also holds people who are not: a paramour,
    or an in-law's own relations (a brother-in-law's adoptive parents), who head houses of their own."""
    rel = g.relations(head) if head is not None else {}
    out = []
    for pid in people:
        if not g.alive(pid) or (people[pid].get("standing") or "member") == "outside":
            continue
        tags = rel[pid]["them"]["tags"] if pid in rel else []
        if pid == head or head is None or ("kin" in tags and "paramour" not in tags and "outside" not in tags):
            out.append(pid)
    return sorted(out)


def heads_of(g, people):
    """{pid: acting head (a bound kinsman for a headless house)} and {pid: bound kinsman}, for the living."""
    heads, bound = {}, {}
    for pid in people:
        if not g.alive(pid):
            continue
        r, a = g.house_heads(pid)
        if a is None:
            man = g.bound(pid)[0]
            if man is not None:
                a, bound[pid] = man, man
        heads[pid] = a
    return heads, bound


def api_ifdies(con, q):
    """What follows if this man dies: who takes up each house he heads or keeps, which go headless, who becomes
    the Head of the family, and which minors are left with no guardian named. Nothing is written."""
    pid = int(q.get("id", ["0"])[0])
    g, people, unions, links = graph(con)
    if pid not in people or not g.alive(pid):
        raise Bad("no such living person")
    head, _ = family_head(con, g, people)
    family = set(of_the_family(g, people, head))
    before, bound_before = heads_of(g, people)
    after_people = {k: dict(v) for k, v in people.items()}
    after_people[pid]["death"] = "?"
    households = db.rows(con, "SELECT id, head_id FROM household")
    g2 = kin.Graph(after_people, unions, links, households, g.langs)
    after, bound_after = heads_of(g2, after_people)
    head2 = family_head(con, g2, after_people)[0]          # a named Head who dies gives way to the rule
    changes = []
    for k in sorted(after, key=lambda k: people[k].get("birth") or "9999"):
        if k == pid or k not in family or before.get(k) == after.get(k):
            continue
        minor = "minor" in g2.status_tags(k)
        guardian = people[k].get("guardian_id")
        changes.append({"id": k, "before": before.get(k), "after": after.get(k), "bound": k in bound_after,
                        "minor": minor, "guardian": guardian if guardian and g2.alive(guardian) else None})
    return {"id": pid, "head_before": head, "head_after": head2, "changes": changes,
            "headless": [c["id"] for c in changes if c["after"] is None],
            "minors_unguarded": [c["id"] for c in changes if c["minor"] and not c["guardian"]]}


def api_state(con, q):
    g, people, unions, links = graph(con)
    head, named = family_head(con, g, people)
    heads, right, bound = {}, {}, {}
    for pid in people:
        r, a = g.house_heads(pid)
        if a is None and g.alive(pid):         # headless: who is bound by kinship to act for it
            man, via, _ = g.bound(pid)
            if man is not None:
                a, bound[pid] = man, {"by": man, "via": via, "via_en": g.relation(pid, via)["them"]["en"]}
        heads[pid] = a
        if r != a:
            right[pid] = r
    for pid, p in people.items():
        p["living"] = g.alive(pid)          # one judgment of who is living, shared with the page
    family = of_the_family(g, people, head)
    bg = background(con)
    return {"people": list(people.values()), "unions": unions, "links": links,
            "head": head, "head_named": named, "heads": heads, "heads_right": right, "bound": bound, "family": family,
            "lineage_heir": g.lineage_heir(head),
            "succession": succession(con, g, people, head),
            "households": db.rows(con, "SELECT * FROM household ORDER BY name"),
            "me": db.get_setting(con, "me"), "clan_elder": db.get_setting(con, "clan_elder"),
            "meta": dict(META, headship=HEADSHIP, matter_kinds=MATTER_KINDS, matter_states=MATTER_STATES, steps=STEPS),
            "library": library.stats(),
            "matters": [dict(m, steps=[dict(x, by_ids=json.loads(x["by_ids"] or "[]")) for x in
                                       db.rows(con, "SELECT * FROM matter_step WHERE matter_id=? ORDER BY day, id", (m["id"],))])
                        for m in db.rows(con, "SELECT * FROM matter ORDER BY status != 'open', at DESC")],
            "duties": with_translations(db.rows(con, "SELECT * FROM duty ORDER BY id"), [])[0],
            "native_langs": BACKGROUNDS[bg]["langs"],
            "attest": db.rows(con, "SELECT * FROM attest ORDER BY duty_id, id"),
            "background": bg, "backgrounds": {k: v["label"] for k, v in BACKGROUNDS.items()},
            "mode": "own" if own_mode() else "example",
            "rulings": with_translations([], [dict(r, held_by=json.loads(r["held_by"]), grounds=json.loads(r["grounds"]))
                                              for r in db.rows(con, "SELECT * FROM ruling ORDER BY category, topic")])[1]}


def _marks_for(marks, person, toward):
    return {str(d): m for (p, t, d), m in marks.items() if p == person and t == toward}


def api_ego(con, q, ego):
    g, people, _, _ = graph(con)
    if ego not in people:
        raise Bad("no such person")
    duties = family_duties(con)
    bonds, marks = db.current_bonds(con), db.current_marks(con)
    rels = {}
    paths = g.paths_from(ego)
    acting = acting_map(g, people)
    head = family_head(con, g, people)[0]
    heir = g.lineage_heir(head)                               # 종손: heir of the main line
    for pid, r in g.relations(ego).items():
        with_standing(r, people, ego, pid, acting, g, heir, head)
        chain = paths[pid][1]
        rels[pid] = {
            "them": r["them"], "me": r["me"], "via": chain[-2] if len(chain) > 1 else ego,
            "owe": [d["id"] for d in kin.duties_between(duties, r["me"]["tags"], r["them"]["tags"])],
            "owed": [d["id"] for d in kin.duties_between(duties, r["them"]["tags"], r["me"]["tags"])],
            "bond_out": bonds.get((ego, pid)), "bond_in": bonds.get((pid, ego)),
            "marks_out": _marks_for(marks, ego, pid), "marks_in": _marks_for(marks, pid, ego)}
    roles = kin.standing_roles(ego, g, head)
    collective = [d["id"] for d in kin.collective_duties(duties, roles)]
    return {"ego": people[ego], "rels": rels, "standing": roles, "collective": collective,
            "head": head, "under": g.house_head(ego),
            "house_line": house_line(g, ego),
            "marks_collective": _marks_for(marks, ego, 0),
            "bonds": [{"a": a, "b": b, "state": v["state"]} for (a, b), v in bonds.items()]}


def api_between(con, q):
    ids = [int(x) for x in (q.get("ids", [""])[0]).split(",") if x.strip().isdigit()][:40]
    g, people, _, _ = graph(con)
    duties = family_duties(con)
    bonds = db.current_bonds(con)
    acting = acting_map(g, people)
    head = family_head(con, g, people)[0]
    heir = g.lineage_heir(head)                               # 종손: heir of the main line
    out = {}
    for a in ids:
        if a not in people:
            continue
        rel = g.relations(a)
        out[a] = {}
        for b in ids:
            if b == a or b not in rel:
                continue
            r = with_standing(rel[b], people, a, b, acting, g, heir, head)
            out[a][b] = {"en": r["them"]["en"], "ko": r["them"]["ko"], "ko_term": r["them"]["ko_term"], "zh": r["them"]["zh"],
                         "zh_hant": r["them"]["zh_hant"], "chon": r["them"]["chon"],
                         "owe": [d["id"] for d in kin.duties_between(duties, r["me"]["tags"], r["them"]["tags"])],
                         "bond": bonds.get((a, b))}
    return {"ids": ids, "matrix": out}


def api_rollup(con, q):
    _, people, _, _ = graph(con)
    duties = {d["id"]: d for d in family_duties(con)}
    bonds, marks = db.current_bonds(con), db.current_marks(con)
    counts, torn = {}, []
    for (a, b), v in bonds.items():
        if a not in people or b not in people:
            continue
        counts[v["state"]] = counts.get(v["state"], 0) + 1
        if v["state"] != "kept":
            torn.append({"a": a, "b": b, "state": v["state"], "note": v["note"], "at": v["at"]})
    per_person, per_sphere, failing = {}, {}, []
    for (p, t, d), v in marks.items():
        if p not in people or d not in duties or v["state"] not in ("kept", "poorly", "failing"):
            continue
        pp = per_person.setdefault(p, {"kept": 0, "poorly": 0, "failing": 0})
        pp[v["state"]] += 1
        sp = per_sphere.setdefault(duties[d]["sphere"], {"kept": 0, "poorly": 0, "failing": 0})
        sp[v["state"]] += 1
        if v["state"] in ("failing", "poorly"):           # failing first, then not doing well
            failing.append({"person": p, "toward": t, "duty": d, "state": v["state"], "note": v["note"], "at": v["at"]})
    order = {"severed": 0, "broken": 1, "strained": 2}
    torn.sort(key=lambda x: (order.get(x["state"], 9), -x["at"]))
    failing.sort(key=lambda x: (x["state"] != "failing", -x["at"]))
    return {"bond_counts": counts, "torn": torn, "per_person": per_person,
            "per_sphere": per_sphere, "failing": failing}


def api_history(con, q):
    a, b = int(q["a"][0]), int(q["b"][0])
    return {"bonds": db.rows(con, "SELECT * FROM bond WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?) "
                                  "ORDER BY at DESC LIMIT 100", (a, b, b, a)),
            "marks": db.rows(con, "SELECT * FROM mark WHERE (person_id=? AND toward_id=?) OR (person_id=? AND toward_id=?) "
                                  "ORDER BY at DESC LIMIT 200", (a, b, b, a))}


def api_library(con, q):
    return {"results": library.search(q.get("q", [""])[0], 25), "stats": library.stats()}


HTML = "text/html; charset=utf-8"
STATIC = {"/": (None, HTML), "/index.html": ("index.html", HTML), "/full": ("index.html", HTML),
          "/m": ("m.html", HTML), "/m.html": ("m.html", HTML),
          "/maps.js": ("maps.js", "text/javascript; charset=utf-8"), "/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"),
          "/about.js": ("about.js", "text/javascript; charset=utf-8")}
UI_LOCALES = ("ko", "zh-Hant", "zh-Hans")
CONTENT = {}            # locale -> {"duties": {seed_ix: text}, "rulings": {seed_ix: {field: text, "points": [...]}}}


def content(locale):
    """Translations of the seeded duties and rulings (way/i18n/<locale>.json), read once."""
    if locale not in CONTENT:
        path = os.path.join(ROOT, "way", "i18n", locale + ".json")
        CONTENT[locale] = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    return CONTENT[locale]


def with_translations(duties, rulings):
    """Each seeded duty and ruling carries its translations, unless the family has reworded it (then its own words
    stand in every language)."""
    seed = _seed["duties"]
    for d in duties:
        ix = d.get("seed_ix")
        if ix is not None and ix < len(seed) and kin_text(d["text"]) == kin_text(seed[ix][5]):
            d["i18n"] = {loc: content(loc).get("duties", {}).get(str(ix)) for loc in UI_LOCALES if content(loc).get("duties", {}).get(str(ix))}
    for r in rulings:
        ix = r.get("seed_ix")
        if ix is not None:
            r["i18n"] = {loc: content(loc).get("rulings", {}).get(str(ix)) for loc in UI_LOCALES if content(loc).get("rulings", {}).get(str(ix))}
    return duties, rulings


def kin_text(s):
    return db.american(s or "").strip()
MOBILE_UA = re.compile(r"Mobi|Android|iPhone|iPod|IEMobile|Opera Mini|Windows Phone|BlackBerry", re.I)


def cookie(headers, name):
    jar = http.cookies.SimpleCookie()
    try:
        jar.load(headers.get("Cookie") or "")
    except http.cookies.CookieError:
        return ""
    return jar[name].value if name in jar else ""


def own_mode():
    """A family's own record once it exists (or FAMILY_DB names one); until then the example families."""
    return bool(os.environ.get("FAMILY_DB")) or os.path.exists(db.DB_PATH)


def db_path(headers):
    """The database this request is about: the family's own, or the example family for the background chosen
    on the page (a way_bg cookie), built the first time it is asked for."""
    if own_mode():
        return db.DB_PATH
    bg = cookie(headers, "way_bg")
    bg = bg if bg in BACKGROUNDS else DEFAULT_BG
    path = os.path.join(db.DATA, "examples", bg + ".db")
    if not os.path.exists(path):
        import example
        con = db.connect(path)
        try:
            example.build(con, bg)
        finally:
            con.close()
    return path


def front_page(headers):
    """ "/" is the full site on a computer and the phone view (m.html) on a phone. A way_ui cookie
    (set by the "full site" / "phone view" switches) overrides the guess."""
    jar = http.cookies.SimpleCookie()
    try:
        jar.load(headers.get("Cookie") or "")
    except http.cookies.CookieError:
        pass
    ui = jar["way_ui"].value if "way_ui" in jar else ""
    if ui in ("full", "mobile"):
        return "index.html" if ui == "full" else "m.html"
    return "m.html" if MOBILE_UA.search(headers.get("User-Agent") or "") else "index.html"
GET = {"/api/state": api_state, "/api/between": api_between, "/api/rollup": api_rollup, "/api/ifdies": api_ifdies,
       "/api/history": api_history, "/api/library": api_library}


def clean(body, fields):
    data = {k: body[k] for k in fields if k in body}
    for k in ("household_id", "head_id", "carried_by", "birth_order"):
        if k in data and data[k] in ("", 0, "0"):
            data[k] = None
    return data


def check(con, what, method, body):
    """Refuse values the rest of the app would silently misread. Runs before every write."""
    if method == "DELETE":
        return
    if what == "person" and "sex" in body and body["sex"] not in ("m", "f", "u"):
        raise Bad("sex must be m, f or u")
    if what == "person" and body.get("headship") and body["headship"] not in HEADSHIP:
        raise Bad("bad headship")
    if what == "person" and body.get("birth_order") not in (None, "", 0) and not str(body["birth_order"]).isdigit():
        raise Bad("birth order must be a whole number")
    if what == "duty":
        for k, allowed in (("from_role", META["roles"]), ("to_role", META["roles"]),
                           ("sphere", META["spheres"]), ("tradition", META["traditions"]),
                           ("status", ("draft", "confirmed", "retired"))):
            if body.get(k) and body[k] not in allowed:
                raise Bad("unknown %s %r" % (k.replace("_", " "), body[k]))
    if what == "attest" and method == "POST":
        if body.get("tradition") not in META["traditions"]:
            raise Bad("unknown tradition %r" % body.get("tradition"))
        if not con.execute("SELECT 1 FROM duty WHERE id=?", (body.get("duty_id"),)).fetchone():
            raise Bad("no such duty")
    head = (body.get("value") if what == "setting" and body.get("key") == "clan_elder"
            else body.get("head_id") if what == "household" else None)
    if head not in (None, "", 0):
        g, people, _, _ = graph(con)
        if head not in people or g.sex(head) != "m" or not g.alive(head):
            raise Bad("the Head of the family must be a living man" if what == "setting"
                      else "the head of a household must be a living man")


RULING_STATES = ("proposed", "accepted", "kept", "revise", "rejected")


def decide_ruling(con, rid, body):
    """accepted: the practice becomes a retired duty carrying the resolution and the grounds' citations.
    kept: the house keeps it after all, so it becomes a draft duty. Either way the duty is made once and then
    follows the decision (a later change of mind moves the same duty, it never makes a second)."""
    r = con.execute("SELECT * FROM ruling WHERE id=?", (rid,)).fetchone()
    if not r:
        raise Bad("no such ruling")
    r = dict(r)
    if "action" in body and body["action"] not in ("", "keep", "revise", "retire"):
        raise Bad("bad action")
    for k in ("note", "resolution", "allowed", "revision", "action"):
        if k in body:
            con.execute("UPDATE ruling SET %s=? WHERE id=?" % k, (str(body[k]), rid))
    st = body.get("status")
    if st:
        if st not in RULING_STATES:
            raise Bad("bad status")
        con.execute("UPDATE ruling SET status=?, at=? WHERE id=?", (st, time.time(), rid))
        r = dict(con.execute("SELECT * FROM ruling WHERE id=?", (rid,)).fetchone())
        if r["category"] in ("house", "review"):       # an existing duty judged against the literature
            d = con.execute("SELECT id FROM duty WHERE seed_ix=?", (r["duty_seed_ix"],)).fetchone()
            if not d:
                raise Bad("that duty is no longer on the list")
            did, grounds = d[0], json.loads(r["grounds"])
            if st == "accepted":                       # apply the proposed action; "kept" leaves the duty as written
                if r["action"] in ("keep", "revise"):
                    if r["action"] == "revise" and r["revision"].strip():
                        con.execute("UPDATE duty SET text=? WHERE id=?", (r["revision"].strip(), did))
                    for g in grounds:                  # the literature that supports it (or its revision) becomes its provenance
                        if (g.get("stance", "support") == "support" or g.get("attest")) and g.get("tradition") in META["traditions"] and not con.execute(
                                "SELECT 1 FROM attest WHERE duty_id=? AND citation=?", (did, g.get("citation", ""))).fetchone():
                            con.execute("INSERT INTO attest(duty_id,tradition,citation,quote) VALUES(?,?,?,?)",
                                        (did, g["tradition"], g.get("citation", ""), g.get("quote", "")))
                elif r["action"] == "retire":
                    against = "; ".join(dict.fromkeys(g["citation"] for g in grounds if g.get("stance") == "against" and g.get("citation")))
                    con.execute("UPDATE duty SET status='retired', reason=?, counter=? WHERE id=?", (r["resolution"], against, did))
            con.execute("UPDATE ruling SET duty_id=? WHERE id=?", (did, rid))
            con.commit()
            return {"ok": True}
        if st in ("accepted", "kept"):
            grounds, held = json.loads(r["grounds"]), json.loads(r["held_by"])
            counter = "; ".join(dict.fromkeys(g["citation"] for g in grounds if g.get("citation")))
            reason = r["resolution"] + ((" Still permitted: " + r["allowed"]) if r["allowed"] else "")
            fields = {"status": "retired" if st == "accepted" else "draft", "reason": reason if st == "accepted" else "",
                      "counter": counter if st == "accepted" else ""}
            if r["duty_id"] and con.execute("SELECT 1 FROM duty WHERE id=?", (r["duty_id"],)).fetchone():
                con.execute("UPDATE duty SET status=?, reason=?, counter=? WHERE id=?",
                            (fields["status"], fields["reason"], fields["counter"], r["duty_id"]))
            else:
                first = held[0] if held else {}
                trad = first.get("tradition") if first.get("tradition") in META["traditions"] else "clan"
                cur = con.execute("INSERT INTO duty(from_role,to_role,sphere,tradition,citation,text,status,reason,counter) "
                                  "VALUES(?,?,?,?,?,?,?,?,?)",
                                  (r["from_role"], r["to_role"], r["sphere"] if r["sphere"] in META["spheres"] else "rites", trad,
                                   first.get("citation", ""), r["practice"], fields["status"], fields["reason"], fields["counter"]))
                for h in held[1:]:
                    if h.get("tradition") in META["traditions"]:
                        con.execute("INSERT INTO attest(duty_id,tradition,citation,quote) VALUES(?,?,?,?)",
                                    (cur.lastrowid, h["tradition"], h.get("citation", ""), h.get("quote", "")))
                con.execute("UPDATE ruling SET duty_id=? WHERE id=?", (cur.lastrowid, rid))
    con.commit()
    return {"ok": True}


def write(con, method, parts, body, q):
    """All mutations. parts = path after /api/ split on '/'."""
    what = parts[0]
    rid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    check(con, what, method, body)
    if what == "person":
        if method == "DELETE":
            db.delete_person(con, rid)
            for key in ("me", "clan_elder"):
                if db.get_setting(con, key) == rid:
                    db.set_setting(con, key, None)
            return {"ok": True}
        data = clean(body, PERSON_F)
        if "standing" in data and data["standing"] not in META["standings"]:
            raise Bad("bad standing")
        if method == "POST":
            if not (data.get("name") or "").strip():
                raise Bad("a person needs a name")
            return {"id": db.insert(con, "person", data, PERSON_F)}
        db.update(con, "person", rid, data, PERSON_F)
        return {"ok": True}
    if what == "union":
        if method == "DELETE":
            con.execute("DELETE FROM union_ WHERE id=?", (rid,)); con.commit()
            return {"ok": True}
        data = clean(body, UNION_F)
        if "status" in data and data["status"] not in UNION_STATES:
            raise Bad("status must be one of " + ", ".join(UNION_STATES))
        if method == "POST":
            if not data.get("a_id") or not data.get("b_id") or data["a_id"] == data["b_id"]:
                raise Bad("a marriage needs two different people")
            return {"id": db.insert(con, "union_", data, UNION_F)}
        db.update(con, "union_", rid, data, UNION_F)
        return {"ok": True}
    if what == "link":
        p, c = int(body.get("parent_id") or q.get("parent", [0])[0]), int(body.get("child_id") or q.get("child", [0])[0])
        if method == "DELETE":
            con.execute("DELETE FROM parent_child WHERE parent_id=? AND child_id=?", (p, c)); con.commit()
            return {"ok": True}
        if not p or not c or p == c:
            raise Bad("a parent-child link needs two different people")
        if con.execute("SELECT 1 FROM parent_child WHERE parent_id=? AND child_id=?", (c, p)).fetchone():
            raise Bad("that would make someone their own grandparent")
        con.execute("INSERT OR REPLACE INTO parent_child(parent_id,child_id,kind) VALUES(?,?,?)",
                    (p, c, body.get("kind") or "birth"))
        con.commit()
        return {"ok": True}
    if what == "household":
        if method == "DELETE":
            con.execute("UPDATE person SET household_id=NULL WHERE household_id=?", (rid,))
            con.execute("DELETE FROM household WHERE id=?", (rid,)); con.commit()
            return {"ok": True}
        data = clean(body, HOUSE_F)
        if method == "POST":
            return {"id": db.insert(con, "household", data, HOUSE_F)}
        db.update(con, "household", rid, data, HOUSE_F)
        return {"ok": True}
    if what == "ruling" and method == "PUT" and rid:     # the user's decision on a case
        return decide_ruling(con, rid, body)
    if what == "attest":                               # record (or drop) the duty in another tradition
        if method == "POST":
            return {"id": db.insert(con, "attest", clean(body, ATTEST_F), ATTEST_F)}
        if method == "DELETE" and rid:
            con.execute("DELETE FROM attest WHERE id=?", (rid,)); con.commit()
            return {"ok": True}
        raise Bad("bad request")
    if what == "duty":
        data = clean(body, DUTY_F)
        if method == "POST":
            for k in ("from_role", "to_role", "sphere", "tradition", "text"):
                if not data.get(k):
                    raise Bad("a duty needs " + k)
            return {"id": db.insert(con, "duty", data, DUTY_F)}
        if method == "PUT" and rid:
            db.update(con, "duty", rid, data, DUTY_F)
            return {"ok": True}
        if method == "PUT" and body.get("ids"):          # bulk status change
            if body.get("status") not in ("draft", "confirmed", "retired"):
                raise Bad("bad status")
            con.executemany("UPDATE duty SET status=? WHERE id=?",
                            [(body["status"], int(i)) for i in body["ids"]])
            con.commit()
            return {"ok": True}
    if what == "bond" and method == "POST":
        if body.get("state") not in BOND_STATES:
            raise Bad("bad state")
        db.set_bond(con, int(body["from_id"]), int(body["to_id"]), body["state"], body.get("note") or "")
        return {"ok": True}
    if what == "mark" and method == "POST":
        if body.get("state") not in MARK_STATES:
            raise Bad("bad state")
        db.set_mark(con, int(body["person_id"]), int(body.get("toward_id") or 0), int(body["duty_id"]),
                    body["state"], body.get("note") or "")
        return {"ok": True}
    if what == "matter":
        if method == "DELETE" and rid:
            con.execute("DELETE FROM matter_step WHERE matter_id=?", (rid,))
            con.execute("DELETE FROM matter WHERE id=?", (rid,)); con.commit()
            return {"ok": True}
        data = clean(body, MATTER_F)
        if "kind" in data and data["kind"] not in MATTER_KINDS:
            raise Bad("bad kind of matter")
        if "status" in data and data["status"] not in MATTER_STATES:
            raise Bad("bad state of matter")
        if method == "POST":
            if not data.get("person_id") or not (data.get("title") or "").strip():
                raise Bad("a matter needs the person and a few words on what it is")
            data["at"] = time.time()
            return {"id": db.insert(con, "matter", data, MATTER_F + ("at",))}
        if method == "PUT" and rid:
            db.update(con, "matter", rid, data, MATTER_F)
            return {"ok": True}
    if what == "matter_step":
        if method == "DELETE" and rid:
            con.execute("DELETE FROM matter_step WHERE id=?", (rid,)); con.commit()
            return {"ok": True}
        data = clean(body, STEP_F)
        if data.get("step") not in STEPS:
            raise Bad("bad step")
        if not con.execute("SELECT 1 FROM matter WHERE id=?", (data.get("matter_id"),)).fetchone():
            raise Bad("no such matter")
        if isinstance(data.get("by_ids"), list):
            data["by_ids"] = json.dumps([int(i) for i in data["by_ids"]])
        data["at"] = time.time()
        if method == "POST":
            return {"id": db.insert(con, "matter_step", data, STEP_F + ("at",))}
    if what == "setting" and method == "PUT" and body.get("key") == "background":
        if body.get("value") not in BACKGROUNDS:
            raise Bad("unknown background")
        db.set_setting(con, "background", body["value"])
        return {"ok": True}
    if what == "own" and method == "POST":           # start the family's own record (empty), leaving the examples
        if own_mode():
            raise Bad("this copy already keeps a family's own record")
        bg = body.get("background") if body.get("background") in BACKGROUNDS else DEFAULT_BG
        own = db.connect(db.DB_PATH)
        try:
            db.set_setting(own, "background", bg)
        finally:
            own.close()
        return {"ok": True}
    if what == "setting" and method == "PUT" and body.get("key") in ("me", "clan_elder"):
        db.set_setting(con, body["key"], body.get("value"))
        return {"ok": True}
    raise Bad("unknown request")




class Handler(BaseHTTPRequestHandler):
    server_version = "TheWay/1"

    def log_message(self, fmt, *args):
        pass

    def send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def local_only(self, write=False):
        """Loopback use, or the public host (read-only). Refuses pages on other sites trying to drive this
        server from the browser (Host and Origin must match)."""
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        origin = self.headers.get("Origin")
        if host in ("127.0.0.1", "localhost"):
            ok = not origin or origin in ("http://127.0.0.1:%d" % PORT, "http://localhost:%d" % PORT)
            if ok and write and READ_ONLY:
                self.send_json({"error": "This copy is read-only."}, 403)
                return False
        elif PUBLIC_HOST and host == PUBLIC_HOST:
            ok = not origin or origin in ("https://" + PUBLIC_HOST, "http://" + PUBLIC_HOST)
            if ok and write:
                self.send_json({"error": "This is a read-only demonstration. Download The Way to keep your own family's record."}, 403)
                return False
        else:
            ok = False
        if not ok:
            self.send_json({"error": "local use only"}, 403)
        return ok

    def do_GET(self):
        if not self.local_only():
            return
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/health":
            return self.send_json({"ok": True})
        m = re.match(r"^/i18n/(ko|zh-Hant|zh-Hans)\.json$", u.path)
        if m:
            path = os.path.join(ROOT, "web", "i18n", m.group(1) + ".json")
            data = open(path, "rb").read() if os.path.exists(path) else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return self.wfile.write(data)
        if u.path in STATIC:
            name, ctype = STATIC[u.path]
            name = name or front_page(self.headers)
            with open(os.path.join(ROOT, "web", name), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if u.path == "/":
                self.send_header("Vary", "User-Agent, Cookie")
            self.end_headers()
            return self.wfile.write(data)
        try:
            with LOCK:
                con = db.connect(db_path(self.headers))
                try:
                    if u.path in GET:
                        out = GET[u.path](con, q)
                        if u.path == "/api/state":           # the page hides editing where it would be refused
                            host = (self.headers.get("Host") or "").split(":")[0].lower()
                            out["read_only"] = READ_ONLY or bool(PUBLIC_HOST and host == PUBLIC_HOST)
                        return self.send_json(out)
                    if u.path.startswith("/api/ego/"):
                        return self.send_json(api_ego(con, q, int(u.path.rsplit("/", 1)[1])))
                finally:
                    con.close()
        except (Bad, ValueError, KeyError, IndexError) as e:
            return self.send_json({"error": str(e) or "bad request"}, 400)
        except Exception as e:                       # answer in JSON rather than drop the connection
            return self.send_json({"error": "server error: %s" % e}, 500)
        self.send_json({"error": "not found"}, 404)

    def _write(self):
        if not self.local_only(write=True):
            return
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            return self.send_json({"error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            with LOCK:
                con = db.connect(db_path(self.headers))
                try:
                    out = write(con, self.command, u.path[5:].strip("/").split("/"), body, parse_qs(u.query))
                finally:
                    con.close()
            self.send_json(out)
        except (Bad, ValueError, KeyError, TypeError) as e:
            self.send_json({"error": str(e) or "bad request"}, 400)
        except Exception as e:
            self.send_json({"error": "server error: %s" % e}, 500)

    do_POST = do_PUT = do_DELETE = _write


def export_way():
    con = db.connect()
    out = dict(_seed)
    att = {}
    for a in db.rows(con, "SELECT * FROM attest ORDER BY id"):
        att.setdefault(a["duty_id"], []).append([a["tradition"], a["citation"], a["quote"]])
    out["duties"] = [[d["from_role"], d["to_role"], d["sphere"], d["tradition"], d["citation"], d["text"],
                      {k: v for k, v in (("status", d["status"]), ("reason", d["reason"]), ("counter", d["counter"]),
                                         ("attest", att.get(d["id"]))) if v}]
                     for d in db.rows(con, "SELECT * FROM duty ORDER BY id")]
    out["attest"] = []
    path = os.path.join(ROOT, "way", "the-way-export.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("Wrote", path)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "serve":
        if own_mode():
            db.connect().close()
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
        print("The Way on http://%s:%d/%s" % (HOST, PORT, ", public (read-only) as %s" % PUBLIC_HOST if PUBLIC_HOST else ""), flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    elif cmd == "index":
        library.build()
    elif cmd == "export-way":
        export_way()
    elif cmd == "merge" and len(sys.argv) == 4:      # one person entered twice: merge DROP into KEEP
        con = db.connect()
        keep, drop = int(sys.argv[2]), int(sys.argv[3])
        names = [db.rows(con, "SELECT name FROM person WHERE id=?", (i,)) for i in (keep, drop)]
        db.merge_people(con, keep, drop)
        print("Merged %s (#%d) into %s (#%d)" % (names[1][0]["name"], drop, names[0][0]["name"], keep))
    elif cmd == "import-gramps":
        import import_gramps
        import_gramps.main(sys.argv[2:])
    else:
        sys.exit("usage: run.sh serve | index | import-gramps [--tree NAME] [--apply] | merge KEEP_ID DROP_ID | export-way")


if __name__ == "__main__":
    main()
