"""SQLite store. Only three kinds of structural fact are kept (person, union,
parent_child); every relation and role is derived from them in kin.py."""
import json
import os
import re
import sqlite3
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("FAMILY_DATA") or os.path.join(ROOT, "data")     # where the records live (a packaged app uses the user's folder)
DB_PATH = os.environ.get("FAMILY_DB") or os.path.join(DATA, "family.db")
SEED = os.path.join(ROOT, "way", "duties.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS household(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, head_id INTEGER, place TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS person(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, ko_name TEXT DEFAULT '',
  sex TEXT DEFAULT 'u',            -- m / f / u
  birth TEXT DEFAULT '',           -- YYYY or YYYY-MM-DD
  death TEXT DEFAULT '',
  household_id INTEGER, notes TEXT DEFAULT '', vault_note TEXT DEFAULT '',
  ext_id TEXT DEFAULT '');         -- handle in the source tree (Gramps), for re-import
CREATE TABLE IF NOT EXISTS union_(
  id INTEGER PRIMARY KEY, a_id INTEGER NOT NULL, b_id INTEGER NOT NULL,
  status TEXT DEFAULT 'married',   -- married / separated / widowed / divorced
  start TEXT DEFAULT '', end TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS parent_child(
  parent_id INTEGER NOT NULL, child_id INTEGER NOT NULL,
  kind TEXT DEFAULT 'birth',       -- birth / adopted / step
  PRIMARY KEY(parent_id, child_id));
CREATE TABLE IF NOT EXISTS duty(
  id INTEGER PRIMARY KEY, from_role TEXT NOT NULL, to_role TEXT NOT NULL,
  sphere TEXT NOT NULL, tradition TEXT NOT NULL, citation TEXT DEFAULT '',
  text TEXT NOT NULL,
  status TEXT DEFAULT 'draft');    -- draft / confirmed / retired
CREATE TABLE IF NOT EXISTS bond(   -- history; newest row per (from,to) is current
  id INTEGER PRIMARY KEY, from_id INTEGER NOT NULL, to_id INTEGER NOT NULL,
  state TEXT NOT NULL,             -- kept / strained / broken / severed / unset
  note TEXT DEFAULT '', at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mark(   -- history; newest row per (person,toward,duty) is current
  id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL, toward_id INTEGER NOT NULL DEFAULT 0,
  duty_id INTEGER NOT NULL,
  state TEXT NOT NULL,             -- kept / poorly (not doing well) / failing / na / unset
  note TEXT DEFAULT '', at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS setting(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS ruling(  -- a practice the house questions or will not keep, with the case against it, for review
  id INTEGER PRIMARY KEY, seed_ix INTEGER, topic TEXT NOT NULL, category TEXT DEFAULT '',
  question TEXT DEFAULT '', practice TEXT DEFAULT '', from_role TEXT DEFAULT 'kin', to_role TEXT DEFAULT 'kin',
  sphere TEXT DEFAULT 'rites',
  held_by TEXT DEFAULT '[]',      -- JSON [{tradition, citation, quote}]: where the practice is taught
  grounds TEXT DEFAULT '[]',      -- JSON [{tradition, citation, quote, point}]: verified quotations against it
  allowed TEXT DEFAULT '',        -- what remains permitted (civil honor, for instance)
  resolution TEXT DEFAULT '',     -- the house's proposed position
  status TEXT DEFAULT 'proposed', -- proposed / accepted / kept / revise / rejected
  note TEXT DEFAULT '', duty_id INTEGER, at REAL);
CREATE TABLE IF NOT EXISTS matter(  -- a matter before the family: a fault, a dispute, one drifting, a cutting off
  id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL, other_id INTEGER,
  kind TEXT NOT NULL DEFAULT 'fault',   -- fault / dispute / drifting / cut_off
  title TEXT NOT NULL, status TEXT DEFAULT 'open',   -- open / restored / settled / cut_off
  outcome TEXT DEFAULT '', at REAL);
CREATE TABLE IF NOT EXISTS matter_step(  -- what was done, in order: Matt 18:15-17, then the decision and any restoring
  id INTEGER PRIMARY KEY, matter_id INTEGER NOT NULL,
  step TEXT NOT NULL,                   -- private / witnesses / family / decision / restored / note
  day TEXT DEFAULT '', by_ids TEXT DEFAULT '[]', text TEXT DEFAULT '', at REAL);
CREATE TABLE IF NOT EXISTS attest(  -- the same duty as recorded in another tradition or source
  id INTEGER PRIMARY KEY, duty_id INTEGER NOT NULL, tradition TEXT NOT NULL,
  citation TEXT DEFAULT '', quote TEXT DEFAULT '', note TEXT DEFAULT '');
"""


# The family is American: duties, reasons and labels are in American spelling. (Quotations from old
# sources are not touched; they keep the spelling their authors printed.)
US = {"honour": "honor", "honoured": "honored", "honouring": "honoring", "honours": "honors", "honourable": "honorable",
      "dishonour": "dishonor", "dishonoured": "dishonored", "colour": "color", "coloured": "colored", "behaviour": "behavior",
      "neighbour": "neighbor", "neighbours": "neighbors", "labour": "labor", "labours": "labors", "favour": "favor",
      "favouritism": "favoritism", "favourite": "favorite", "endeavour": "endeavor", "saviour": "savior", "centre": "center",
      "defence": "defense", "offence": "offense", "offences": "offenses", "licence": "license", "judgement": "judgment",
      "grey": "gray", "wilful": "willful", "skilful": "skillful", "whilst": "while", "amongst": "among", "learnt": "learned",
      "fulfil": "fulfill", "counsellor": "counselor", "counselled": "counseled", "travelled": "traveled", "ageing": "aging",
      "acknowledgement": "acknowledgment", "recognise": "recognize", "recognised": "recognized", "realise": "realize",
      "organise": "organize", "apologise": "apologize", "criticise": "criticize", "practise": "practice", "plough": "plow"}
_US = re.compile(r"\b(" + "|".join(sorted(US, key=len, reverse=True)) + r")\b", re.I)


def american(text):
    """British spellings to American, keeping a capital where there was one."""
    def fix(m):
        w = US[m.group(1).lower()]
        return w[0].upper() + w[1:] if m.group(1)[0].isupper() else w
    return _US.sub(fix, text or "")


def connect(path=None):
    path = path or DB_PATH
    if path != ":memory:":
        os.makedirs(os.path.dirname(path), exist_ok=True)
    new = path == ":memory:" or not os.path.exists(path)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    if new and path != ":memory:":
        os.chmod(path, 0o600)
    have = [r[1] for r in con.execute("PRAGMA table_info(person)")]
    for col in ("standing TEXT DEFAULT 'member'", "standing_date TEXT DEFAULT ''", "standing_note TEXT DEFAULT ''",
                "headship TEXT DEFAULT ''",        # '' holds / renounced / abandoned
                "headship_date TEXT DEFAULT ''", "headship_note TEXT DEFAULT ''",
                "carried_by INTEGER", "carried_note TEXT DEFAULT ''",   # who actually bears this person's load
                "birth_order INTEGER",             # 1 = first-born; orders siblings who have no dates
                "burial TEXT DEFAULT ''",           # where he lies: the grave the family keeps
                "guardian_id INTEGER"):             # for a minor: the guardian named (in a will) should his parents die
        if col.split()[0] not in have:
            con.execute("ALTER TABLE person ADD COLUMN " + col)
    have = [r[1] for r in con.execute("PRAGMA table_info(duty)")]
    for col in ("reason TEXT DEFAULT ''",          # why the house does not keep it (for retired duties)
                "counter TEXT DEFAULT ''",         # the commands and standards against it
                "seed_ix INTEGER"):                # its row in way/duties.json, so attestations can find it
        if col.split()[0] not in have:
            con.execute("ALTER TABLE duty ADD COLUMN " + col)
    if os.path.exists(SEED):
        seed_duties(con)
    have = [r[1] for r in con.execute("PRAGMA table_info(ruling)")]
    for col in ("verdict TEXT DEFAULT ''",          # what the literature says of it: set aside / keep / supported / contradicted …
                "action TEXT DEFAULT ''",           # for a house protocol: keep / revise / retire
                "revision TEXT DEFAULT ''",         # the proposed rewording, when the action is revise
                "duty_seed_ix INTEGER",             # the existing duty a house protocol case is about
                "rev INTEGER DEFAULT 0"):           # which revision of the case in way/rulings.json this is
        if col.split()[0] not in have:
            con.execute("ALTER TABLE ruling ADD COLUMN " + col)
    seed_rulings(con)
    if not con.execute("SELECT 1 FROM setting WHERE key='spelling_us'").fetchone():
        for did, text, reason in con.execute("SELECT id, text, reason FROM duty").fetchall():
            if american(text) != text or american(reason) != reason:
                con.execute("UPDATE duty SET text=?, reason=? WHERE id=?", (american(text), american(reason), did))
        con.execute("INSERT INTO setting(key,value) VALUES('spelling_us','true')")
    con.commit()
    return con


ORIGINAL_SEED = 90      # rows in the first seed; databases made before 'seed_n' existed have exactly these


def seed_duties(con):
    """The seed file is append-only. Insert only rows this database has not been offered yet,
    so duties the user reworded or retired are never re-added.
    A duty row is [from, to, sphere, tradition, citation, text] with an optional 7th element
    {status, reason, counter, attest: [[tradition, citation, quote], ...]}. The separate "attest" list,
    [[seed row, tradition, citation, quote], ...], records more traditions for duties already offered."""
    with open(SEED, encoding="utf-8") as f:
        seed = json.load(f)
    rows_ = seed["duties"]
    setting = lambda k: (lambda r: json.loads(r[0]) if r else None)(con.execute("SELECT value FROM setting WHERE key=?", (k,)).fetchone())
    put = lambda k, v: con.execute("INSERT INTO setting(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, json.dumps(v)))
    done = setting("seed_n")
    if done is None:
        done = ORIGINAL_SEED if con.execute("SELECT COUNT(*) FROM duty").fetchone()[0] else 0
    if con.execute("SELECT COUNT(*) FROM duty WHERE seed_ix IS NOT NULL").fetchone()[0] == 0:
        for ix, row in enumerate(rows_[:done]):     # databases from before seed_ix: find each offered row by its words
            fr, to, _sphere, _trad, _cite, text = row[:6]
            for d in con.execute("SELECT id, text FROM duty WHERE from_role=? AND to_role=? AND seed_ix IS NULL ORDER BY id", (fr, to)).fetchall():
                if american(d[1]) == american(text):    # the seed may since have been put into American spelling
                    con.execute("UPDATE duty SET seed_ix=? WHERE id=?", (ix, d[0]))
                    break
    for ix in range(done, len(rows_)):
        fr, to, sphere, trad, cite, text = rows_[ix][:6]
        extra = rows_[ix][6] if len(rows_[ix]) > 6 else {}
        cur = con.execute(
            "INSERT INTO duty(from_role,to_role,sphere,tradition,citation,text,status,reason,counter,seed_ix) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (fr, to, sphere, trad, cite, text, extra.get("status", "draft"), extra.get("reason", ""), extra.get("counter", ""), ix))
        for a in extra.get("attest", []):
            con.execute("INSERT INTO attest(duty_id,tradition,citation,quote) VALUES(?,?,?,?)", (cur.lastrowid, a[0], a[1], a[2] if len(a) > 2 else ""))
    if done != len(rows_):
        put("seed_n", len(rows_))
    for ix, old_fr, old_to, fr, to in seed.get("role_fixes", []):
        con.execute("UPDATE duty SET from_role=?, to_role=? WHERE seed_ix=? AND from_role=? AND to_role=?",
                    (fr, to, ix, old_fr, old_to))     # a corrected role pair, unless the user has set the roles himself
    att = seed.get("attest", [])
    adone = setting("seed_attest_n") or 0
    for ix, trad, cite, *quote in att[adone:]:
        d = con.execute("SELECT id FROM duty WHERE seed_ix=?", (ix,)).fetchone()
        if d:                                       # the duty may have been deleted since
            con.execute("INSERT INTO attest(duty_id,tradition,citation,quote) VALUES(?,?,?,?)", (d[0], trad, cite, quote[0] if quote else ""))
    if adone != len(att):
        put("seed_attest_n", len(att))


RULINGS = os.path.join(ROOT, "way", "rulings.json")


def seed_rulings(con):
    """way/rulings.json is append-only like the duties: each case is offered once, and the user's decision stands.
    A case revised in the file (its "rev" raised) replaces one still awaiting his word or sent back as needing work,
    and goes back to awaiting his word; his note on it stays. A case he has decided is never touched."""
    if not os.path.exists(RULINGS):
        return
    with open(RULINGS, encoding="utf-8") as f:
        cases = json.load(f).get("rulings", [])
    r = con.execute("SELECT value FROM setting WHERE key='rulings_n'").fetchone()
    done = json.loads(r[0]) if r else 0
    for ix in range(done, len(cases)):
        c = cases[ix]
        con.execute("INSERT INTO ruling(seed_ix,topic,category,question,practice,from_role,to_role,sphere,held_by,grounds,allowed,resolution,"
                    "verdict,action,revision,duty_seed_ix,at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ix, c["topic"], c.get("category", ""), c.get("question", ""), c.get("practice", ""), c.get("from_role", "kin"),
                     c.get("to_role", "kin"), c.get("sphere", "rites"), json.dumps(c.get("held_by", []), ensure_ascii=False),
                     json.dumps(c.get("grounds", []), ensure_ascii=False), c.get("allowed", ""), c.get("resolution", ""),
                     c.get("verdict", ""), c.get("action", ""), c.get("revision", ""), c.get("duty_seed_ix"), time.time()))
    for ix in range(min(done, len(cases))):      # a revised case reaches one not yet decided, or sent back as needing work
        c = cases[ix]
        if c.get("rev", 0):
            con.execute("UPDATE ruling SET topic=?, question=?, practice=?, held_by=?, grounds=?, allowed=?, resolution=?, verdict=?, action=?, "
                        "revision=?, rev=?, status='proposed' WHERE seed_ix=? AND status IN ('proposed','revise') AND COALESCE(rev,0) < ?",
                        (c["topic"], c.get("question", ""), c.get("practice", ""), json.dumps(c.get("held_by", []), ensure_ascii=False),
                         json.dumps(c.get("grounds", []), ensure_ascii=False), c.get("allowed", ""), c.get("resolution", ""),
                         c.get("verdict", ""), c.get("action", ""), c.get("revision", ""), c["rev"], ix, c["rev"]))
    if done != len(cases):
        con.execute("INSERT INTO setting(key,value) VALUES('rulings_n',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (json.dumps(len(cases)),))


def rows(con, sql, args=()):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def load_graph(con):
    people = {p["id"]: p for p in rows(con, "SELECT * FROM person")}
    unions = rows(con, "SELECT * FROM union_")
    links = rows(con, "SELECT * FROM parent_child")
    return people, unions, links


def insert(con, table, data, allowed):
    keys = [k for k in data if k in allowed]
    cur = con.execute(
        "INSERT INTO %s(%s) VALUES(%s)" % (table, ",".join(keys), ",".join("?" * len(keys))),
        [data[k] for k in keys])
    con.commit()
    return cur.lastrowid


def update(con, table, rid, data, allowed):
    keys = [k for k in data if k in allowed]
    if keys:
        con.execute("UPDATE %s SET %s WHERE id=?" % (table, ",".join(k + "=?" for k in keys)),
                    [data[k] for k in keys] + [rid])
        con.commit()


def current_bonds(con):
    """{(from,to): {state,note,at}} — newest row wins; 'unset' clears."""
    out = {}
    for r in rows(con, "SELECT * FROM bond ORDER BY at, id"):
        k = (r["from_id"], r["to_id"])
        if r["state"] == "unset":
            out.pop(k, None)
        else:
            out[k] = {"state": r["state"], "note": r["note"], "at": r["at"]}
    return out


def current_marks(con):
    """{(person,toward,duty): {state,note,at}}"""
    out = {}
    for r in rows(con, "SELECT * FROM mark ORDER BY at, id"):
        k = (r["person_id"], r["toward_id"], r["duty_id"])
        if r["state"] == "unset":
            out.pop(k, None)
        else:
            out[k] = {"state": r["state"], "note": r["note"], "at": r["at"]}
    return out


def set_bond(con, a, b, state, note=""):
    con.execute("INSERT INTO bond(from_id,to_id,state,note,at) VALUES(?,?,?,?,?)",
                (a, b, state, note, time.time()))
    con.commit()


def set_mark(con, person, toward, duty, state, note=""):
    con.execute("INSERT INTO mark(person_id,toward_id,duty_id,state,note,at) VALUES(?,?,?,?,?,?)",
                (person, toward or 0, duty, state, note, time.time()))
    con.commit()


def get_setting(con, key, default=None):
    r = con.execute("SELECT value FROM setting WHERE key=?", (key,)).fetchone()
    return json.loads(r[0]) if r else default


def set_setting(con, key, value):
    con.execute("INSERT INTO setting(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
    con.commit()


def _better_date(a, b):
    """Of two dates for the same event, the more informative ('' < '?' < '1890' < '1890-03-02')."""
    rank = lambda d: 0 if not d else 1 if d == "?" else 1 + len(d)
    return b if rank(b) > rank(a) else a


def merge_people(con, keep, drop):
    """One person entered twice: fold `drop` into `keep` and delete `drop`. Links, marriages,
    bonds and marks move across; blanks in `keep` are filled from `drop`. The dropped record's
    Gramps handle is remembered so a re-import maps it to `keep` instead of re-creating it."""
    k = con.execute("SELECT * FROM person WHERE id=?", (keep,)).fetchone()
    d = con.execute("SELECT * FROM person WHERE id=?", (drop,)).fetchone()
    if not k or not d or keep == drop:
        raise ValueError("merge needs two different existing people")
    k, d = dict(k), dict(d)
    note = "\n".join(x for x in (k["notes"], d["notes"],
                                 "Also recorded as %s." % d["name"] if d["name"] != k["name"] else "") if x)
    con.execute("UPDATE person SET birth=?, death=?, ko_name=?, notes=?, household_id=?, vault_note=? WHERE id=?",
                (_better_date(k["birth"], d["birth"]), _better_date(k["death"], d["death"]),
                 k["ko_name"] or d["ko_name"], note, k["household_id"] or d["household_id"],
                 k["vault_note"] or d["vault_note"], keep))
    for col in ("parent_id", "child_id"):
        con.execute("UPDATE OR IGNORE parent_child SET %s=? WHERE %s=?" % (col, col), (keep, drop))
        con.execute("DELETE FROM parent_child WHERE %s=?" % col, (drop,))
    con.execute("DELETE FROM parent_child WHERE parent_id=child_id")
    for col in ("a_id", "b_id"):
        con.execute("UPDATE union_ SET %s=? WHERE %s=?" % (col, col), (keep, drop))
    con.execute("DELETE FROM union_ WHERE a_id=b_id")
    con.execute("DELETE FROM union_ WHERE id NOT IN (SELECT MIN(id) FROM union_ "
                "GROUP BY MIN(a_id,b_id), MAX(a_id,b_id))")
    for table, cols in (("bond", ("from_id", "to_id")), ("mark", ("person_id", "toward_id")),
                        ("household", ("head_id",)), ("person", ("carried_by",))):
        for col in cols:
            con.execute("UPDATE %s SET %s=? WHERE %s=?" % (table, col, col), (keep, drop))
    for key in ("me", "clan_elder"):
        if get_setting(con, key) == drop:
            set_setting(con, key, keep)
    merged = get_setting(con, "merged", {})
    for h, target in list(merged.items()):          # earlier merges into the record now dropped
        if target == drop:
            merged[h] = keep
    if d["ext_id"]:
        merged[d["ext_id"]] = keep
    set_setting(con, "merged", merged)
    con.execute("DELETE FROM person WHERE id=?", (drop,))
    con.commit()


def delete_person(con, pid):
    con.execute("DELETE FROM parent_child WHERE parent_id=? OR child_id=?", (pid, pid))
    con.execute("DELETE FROM union_ WHERE a_id=? OR b_id=?", (pid, pid))
    con.execute("DELETE FROM bond WHERE from_id=? OR to_id=?", (pid, pid))
    con.execute("DELETE FROM mark WHERE person_id=? OR toward_id=?", (pid, pid))
    con.execute("UPDATE household SET head_id=NULL WHERE head_id=?", (pid,))
    con.execute("UPDATE person SET carried_by=NULL WHERE carried_by=?", (pid,))
    con.execute("DELETE FROM person WHERE id=?", (pid,))
    con.commit()
