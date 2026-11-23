"""Fixture clan: three generations, in-laws, remarriage, step and half kin."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kin

P = {}
def person(i, name, sex, birth, death=""):
    P[i] = {"id": i, "name": name, "sex": sex, "birth": birth, "death": death}

# generation 1
person(1, "Grandfather", "m", "1930"); person(2, "Grandmother", "f", "1932")
person(3, "MatGrandfather", "m", "1931"); person(4, "MatGrandmother", "f", "1933")
# generation 2
person(10, "Father", "m", "1955"); person(11, "Mother", "f", "1957")
person(12, "BigUncle", "m", "1952"); person(13, "BigUncleWife", "f", "1953")
person(14, "LittleUncle", "m", "1960"); person(15, "PatAunt", "f", "1958"); person(16, "PatAuntHusband", "m", "1956")
person(17, "MatUncle", "m", "1959"); person(18, "MatAunt", "f", "1961")
# generation 3
person(20, "Ego", "m", "1985"); person(21, "Wife", "f", "1987")
person(22, "ElderBrother", "m", "1982"); person(23, "ElderBrotherWife", "f", "1983")
person(24, "YoungerSister", "f", "1990"); person(25, "YoungerSisterHusband", "m", "1988")
person(26, "CousinViaBigUncle", "m", "1980"); person(27, "CousinViaPatAunt", "f", "1986")
person(28, "CousinViaMatAunt", "f", "1991")
person(30, "WifeFather", "m", "1958"); person(31, "WifeMother", "f", "1960")
person(32, "WifeElderBrother", "m", "1984"); person(33, "WifeYoungerSister", "f", "1992")
person(34, "WifeSisterHusband", "m", "1990")
person(35, "ExWife", "f", "1986"); person(36, "FatherSecondWife", "f", "1965")
person(37, "HalfBrother", "m", "1998"); person(38, "StepSister", "f", "1989")
# generation 4
person(40, "Son", "m", "2012"); person(41, "Daughter", "f", "2015"); person(42, "YoungerSon", "m", "2018")
person(43, "Nephew", "m", "2010"); person(44, "SonOfFirstMarriage", "m", "2008")
person(45, "WifeDaughterBefore", "f", "2009")

def kids(parents, children):
    return [{"parent_id": p, "child_id": c} for p in parents for c in children]

L = (kids([1, 2], [10, 12, 14, 15]) + kids([3, 4], [11, 17, 18]) + kids([10, 11], [20, 22, 24])
     + kids([12, 13], [26]) + kids([15, 16], [27]) + kids([18], [28])
     + kids([30, 31], [21, 32, 33]) + kids([20, 21], [40, 41, 42]) + kids([22, 23], [43])
     + kids([20, 35], [44]) + kids([21], [45]) + kids([10, 36], [37]) + kids([36], [38]))
def u(a, b, status="married"):
    return {"a_id": a, "b_id": b, "status": status}
U = [u(1, 2), u(3, 4), u(10, 11, "widowed"), u(10, 36), u(12, 13), u(15, 16), u(20, 21), u(22, 23),
     u(24, 25), u(30, 31), u(33, 34), u(20, 35, "divorced")]

G = kin.Graph(P, U, L)
R = G.relations(20)
WR = G.relations(21)


class Kin(unittest.TestCase):
    def check(self, rels, pid, en, ko, gen=None):
        r = rels[pid]["them"]
        self.assertEqual((r["en"].split(" (")[0], r["ko"]), (en, ko), P[pid]["name"] + " via " + r["path"])
        if gen is not None:
            self.assertEqual(r["gen"], gen)

    def test_direct_line(self):
        self.check(R, 10, "father", "아버지", 1)
        self.check(R, 11, "mother", "어머니", 1)
        self.check(R, 1, "grandfather", "할아버지", 2)
        self.check(R, 4, "grandmother", "외할머니", 2)
        self.check(R, 40, "son", "아들", -1)
        self.check(R, 41, "daughter", "딸", -1)
        self.check(R, 21, "wife", "아내", 0)
        self.check(WR, 20, "husband", "남편", 0)

    def test_siblings(self):
        self.check(R, 22, "elder brother", "형", 0)
        self.check(R, 24, "younger sister", "여동생", 0)
        self.check(G.relations(24), 20, "elder brother", "오빠")
        self.check(G.relations(24), 22, "elder brother", "오빠")
        self.check(R, 37, "younger half-brother", "남동생")
        self.check(R, 38, "stepsister", "의붓자매")

    def test_uncles_cousins(self):
        self.check(R, 12, "uncle", "큰아버지", 1)
        self.check(R, 14, "uncle", "작은아버지")
        self.check(R, 15, "aunt", "고모")
        self.check(R, 17, "uncle", "외삼촌")
        self.check(R, 18, "aunt", "이모")
        self.check(R, 13, "aunt by marriage", "큰어머니")
        self.check(R, 16, "uncle by marriage", "고모부")
        self.check(R, 26, "cousin", "사촌", 0)
        self.check(R, 27, "cousin", "고종사촌")
        self.check(R, 28, "cousin", "이종사촌")
        self.assertEqual(R[26]["them"]["chon"], 4)
        self.check(R, 43, "nephew", "조카", -1)
        self.check(G.relations(43), 20, "uncle", "작은아버지")

    def test_in_laws(self):
        self.check(R, 30, "father-in-law", "장인", 1)
        self.check(R, 31, "mother-in-law", "장모")
        self.check(WR, 10, "father-in-law", "시아버지")
        self.check(WR, 11, "mother-in-law", "시어머니")
        self.check(R, 32, "brother-in-law", "처남 (형님)")
        self.check(R, 33, "sister-in-law", "처제")
        self.check(R, 34, "brother-in-law", "동서")
        self.check(R, 23, "sister-in-law", "형수")
        self.check(R, 25, "brother-in-law", "매제")
        self.check(WR, 22, "brother-in-law", "아주버님")
        self.check(WR, 24, "sister-in-law", "아가씨")
        self.check(G.relations(10), 21, "daughter-in-law", "며느리", -1)
        self.check(G.relations(30), 20, "son-in-law", "사위")
        self.check(G.relations(10), 30, "child's father-in-law", "사돈")

    def test_step_and_former(self):
        self.check(R, 36, "stepmother", "새어머니")
        self.check(R, 45, "stepdaughter", "의붓딸")
        self.check(R, 35, "former wife", "전처")
        self.check(R, 44, "son", "아들")

    def test_tags_both_ways(self):
        r = R[10]
        self.assertIn("father", r["them"]["tags"]); self.assertIn("superior", r["them"]["tags"])
        self.assertIn("son", r["me"]["tags"]); self.assertIn("inferior", r["me"]["tags"])
        self.assertIn("eldest_son", G.relations(10)[22]["them"]["tags"])
        self.assertNotIn("eldest_son", r["me"]["tags"])
        self.assertIn("eldest_son", R[44]["them"]["tags"])       # eldest living son of Ego
        self.assertIn("husband", R[21]["me"]["tags"]); self.assertIn("wife", R[21]["them"]["tags"])
        self.assertIn("elder_sibling", R[22]["them"]["tags"]); self.assertIn("younger_sibling", R[22]["me"]["tags"])
        self.assertIn("daughter_in_law", G.relations(10)[21]["them"]["tags"])
        self.assertIn("parent_in_law", G.relations(10)[21]["me"]["tags"])
        self.assertIn("equal", R[26]["them"]["tags"])

    def test_symmetry(self):
        """What A is to B, seen from B, matches what B's own search finds."""
        for a in (20, 21, 10, 43):
            ra = G.relations(a)
            for b, r in ra.items():
                back = G.relations(b).get(a)
                self.assertIsNotNone(back, "%s cannot see %s" % (P[b]["name"], P[a]["name"]))
                self.assertEqual(r["me"]["kind"], back["them"]["kind"],
                                 "%s<->%s %s vs %s" % (P[a]["name"], P[b]["name"], r["me"]["path"], back["them"]["path"]))

    def test_duties(self):
        duties = [{"id": 1, "from_role": "child", "to_role": "parent", "status": "draft"},
                  {"id": 2, "from_role": "husband", "to_role": "wife", "status": "confirmed"},
                  {"id": 3, "from_role": "child", "to_role": "parent", "status": "retired"}]
        r = R[10]
        self.assertEqual([d["id"] for d in kin.duties_between(duties, r["me"]["tags"], r["them"]["tags"])], [1])
        self.assertEqual(kin.duties_between(duties, r["them"]["tags"], r["me"]["tags"]), [])
        r = R[21]
        self.assertEqual([d["id"] for d in kin.duties_between(duties, r["me"]["tags"], r["them"]["tags"])], [2])


class Headship(unittest.TestCase):
    def test_house_heads(self):
        h = G.house_head
        self.assertEqual(h(20), 20)            # married man heads his own house
        self.assertEqual(h(21), 20)            # wife under her husband
        self.assertEqual(h(40), 20); self.assertEqual(h(41), 20)   # children under their father
        self.assertEqual(h(45), 20)            # wife's daughter under her mother's husband
        self.assertEqual(h(14), 1)             # unmarried son under his living father
        self.assertEqual(h(2), 1)
        self.assertEqual(h(28), None if not G.alive(18) else h(28))
        self.assertEqual(h(18), 3)             # unmarried mother, father living: under her father
        for pid in P:                          # a head is always a living man
            x = h(pid)
            if x is not None:
                self.assertEqual(G.sex(x), "m"); self.assertTrue(G.alive(x))

    def test_widow_and_orphans(self):
        people = {i: dict(p) for i, p in P.items()}
        people[20]["death"] = "2024"
        g = kin.Graph(people, U, L)
        self.assertEqual(g.house_head(21), 30)  # widow whose sons are all under 18: under her own father
        self.assertEqual(g.house_head(41), 30)  # a fatherless child under 18 goes with her mother
        self.assertEqual(g.house_head(42), 30)
        self.assertEqual(g.house_head(44), 10)  # grown and unmarried, father dead, no elder brother: his father's father
        people[40]["birth"] = "2000"
        g = kin.Graph(people, U, L)
        self.assertEqual(g.house_head(21), 40)  # widow with a grown son: under him

    def test_abandoned_and_household(self):
        people = {i: dict(p) for i, p in P.items()}
        people[20]["headship"] = "abandoned"
        g = kin.Graph(people, U, L)
        self.assertEqual(g.house_heads(21), (20, 30))   # by right her husband; acting, her father
        self.assertEqual(g.house_heads(40), (20, 30))   # the children go with their mother
        self.assertIn("household_head", kin.standing_roles(20, g, None))   # he still owes what he left
        people[2]["household_id"] = 7                   # grandmother lives in her grandson's household
        g = kin.Graph(people, U, L, [{"id": 7, "head_id": 20}])
        self.assertEqual(g.house_heads(2), (1, 1))      # her husband still comes first
        people[1]["death"] = "2020"
        g = kin.Graph(people, U, L, [{"id": 7, "head_id": 14}])
        self.assertEqual(g.house_head(2), 14)           # widowed, she is under the man whose household she lives in
        self.assertEqual(g.line_succession(20)[:2], [12, 10] if P[12]["birth"] < P[10]["birth"] else [10, 12])

    def test_main_head(self):
        for base in (20, 21, 40, 43, 26, 37):
            if base == 21:
                self.assertEqual(G.main_head(base), 30)       # her own father's line
            else:
                self.assertEqual(G.main_head(base), 1)        # Grandfather, 1930, living
        people = {i: dict(p) for i, p in P.items()}
        people[1]["death"] = "2020"
        g = kin.Graph(people, U, L)
        self.assertEqual(g.main_head(40), 12)   # eldest living man of the next generation (BigUncle, 1952)
        for i in (12, 10, 14):
            people[i]["death"] = "2022"
        g = kin.Graph(people, U, L)
        self.assertEqual(g.main_head(40), 26)   # then the eldest of the generation after (1980)

    def test_bound_by_kinship(self):
        """A headless house: the man acting for the nearest kin is bound to act for it."""
        people = {i: dict(p) for i, p in P.items()}
        people[20]["headship"] = "abandoned"
        people[30]["death"] = people[32]["death"] = "2020"
        g = kin.Graph(people, U, L)
        self.assertEqual(g.house_heads(21), (20, None))      # her own line has no man left who acts
        self.assertEqual(g.bound(21), (44, 40, "C"))         # her son's acting head: his grown half-brother
        self.assertEqual(g.bound(20), (None, None, ""))      # the man who left is not put under another

    def test_one_head_for_everyone(self):
        """With no 'me' set, every page must show the same Head, never none."""
        import db, server
        con = db.connect(":memory:")
        for i, p in P.items():
            con.execute("INSERT INTO person(id,name,sex,birth,death) VALUES(?,?,?,?,?)",
                        (i, p["name"], p["sex"], p.get("birth", ""), p.get("death", "")))
        for u in U:
            con.execute("INSERT INTO union_(a_id,b_id,status) VALUES(?,?,?)", (u["a_id"], u["b_id"], u["status"]))
        for l in L:
            con.execute("INSERT INTO parent_child(parent_id,child_id) VALUES(?,?)", (l["parent_id"], l["child_id"]))
        heads = {server.api_ego(con, {}, pid)["head"] for pid in P}
        self.assertEqual(heads, {server.api_state(con, {})["head"]})
        self.assertIsNotNone(heads.pop())
        woman = next(i for i in P if P[i]["sex"] == "f")
        for bad in (lambda: server.write(con, "POST", ["household"], {"name": "x", "head_id": woman}, {}),
                    lambda: server.write(con, "PUT", ["setting"], {"key": "clan_elder", "value": woman}, {}),
                    lambda: server.write(con, "PUT", ["person", "1"], {"sex": "x"}, {}),
                    lambda: server.write(con, "POST", ["duty"], {"from_role": "fathr", "to_role": "son",
                                         "sphere": "worship", "tradition": "scripture", "text": "t"}, {})):
            self.assertRaises(server.Bad, bad)

    def test_merge_duplicate(self):
        import db
        con = db.connect(":memory:")
        for i, n, b, ext in ((1, "Harry", "1891", "h1"), (2, "Amerigo Harry", "1891-03-27", "h2"),
                             (3, "Louise", "", ""), (4, "Norman", "", ""), (5, "Melvin", "", "")):
            con.execute("INSERT INTO person(id,name,sex,birth,ext_id) VALUES(?,?,?,?,?)", (i, n, "m", b, ext))
        con.executemany("INSERT INTO parent_child(parent_id,child_id) VALUES(?,?)", ((1, 4), (2, 4), (2, 5)))
        con.executemany("INSERT INTO union_(a_id,b_id) VALUES(?,?)", ((1, 3), (3, 2)))
        db.merge_people(con, 2, 1)
        self.assertEqual(sorted(db.rows(con, "SELECT parent_id, child_id FROM parent_child"), key=str),
                         [{"parent_id": 2, "child_id": 4}, {"parent_id": 2, "child_id": 5}])
        self.assertEqual(con.execute("SELECT COUNT(*) FROM union_").fetchone()[0], 1)
        self.assertEqual(db.get_setting(con, "merged"), {"h1": 2})
        self.assertEqual(db.rows(con, "SELECT birth FROM person WHERE id=2")[0]["birth"], "1891-03-27")


if __name__ == "__main__":
    unittest.main()
