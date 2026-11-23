#!/usr/bin/env python3
"""Import a Gramps family tree (its SQLite database) into this app.

Reads a temporary copy of the Gramps database, never the original.
Default is a dry run that only prints counts. --apply writes people, unions
and parent-child links; people already imported (same Gramps handle) are
updated rather than duplicated, so it is safe to run again after editing in Gramps.

  ./run.sh import-gramps                 # dry run, first tree found
  ./run.sh import-gramps --tree "Family Tree" --apply
"""
import argparse, glob, os, pickle, shutil, sqlite3, sys, tempfile
import db

GRAMPS_DIR = os.path.expanduser("~/.gramps/grampsdb")
BIRTH, DEATH, DIVORCE = 12, 13, 7
SEX = {0: "f", 1: "m"}
CHILD_KIND = {2: "adopted", 3: "step"}


def find_tree(name):
    found = []
    for d in sorted(glob.glob(os.path.join(GRAMPS_DIR, "*"))):
        f, n = os.path.join(d, "sqlite.db"), os.path.join(d, "name.txt")
        if os.path.exists(f):
            title = open(n).read().strip() if os.path.exists(n) else os.path.basename(d)
            found.append((title, f, os.path.getsize(f)))
    if name:
        found = [t for t in found if t[0].lower() == name.lower()]
    if not found:
        sys.exit("No Gramps tree found" + (" named %r" % name if name else ""))
    return max(found, key=lambda t: t[2]) if not name else found[0]


def date_text(d):
    """Gramps date tuple -> 'YYYY' or 'YYYY-MM-DD' ('' if unknown)."""
    try:
        day, month, year = d[3][0], d[3][1], d[3][2]
    except (TypeError, IndexError):
        return ""
    if not year:
        return ""
    return "%04d-%02d-%02d" % (year, month, day) if month and day else "%04d" % year


def read_tree(path):
    tmp = tempfile.mkdtemp(prefix="gramps-import-")
    try:
        copy = os.path.join(tmp, "g.db")
        shutil.copy(path, copy)
        g = sqlite3.connect(copy)
        events = {}
        for h, blob in g.execute("SELECT handle, blob_data FROM event"):
            e = pickle.loads(blob)
            events[h] = (e[2][0], date_text(e[3]))
        people = {}
        for h, given, sur, blob, gender in g.execute(
                "SELECT handle, given_name, surname, blob_data, gender FROM person"):
            p = pickle.loads(blob)
            birth = death = ""
            dead = False
            for ref in p[7]:
                kind, when = events.get(ref[3], (None, ""))
                if kind == BIRTH and not birth:
                    birth = when
                if kind == DEATH:
                    dead, death = True, death or when
            name = " ".join(x for x in ((given or "").strip(), (sur or "").strip()) if x) or "(unnamed)"
            if not dead and birth[:4].isdigit() and int(birth[:4]) < 1915:
                dead = True
            people[h] = {"name": name, "sex": SEX.get(gender, "u"), "birth": birth,
                         "death": death or ("?" if dead else ""), "ext_id": h}
        unions, links = [], []
        for h, blob, father, mother in g.execute(
                "SELECT handle, blob_data, father_handle, mother_handle FROM family"):
            f = pickle.loads(blob)
            if father and mother:
                divorced = any(events.get(r[3], (None,))[0] == DIVORCE for r in f[6])
                unions.append((father, mother, "divorced" if divorced else "married"))
            for ref in f[4]:
                child = ref[3]
                if father:
                    links.append((father, child, CHILD_KIND.get(ref[4][0], "birth")))
                if mother:
                    links.append((mother, child, CHILD_KIND.get(ref[5][0], "birth")))
        g.close()
        return people, unions, links
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tree", help="name of the Gramps tree (default: the largest)")
    ap.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    a = ap.parse_args(argv)
    title, path, _ = find_tree(a.tree)
    people, unions, links = read_tree(path)
    links = [l for l in links if l[0] in people and l[1] in people]
    unions = [u for u in unions if u[0] in people and u[1] in people]
    born = sorted(p["birth"][:4] for p in people.values() if p["birth"])
    print("Gramps tree %r: %d people (%d living), %d marriages, %d parent-child links, births %s-%s" % (
        title, len(people), sum(1 for p in people.values() if not p["death"]), len(unions), len(links),
        born[0] if born else "?", born[-1] if born else "?"))
    if not a.apply:
        print("Dry run: nothing written. Add --apply to import.")
        return
    con = db.connect()
    ids = {r["ext_id"]: r["id"] for r in db.rows(con, "SELECT id, ext_id FROM person WHERE ext_id != ''")}
    merged = {h: t for h, t in db.get_setting(con, "merged", {}).items() if t in ids.values()}
    new = 0
    for h, p in people.items():
        if h in merged:   # a duplicate already folded into another person here: map it, don't re-create it
            ids[h] = merged[h]
        elif h in ids:      # keep anything edited here; refresh only the facts Gramps owns,
            # and never let a blank in Gramps erase a birth or death entered in this app
            con.execute("UPDATE person SET name=?, sex=?, birth=COALESCE(NULLIF(?,''),birth), "
                        "death=COALESCE(NULLIF(?,''),death) WHERE id=?",
                        (p["name"], p["sex"], p["birth"], p["death"], ids[h]))
        else:
            ids[h] = con.execute("INSERT INTO person(name,sex,birth,death,ext_id) VALUES(?,?,?,?,?)",
                                 (p["name"], p["sex"], p["birth"], p["death"], h)).lastrowid
            new += 1
    have = {frozenset((r["a_id"], r["b_id"])) for r in db.rows(con, "SELECT a_id, b_id FROM union_")}
    for fa, mo, status in unions:
        if frozenset((ids[fa], ids[mo])) not in have:
            con.execute("INSERT INTO union_(a_id,b_id,status) VALUES(?,?,?)", (ids[fa], ids[mo], status))
            have.add(frozenset((ids[fa], ids[mo])))
    for par, ch, kind in links:
        con.execute("INSERT OR IGNORE INTO parent_child(parent_id,child_id,kind) VALUES(?,?,?)",
                    (ids[par], ids[ch], kind))
    con.commit()
    print("Imported: %d new people, %d already present (%d of them merged duplicates)." % (
        new, len(people) - new, sum(1 for h in people if h in merged)))


if __name__ == "__main__":
    main()
