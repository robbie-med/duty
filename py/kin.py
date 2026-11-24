"""Kinship engine. Given people, unions and parent-child links, derive what any
person is to any other: English relation, Korean term (호칭), generation
distance, degree (촌), and the role tags that duties attach to.

A relation is a path of steps from ego: P (to a parent), C (to a child),
S (to a spouse). "PPC" = parent's parent's child = uncle or aunt.
Two specials: X = former spouse, K = other parent of my child (never married).
"""
import heapq
import json
import os
import re
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "way", "kinterms.json"), encoding="utf-8") as _f:
    KO = json.load(_f)["terms"]
with open(os.path.join(ROOT, "way", "kinterms.zh.json"), encoding="utf-8") as _f:
    ZH = json.load(_f)["terms"]
with open(os.path.join(ROOT, "way", "kinterms.zh-hant.json"), encoding="utf-8") as _f:
    ZH_HANT = json.load(_f)["terms"]

MAX_STEPS = 8
AGED = 65                       # "aged": from this age the duties to the aged apply
THIS_YEAR = time.localtime().tm_year
_SHAPE = re.compile(r"^(S?)(P*)(C*)(S?)$")
_INV = {"P": "C", "C": "P", "S": "S", "X": "X", "K": "K", "Q": "Q"}


def invert(path):
    return "".join(_INV[c] for c in reversed(path))


class Graph:
    def __init__(self, people, unions, links, households=(), langs=("ko",)):
        self.people = people
        self.langs = tuple(langs)       # the family's own languages for terms of address: "ko", "zh"
        self.keepers = {h["id"]: h["head_id"] for h in households if h.get("head_id") in people}
        self.parents, self.children, self.spouses, self.exes, self.partners = {}, {}, {}, {}, {}
        self._alive, self._born = {}, {}
        self.kind = {}                  # (parent, child) -> birth / adopted / step
        for l in links:
            if l["parent_id"] in people and l["child_id"] in people:
                self.kind[(l["parent_id"], l["child_id"])] = l.get("kind") or "birth"
                self.parents.setdefault(l["child_id"], []).append(l["parent_id"])
                self.children.setdefault(l["parent_id"], []).append(l["child_id"])
        for u in unions:
            a, b = u["a_id"], u["b_id"]
            if a not in people or b not in people:
                continue
            tgt = (self.exes if u["status"] == "divorced" else
                   self.partners if u["status"] == "paramour" else self.spouses)
            tgt.setdefault(a, []).append(b)
            tgt.setdefault(b, []).append(a)

    # -- small facts ---------------------------------------------------
    def sex(self, pid):
        return self.people[pid].get("sex") or "u"

    def older(self, a, b):
        """True if a was born before b, None if unknown."""
        ba, bb = self.people[a].get("birth") or "", self.people[b].get("birth") or ""
        if ba and bb and ba[:len(bb)] != bb[:len(ba)]:
            return ba < bb
        oa, ob = self.people[a].get("birth_order"), self.people[b].get("birth_order")   # siblings without dates
        if oa and ob and oa != ob and set(self.parents.get(a, [])) & set(self.parents.get(b, [])):
            return oa < ob
        return None

    def born_about(self, pid, depth=3):
        """Birth year, or a rough guess from relatives when none is recorded (None if no clue)."""
        if depth == 3:
            if pid not in self._born:
                self._born[pid] = self._born_about(pid, 3)
            return self._born[pid]
        return self._born_about(pid, depth)

    def _born_about(self, pid, depth):
        b = (self.people[pid].get("birth") or "")[:4]
        if b.isdigit():
            return int(b)
        if depth == 0:
            return None
        guesses = []
        for rel, shift in ((self.parents, 30), (self.children, -30), (self.spouses, 0), (self.exes, 0)):
            for other in rel.get(pid, []):
                y = self.born_about(other, depth - 1)
                if y is not None:
                    guesses.append(y + shift)
        return sum(guesses) // len(guesses) if guesses else None

    def alive(self, pid):
        if pid not in self._alive:
            if self.people[pid].get("death"):
                self._alive[pid] = False
            else:                      # no death recorded: living unless born (or evidently born) long ago
                y = self.born_about(pid)
                self._alive[pid] = y is None or y >= 1915
        return self._alive[pid]

    def eldest_son(self, parent):
        sons = [c for c in self.children.get(parent, [])
                if self.sex(c) == "m" and self.alive(c) and self.people[c].get("birth")]
        return min(sons, key=lambda c: self.people[c]["birth"]) if sons else None

    # -- headship ------------------------------------------------------
    def _father(self, pid):
        """The father whose line he belongs to: an adoptive father before the father by birth."""
        men = [p for p in self.parents.get(pid, []) if self.sex(p) == "m"]
        return next((p for p in men if self.kind.get((p, pid)) == "adopted"), men[0] if men else None)

    def left_for_adoption(self, child, parent):
        """Adopted out: the child has adoptive parents and `parent` is not one of them.
        Still kin by birth, but out of that parent's house and line of succession."""
        return self.kind.get((parent, child)) != "adopted" and any(
            self.kind.get((q, child)) == "adopted" for q in self.parents.get(child, []))

    def _living_men(self, ids):
        return [i for i in ids if self.sex(i) == "m" and self.alive(i)]

    def _eldest(self, ids):
        return min(ids, key=lambda i: (self.people[i].get("birth") or "9999", i)) if ids else None

    def lineage_heir(self, base):
        """The heir of the main line (종손 宗子): from the founder of base's father's line, eldest son after eldest son
        down to the first living man. A son with no living man left below him passes it to his next brother.
        Sons adopted out leave the line; a son adopted in stands in it."""
        if base is None or base not in self.people:
            return None
        key = ("heir", base)
        if key in self._born:
            return self._born[key]
        root, seen = base, {base}
        while True:
            f = self._father(root)
            if f is None or f in seen:
                break
            seen.add(f); root = f

        def sons(p):
            s = [c for c in self.children.get(p, []) if self.sex(c) == "m" and not self.left_for_adoption(c, p)]
            return sorted(s, key=lambda c: (self.born_about(c) or 9999, self.people[c].get("birth_order") or 99, c))

        def walk(p, depth=0):
            if depth > 40:
                return None
            for son in sons(p):
                if self.alive(son):
                    return son
                h = walk(son, depth + 1)
                if h is not None:
                    return h
            return None
        heir = root if self.alive(root) else walk(root)
        self._born[key] = heir
        return heir

    def status_tags(self, pid, heir=None):
        """Roles a person holds by their own condition, whoever looks at them: departed, minor, fatherless,
        aged, widow or widower, heir of the main line."""
        if not self.alive(pid):
            return ["departed"]
        tags = []
        y = self.born_about(pid)
        age = THIS_YEAR - y if y else None
        if age is not None and age < 18:
            tags.append("minor")
            f = self._father(pid)
            if f is not None and not self.alive(f):
                tags.append("orphan")
        if age is not None and age >= AGED:
            tags.append("aged")
        sp = self.spouses.get(pid, [])
        if sp and not any(self.alive(x) for x in sp):
            tags.append({"f": "widow", "m": "widower"}.get(self.sex(pid)))
        if heir is not None and heir == pid:
            tags.append("lineage_heir")
        return [t for t in tags if t]

    def adult(self, pid):
        y = self.born_about(pid)
        return y is None or THIS_YEAR - y >= 18

    def holds(self, pid):
        """May act as a head: a living man who has not stepped down from or abandoned his headship."""
        return self.sex(pid) == "m" and self.alive(pid) and not self.people[pid].get("headship")

    def _by_age(self, ids):
        return sorted(ids, key=lambda i: (self.people[i].get("birth") or "9999", self.people[i].get("birth_order") or 99, i))

    def house_line(self, pid, depth=0):
        """Order of succession over this person's house: [(man, why)], first in right first.
        The first who still holds (living, not stepped down, not gone) is the acting head.
        A man with a wife or children heads his own house. A wife is under her husband. Then whoever
        keeps the household she lives in; a widow's grown sons, eldest first; the father; the
        mother's husband; for a child under 18, whoever heads the mother; the brothers (for a man,
        only those elder than he), eldest first; the father's father. Failing all, a man heads himself;
        a woman falls directly under the Head of the family."""
        if not self.alive(pid):
            return []
        out, seen = [], set()

        def add(i, why):
            if i is not None and i not in seen and self.sex(i) == "m" and self.alive(i):
                seen.add(i); out.append((i, why))
        male = self.sex(pid) == "m"
        if male and (self.spouses.get(pid) or self.children.get(pid)):
            add(pid, "heads his own house")
        if not male:
            for h in self._by_age(self.spouses.get(pid, [])):
                add(h, "her husband")
        keeper = self.keepers.get(self.people[pid].get("household_id"))
        if keeper != pid:
            add(keeper, "keeps the household %s lives in" % ("he" if male else "she"))
        if not male:
            for s in self._by_age(c for c in self.children.get(pid, [])
                                  if self.adult(c) and not self.left_for_adoption(c, pid)):
                add(s, "her son")
        father = self._father(pid)
        add(father, "father")
        for par in self.parents.get(pid, []):
            for s in self._by_age(self.spouses.get(par, [])):
                add(s, "mother's husband")
        if not self.adult(pid) and depth < 3:
            mother = next((p for p in self.parents.get(pid, []) if self.sex(p) == "f"), None)
            if mother:
                for i, why in self.house_line(mother, depth + 1):
                    add(i, "with the mother: " + why)
        sibs = self._by_age({c for par in self.parents.get(pid, []) for c in self.children.get(par, [])})
        for b in sibs[:sibs.index(pid)] if male and pid in sibs else sibs:
            if b != pid and self.adult(b) and not any(self.left_for_adoption(b, q) for q in self.parents.get(pid, [])
                                                       if q in self.parents.get(b, [])):
                add(b, "brother")
        if father:
            add(self._father(father), "father's father")
        if male and self.adult(pid):          # a boy under 18 with no man over him falls to the Head of the family
            add(pid, "heads himself")
        return out

    def house_heads(self, pid):
        """(head by right, acting head). Either may be None."""
        line = self.house_line(pid)
        acting = next((i for i, _ in line if self.holds(i)), None)
        return (line[0][0] if line else None), acting

    def bound(self, pid, paths=None):
        """For a house with no man left to act in its own line (headless): the man bound by
        kinship to act for it, as the nearer kinsman was in Lev 25:25, 48-49 and Ruth 3:12; 4:1-6.
        Kin are taken nearest first (fewest steps, blood before marriage, elder first). The first
        grown man who still holds is bound himself; for a kinswoman or child, the man acting at
        the head of her house. Returns (man, kinsman through whom, path) or (None, None, '')."""
        if not self.alive(pid) or self.house_heads(pid)[0] == pid:   # a man who left his own house is not put under another
            return None, None, ""
        paths = paths or self.paths_from(pid)
        kin = [k for k, (path, _) in paths.items()
               if k != pid and path not in ("X", "K", "Q") and self.alive(k)]
        tiers = {}
        for k in kin:                       # equally near: same number of steps and of marriages
            tiers.setdefault((len(paths[k][0]), paths[k][0].count("S")), []).append(k)
        age = lambda i: (self.born_about(i) or 9999, self.people[i].get("birth") or "9999", i)
        for t in sorted(tiers):
            found = []
            for k in tiers[t]:
                if self.holds(k) and self.adult(k):
                    found.append((k, k))
                else:
                    a = self.house_head(k)
                    if a is not None and a != pid and self.holds(a):
                        found.append((a, k))
            if found:                       # within the nearest tier, the eldest man is bound
                man, via = min(found, key=lambda f: (age(f[0]), f[0] != f[1], age(f[1])))
                return man, via, paths[via][0]
        return None, None, ""

    def house_head(self, pid):
        """The man who acts at the head of this person's house, or None (then the Head of the family)."""
        return self.house_heads(pid)[1]

    def line_top(self, pid):
        """First known ancestor up the father's line."""
        top, seen = pid, {pid}
        while True:
            f = self._father(top)
            if f is None or f in seen:
                return top
            top = f; seen.add(f)

    def main_line_head(self):
        """The Head when there is no one to trace from: the senior living man of the largest
        male line in the tree (then the next largest, and so on); failing all, the eldest living man."""
        lines = {}
        for pid in self.people:
            if self.sex(pid) == "m":
                lines.setdefault(self.line_top(pid), []).append(pid)
        for top, _ in sorted(lines.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            h = self.main_head(top)
            if h:
                return h
        return self._eldest([i for i in self.people if self.holds(i)])

    def line_succession(self, base):
        """Order of succession to the headship of base's father's line: every living man descended
        from its first known ancestor through men only, the oldest generation first, eldest first."""
        if base not in self.people:
            return []
        order, level, seen = [], [self.line_top(base)], set()
        while level:
            order += self._by_age(self._living_men(level))
            nxt = []
            for p in level:
                if p in seen or self.sex(p) != "m":
                    continue
                seen.add(p)
                nxt += [c for c in self.children.get(p, [])
                        if self.sex(c) == "m" and c not in seen and self._father(c) == p]
            level = nxt
        return order

    def main_head(self, base):
        """The Head of the family by rule: the first in the line's succession who still holds."""
        return next((m for m in self.line_succession(base) if self.holds(m)), None)

    # -- path finding --------------------------------------------------
    def paths_from(self, ego):
        """Shortest admissible path from ego to everyone reachable.
        Returns {pid: (path, chain_of_ids)}. Fewer steps wins, then fewer marriages."""
        best = {ego: ("", [ego])}
        seen = set()
        n = 0
        heap = [(0, 0, n, ego, "", [ego])]
        while heap:
            steps, sc, _, pid, path, chain = heapq.heappop(heap)
            last = path[-1:] if path else ""
            if (pid, last, sc) in seen:
                continue
            seen.add((pid, last, sc))
            best.setdefault(pid, (path, chain))
            if steps >= MAX_STEPS:
                continue
            moves = []
            if last != "C":                       # never child -> its other parent
                moves += [("P", p) for p in self.parents.get(pid, [])]
            moves += [("C", c) for c in self.children.get(pid, [])]
            if last != "S" and sc < 2:
                moves += [("S", s) for s in self.spouses.get(pid, [])]
            for step, nxt in moves:
                if nxt in chain:
                    continue
                n += 1
                heapq.heappush(heap, (steps + 1, sc + (step == "S"), n, nxt,
                                      path + step, chain + [nxt]))
        for x in self.exes.get(ego, []):
            best.setdefault(x, ("X", [ego, x]))
        for x in self.partners.get(ego, []):      # living together unmarried: shown, never a spouse
            best.setdefault(x, ("Q", [ego, x]))
        for c in self.children.get(ego, []):
            for other in self.parents.get(c, []):
                best.setdefault(other, ("K", [ego, other]))
        return best

    # -- describing a path ---------------------------------------------
    def describe(self, path, chain):
        """What chain[-1] is to chain[0]."""
        ego, tgt = chain[0], chain[-1]
        ts, es = self.sex(tgt), self.sex(ego)
        mf = lambda m, f, n: m if ts == "m" else f if ts == "f" else n
        gen = path.count("P") - path.count("C")
        rel = {"path": path, "gen": gen, "chon": None, "half": False}
        qual, kind, en = "", "kin", None

        def age_word(a, b):          # is a elder or younger than b
            o = self.older(a, b)
            return "" if o is None else ("elder" if o else "younger")

        m = _SHAPE.match(path)
        if path == "":
            kind, en = "self", "self"
        elif path == "X":
            kind, en = "ex_spouse", mf("former husband", "former wife", "former spouse")
        elif path == "Q":
            kind, en = "paramour", "paramour (living together, unmarried)"
        elif path == "K":
            kind, en = "co_parent", mf("father of my child", "mother of my child", "other parent of my child")
        elif path == "PSC":
            kind, en = "sibling", mf("stepbrother", "stepsister", "step-sibling")
            qual = age_word(tgt, ego)
        elif path == "CSP":
            kind, en = "co_parent_in_law", mf("child's father-in-law", "child's mother-in-law", "child's parent-in-law")
        elif m:
            s1, u, d, s2 = bool(m.group(1)), len(m.group(2)), len(m.group(3)), bool(m.group(4))
            base = 1 if s1 else 0
            origin = chain[base]                 # ego, or ego's spouse
            blood = chain[base + u + d]          # the blood relative on the path
            bs = self.sex(blood)
            side = ""
            if u >= 1:
                side = {"m": "pat", "f": "mat"}.get(self.sex(chain[base + 1]), "")
            if not s1 and not s2:
                rel["chon"] = u + d
            b_en, b_kind, b_qual = self._blood(u, d, blood, origin, chain, base, side)
            if (u, d) == (1, 1):
                pa, pb = set(self.parents.get(origin, [])), set(self.parents.get(blood, []))
                rel["half"] = len(pa) == 2 and len(pb) == 2 and len(pa & pb) == 1
                if rel["half"] and not s1 and not s2:
                    b_en = b_en.replace("brother", "half-brother").replace("sister", "half-sister")
            if not s1 and not s2:
                kind, en, qual = b_kind, b_en, b_qual
            elif s1 and not s2:
                whose = "wife's " if self.sex(chain[1]) == "f" else "husband's " if self.sex(chain[1]) == "m" else "spouse's "
                qual = b_qual
                if (u, d) == (0, 0):
                    kind, en = "spouse", mf("husband", "wife", "spouse")
                elif u == 0 and d == 1:
                    kind, en = "step_child", mf("stepson", "stepdaughter", "stepchild")
                elif (u, d) == (1, 0):
                    kind, en = "parent_in_law", mf("father-in-law", "mother-in-law", "parent-in-law")
                elif (u, d) == (1, 1):
                    kind, en = "sibling_in_law", mf("brother-in-law", "sister-in-law", "sibling-in-law") + " (%s%s)" % (whose, b_en)
                else:
                    kind = b_kind if b_kind in ("uncle_aunt", "nephew_niece", "grandparent", "cousin") else "kin"
                    en = whose + b_en
            elif s2 and not s1:
                qual = ".".join(x for x in (b_qual_for_spouse(side, bs, b_qual, u, d)) if x)
                if (u, d) == (1, 0):
                    kind, en = "step_parent", mf("stepfather", "stepmother", "step-parent")
                elif (u, d) == (0, 1):
                    kind, en = "child_in_law", mf("son-in-law", "daughter-in-law", "child-in-law")
                elif (u, d) == (1, 1):
                    kind, en = "sibling_in_law", mf("brother-in-law", "sister-in-law", "sibling-in-law") + " (%s's %s)" % (b_en, mf("husband", "wife", "spouse"))
                elif u >= 2 and d == 1:
                    kind, en = "uncle_aunt", mf("uncle", "aunt", "uncle/aunt") + " by marriage (%s's %s)" % (b_en, mf("husband", "wife", "spouse"))
                else:
                    kind = "nephew_niece" if b_kind == "nephew_niece" else "kin"
                    en = "%s's %s" % (b_en, mf("husband", "wife", "spouse"))
            else:
                whose = "wife's " if self.sex(chain[1]) == "f" else "husband's " if self.sex(chain[1]) == "m" else "spouse's "
                qual = bs if bs in "mf" else ""
                kind = "sibling_in_law" if (u, d) == (1, 1) else "kin"
                en = "%s%s's %s" % (whose, b_en, mf("husband", "wife", "spouse"))
                if (u, d) == (1, 1):
                    en = mf("brother-in-law", "sister-in-law", "sibling-in-law") + " (%s)" % en
        else:
            en = "relative by marriage"

        rel["kind"], rel["en"], rel["qual"] = kind, en, qual
        rel["ko_term"] = self._ko(path, es, ts, qual, rel["chon"])
        zq = self._zh_qual(path, qual, chain)
        rel["zh"], rel["zh_hant"] = self._lookup(ZH, path, es, ts, zq), self._lookup(ZH_HANT, path, es, ts, zq)
        # "ko" is what the page shows beside the English: the terms in the family's own languages (none for an Anglo family)
        rel["ko"] = " · ".join(t for t in ([rel["ko_term"]] if "ko" in self.langs else []) + ([rel["zh"]] if "zh" in self.langs else []) if t)
        rel["tags"] = self._tags(kind, ts, qual, gen, ego, tgt, via_spouse=path[:1] == "S" and path[-1:] != "S")
        return rel

    def _blood(self, u, d, blood, origin, chain, base, side):
        """English name, kind and qualifier for a blood relative u up, d down from origin."""
        bs = self.sex(blood)
        mf = lambda m, f, n: m if bs == "m" else f if bs == "f" else n
        if (u, d) == (0, 0):
            return "self", "self", ""
        if d == 0:
            if u == 1:
                return mf("father", "mother", "parent"), "parent", ""
            return "great-" * (u - 2) + "grand" + mf("father", "mother", "parent"), "grandparent", side
        if u == 0:
            if d == 1:
                return mf("son", "daughter", "child"), "child", ""
            via = {"m": "son", "f": "dau"}.get(self.sex(chain[base + 1]), "")
            return "great-" * (d - 2) + "grand" + mf("son", "daughter", "child"), "grandchild", via
        if (u, d) == (1, 1):
            o = self.older(blood, origin)
            age = "" if o is None else ("elder" if o else "younger")
            return (age + " " if age else "") + mf("brother", "sister", "sibling"), "sibling", age
        if d == 1:
            parent_link = chain[base + u - 1]     # origin's ancestor whose sibling this is
            o = self.older(blood, parent_link)
            age = "" if o is None else ("elder" if o else "younger")
            q = ".".join(x for x in (side, age) if x)
            return "great-" * (u - 2) + mf("uncle", "aunt", "uncle/aunt"), "uncle_aunt", q
        if u == 1:
            return "great-" * (d - 2) + mf("nephew", "niece", "nephew/niece"), "nephew_niece", ""
        deg, rem = min(u, d) - 1, abs(u - d)
        name = {1: "", 2: "second ", 3: "third "}.get(deg, "%dth " % deg) + "cousin"
        if rem:
            name += {1: " once", 2: " twice"}.get(rem, " %d times" % rem) + " removed"
        link = self.sex(chain[base + u + 1])      # the ancestor's child on the far side
        q = ".".join(x for x in (side, link if link in "mf" else "") if x)
        return name, "cousin", q

    def _zh_qual(self, path, qual, chain):
        """Chinese also names a nephew by the linking brother or sister (侄 / 外甥), and a cousin as elder or younger."""
        if path in ("PCC", "PCCS", "PCCC") and len(chain) > 2:
            return self.sex(chain[2]) if self.sex(chain[2]) in "mf" else ""
        if path.endswith("PPCC") and len(path) in (4, 5):
            o = self.older(chain[-1], chain[0] if path == "PPCC" else chain[1])
            return qual + ("" if o is None else ".elder" if o else ".younger")
        return qual

    @staticmethod
    def _lookup(table, path, es, ts, qual):
        parts = qual.split(".") if qual else []
        for i in range(len(parts), -1, -1):
            q = ".".join(parts[:i])
            for e in (es, "*"):
                for t in (ts, "*"):
                    v = table.get("%s|%s|%s|%s" % (path, e, t, q))
                    if v:
                        return v
        return ""

    def _ko(self, path, es, ts, qual, chon):
        quals = []
        parts = qual.split(".") if qual else []
        for i in range(len(parts), -1, -1):
            quals.append(".".join(parts[:i]))
        for q in quals:
            for e in (es, "*"):
                for t in (ts, "*"):
                    v = KO.get("%s|%s|%s|%s" % (path, e, t, q))
                    if v:
                        return v
        if chon:
            return "%d촌" % chon
        return ""

    def _tags(self, kind, ts, qual, gen, ego, tgt, via_spouse=False):
        mf = lambda m, f: [m] if ts == "m" else [f] if ts == "f" else []
        t = []
        if kind == "parent":
            t = mf("father", "mother") + ["parent"]
        elif kind == "child":
            t = mf("son", "daughter") + ["child"]
            if self.eldest_son(ego) == tgt:
                t.append("eldest_son")
        elif kind == "spouse":
            t = mf("husband", "wife") + ["spouse"]
        elif kind == "sibling":
            age = qual.split(".")[-1] if qual else ""
            t = ([age + "_sibling"] if age in ("elder", "younger") else []) + ["sibling"]
        elif kind == "child_in_law":
            t = mf("son_in_law", "daughter_in_law") + ["child_in_law"]
        elif kind == "sibling_in_law":
            r = self._in_law_rank(ego, tgt, qual, via_spouse)
            t = ([r + "_sibling_in_law"] if r else []) + ["sibling_in_law"]
        elif kind not in ("self", "kin"):
            t = [kind]
        if kind not in ("self", "spouse", "ex_spouse", "co_parent", "paramour"):
            t.append("superior" if gen > 0 else "inferior" if gen < 0 else "equal")
        if kind != "self":
            t.append("kin")
        return t

    def _in_law_rank(self, ego, tgt, qual, via_spouse):
        """Seniority between in-laws of one generation, as the Sangbyeon Tonggo (常變通攷, 妻齒爲坐之非) records it:
        men linked by a marriage rank by their own ages, never by a wife's or sister's ("安得挾妻年，居長我之叔獻上乎");
        a woman takes her husband's rank ("女坐以夫之齒"), so a brother's wife or a husband's sibling ranks through that marriage.
        Between a man and a woman with no husband to rank her by ("男女異長"), none."""
        se, st = self.sex(ego), self.sex(tgt)
        if se == "m" and st == "m":
            a, b = self.born_about(ego), self.born_about(tgt)
            return "" if not a or not b or a == b else "elder" if b < a else "younger"
        if st == "f" and se == "m" or se == "f":   # brother's wife (through my brother) / husband's sibling (through my husband)
            age = qual.split(".")[-1] if qual else ""
            via_husband = se == "f" and via_spouse or st == "f" and not via_spouse
            return age if via_husband and age in ("elder", "younger") else ""
        return ""

    # -- public --------------------------------------------------------
    def relations(self, ego):
        """{pid: {'them': what they are to ego, 'me': what ego is to them}}"""
        out = {}
        for pid, (path, chain) in self.paths_from(ego).items():
            if pid == ego:
                continue
            out[pid] = {"them": self.describe(path, chain),
                        "me": self.describe(invert(path), chain[::-1])}
        return out

    def relation(self, a, b):
        return self.relations(a).get(b)


def b_qual_for_spouse(side, blood_sex, b_qual, u, d):
    """Qualifier for 'spouse of a blood relative': side, sex of the blood link, elder/younger."""
    age = b_qual.split(".")[-1] if b_qual and b_qual.split(".")[-1] in ("elder", "younger") else ""
    if u >= 2:
        return (side, blood_sex if blood_sex in "mf" else "", age)
    return (blood_sex if blood_sex in "mf" else "", age)


def standing_roles(pid, graph, family_head):
    """Roles a person holds toward a collective rather than toward one person."""
    roles = ["member"] + graph.status_tags(pid, graph.lineage_heir(family_head))
    if graph.alive(pid):                # a wife or husband, and a son or daughter, owe their own house as such
        if any(graph.alive(x) for x in graph.spouses.get(pid, [])):
            roles += {"m": ["husband"], "f": ["wife"]}.get(graph.sex(pid), [])
        if any(graph.alive(x) for x in graph.parents.get(pid, [])):
            roles.append("child")
    if pid in graph.house_heads(pid):   # by right or acting: one who walks away still owes it
        roles.append("household_head")
    if family_head == pid:
        roles.append("clan_elder")
    return roles


def duties_between(duties, my_tags, their_tags):
    """Duties I owe them: I hold the 'from' role toward them, they hold the 'to' role toward me.
    Toward the dead only the duties written for the departed apply (a dead father is buried, mourned and
    remembered, not obeyed or provided for), and the dead owe nothing."""
    if "departed" in my_tags:
        return []
    dead = "departed" in their_tags
    return [d for d in duties if d["status"] != "retired"
            and d["from_role"] in my_tags and d["to_role"] in their_tags and (d["to_role"] == "departed") == dead]


COLLECTIVE = ("household", "clan", "outside")     # owed to a body of people, not to one person


def collective_duties(duties, roles):
    """Duties a person owes the household, the clan, or those outside the family, by the roles he holds himself."""
    return [d for d in duties if d["status"] != "retired" and d["to_role"] in COLLECTIVE and d["from_role"] in roles]
