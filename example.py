#!/usr/bin/env python3
"""The example families: one fictional family for each background the app knows.

  anglo · korean · chinese · korean_anglo · korean_chinese · anglo_chinese

In each, a man of about thirty-five stands at the center. His father's line and his mother's line are each traced
eight generations back in full, his wife's family three generations back; his father's line, his mother's line and
his wife's line each take the names of their own people (an Anglo-American, Korean or Chinese line). Around them:
brothers and sisters with their children, uncles, aunts and cousins, and the situations the app is built to handle:
a Head of the family by rule, a main-line heir, widows, a house left headless and kept by a bound kinsman, a man who
has abandoned his family, an adoption, a divorce, one drifting away, minors with and without a guardian named, and a
few gaps in the record. Every name is invented.

  python3 example.py [path/to/family.db] [--background korean_anglo] [--reset]
(the server builds each example by itself the first time it is shown)
"""
import json
import os
import random
import sys
import time

ANGLO_M = ["John", "William", "James", "Thomas", "George", "Henry", "Charles", "Samuel", "Joseph", "Edward", "Robert",
           "Benjamin", "Daniel", "David", "Isaac", "Nathaniel", "Jacob", "Elijah", "Andrew", "Peter", "Walter", "Frederick"]
ANGLO_F = ["Mary", "Elizabeth", "Sarah", "Anna", "Margaret", "Martha", "Hannah", "Susanna", "Catherine", "Rebecca",
           "Abigail", "Ruth", "Lydia", "Esther", "Rachel", "Eleanor", "Clara", "Alice", "Emma", "Frances", "Edith", "Grace"]
ANGLO_SUR = ["Ellis", "Morgan", "Hale", "Carter", "Bennett", "Foster", "Hayes", "Wright", "Brooks", "Porter", "Sutton",
             "Reed", "Lawson", "Fletcher", "Barton", "Cole", "Mercer", "Dunn", "Walsh", "Holloway", "Parker", "Shaw",
             "Prescott", "Whitfield", "Garrett", "Ashby", "Thornton", "Pierce", "Vaughn", "Crane", "Lowell", "Draper"]
KO_SUR = [("Han", "한"), ("Kim", "김"), ("Lee", "이"), ("Park", "박"), ("Choi", "최"), ("Jung", "정"), ("Kang", "강"),
          ("Cho", "조"), ("Yoon", "윤"), ("Jang", "장"), ("Lim", "임"), ("Shin", "신"), ("Oh", "오"), ("Seo", "서"),
          ("Kwon", "권"), ("Hwang", "황"), ("Song", "송"), ("Ahn", "안"), ("Hong", "홍"), ("Yoo", "유")]
KO_GIVEN_M = [("jeong", "정"), ("su", "수"), ("ho", "호"), ("seong", "성"), ("jae", "재"), ("dong", "동"), ("hwan", "환"),
              ("chul", "철"), ("sang", "상"), ("woo", "우"), ("jin", "진"), ("tae", "태"), ("kwang", "광"), ("gyu", "규"),
              ("min", "민"), ("hyun", "현"), ("il", "일"), ("man", "만"), ("deok", "덕"), ("nam", "남")]
KO_GIVEN_F = [("soon", "순"), ("ja", "자"), ("hee", "희"), ("ok", "옥"), ("sook", "숙"), ("mi", "미"), ("kyung", "경"),
              ("eun", "은"), ("young", "영"), ("hye", "혜"), ("yeon", "연"), ("bok", "복"), ("ji", "지"), ("ae", "애"),
              ("rye", "례"), ("nyeo", "녀"), ("im", "임"), ("sun", "선"), ("hwa", "화"), ("jeong", "정")]
ZH_SUR = [("Lin", "林"), ("Chen", "陈"), ("Wang", "王"), ("Li", "李"), ("Zhang", "张"), ("Liu", "刘"), ("Huang", "黄"),
          ("Zhou", "周"), ("Wu", "吴"), ("Xu", "徐"), ("Sun", "孙"), ("Ma", "马"), ("Zhu", "朱"), ("Hu", "胡"), ("Guo", "郭"),
          ("He", "何"), ("Gao", "高"), ("Luo", "罗"), ("Zheng", "郑"), ("Liang", "梁")]
ZH_GIVEN_M = [("jian", "建"), ("guo", "国"), ("wei", "伟"), ("ming", "明"), ("zhi", "志"), ("qiang", "强"), ("hua", "华"),
              ("jun", "军"), ("dong", "东"), ("wen", "文"), ("de", "德"), ("cheng", "成"), ("hai", "海"), ("shan", "山"),
              ("rong", "荣"), ("bin", "斌"), ("tao", "涛"), ("yong", "勇"), ("xiang", "祥"), ("fu", "福")]
ZH_GIVEN_F = [("mei", "梅"), ("li", "丽"), ("hua", "华"), ("fang", "芳"), ("ying", "英"), ("lan", "兰"), ("xiu", "秀"),
              ("zhen", "珍"), ("yu", "玉"), ("hong", "红"), ("jing", "静"), ("min", "敏"), ("qing", "清"), ("yan", "燕"),
              ("feng", "凤"), ("juan", "娟"), ("xia", "霞"), ("hui", "慧"), ("lian", "莲"), ("zhu", "珠")]
GRAVES = {"A": ["Old Stone Church cemetery, Lancaster County, Pa.", "Hillside Cemetery, Elmira, N.Y.",
                "First Presbyterian churchyard, Carlisle, Pa.", "Riverside Cemetery, Marion, Ohio", "Greenwood Cemetery, Wheeling, W.Va."],
          "K": ["선산 (the family hill), Andong", "선산 (the family hill), Yecheon", "public cemetery, Daegu", "선산, Uiseong"],
          "C": ["祖坟 (the family graves), Jinjiang, Fujian", "祖坟, Taishan, Guangdong", "public cemetery, Quanzhou", "祖坟, Nan'an, Fujian"]}

# Each background: the culture of the center man's father's line, his mother's line, and his wife's line.
LINES = {"anglo": "AAA", "korean": "KKK", "chinese": "CCC", "korean_anglo": "AKA", "korean_chinese": "KCK", "anglo_chinese": "ACA"}
FAMILY = {"A": ("Whitaker", ""), "K": ("Kim", "김"), "C": ("Lin", "林")}           # the center man's surname, by his father's line
MOTHERS = {"A": ("Ellis", ""), "K": ("Han", "한"), "C": ("Chen", "陈")}           # his mother's family
WIVES = {"A": ("Turner", ""), "K": ("Lee", "이"), "C": ("Wang", "王")}            # his wife's family


class Builder:
    def __init__(self, con, seed):
        self.con, self.r = con, random.Random(seed)

    def person(self, nm, sex, birth="", death="", **more):
        name, native = nm
        cols = dict(name=name, sex=sex, birth=str(birth or ""), death=str(death or ""), ko_name=native, **more)
        cur = self.con.execute("INSERT INTO person(%s) VALUES(%s)" % (",".join(cols), ",".join("?" * len(cols))), list(cols.values()))
        return cur.lastrowid

    def marry(self, a, b, status="married"):
        self.con.execute("INSERT INTO union_(a_id,b_id,status) VALUES(?,?,?)", (a, b, status))

    def child(self, c, *parents, kind="birth"):
        for p in parents:
            self.con.execute("INSERT OR REPLACE INTO parent_child(parent_id,child_id,kind) VALUES(?,?,?)", (p, c, kind))

    def couple(self, husband, wife, *children):
        self.marry(husband, wife)
        for c in children:
            self.child(c, husband, wife)

    # -- names: (name in Latin letters, name in hangul or Chinese characters) ---------------------------
    def name(self, culture, sex, surname, given=None):
        sur, native_sur = surname if isinstance(surname, tuple) else (surname, "")
        if culture == "A":       # the center man and his father keep their names to themselves
            return "%s %s" % (given or self.r.choice([x for x in ANGLO_M if x not in ("Daniel", "James")] if sex == "m" else ANGLO_F), sur), ""
        pool = {("K", "m"): KO_GIVEN_M, ("K", "f"): KO_GIVEN_F, ("C", "m"): ZH_GIVEN_M, ("C", "f"): ZH_GIVEN_F}[(culture, sex)]
        a, b = given or self.r.sample(pool, 2)
        if culture == "K":
            return "%s %s-%s" % (sur, a[0].capitalize(), b[0]), native_sur + a[1] + b[1]
        return "%s %s%s" % (sur, a[0].capitalize(), b[0]), native_sur + a[1] + b[1]

    def wife(self, culture, husband_culture, surname, married_surname):
        """A woman keeps her own name; married into an Anglo line she is also known by her husband's surname."""
        name, native = self.name(culture, "f", surname)
        if husband_culture == "A":
            given = name.split(" ")[0] if culture == "A" else self.r.choice(ANGLO_F)
            maiden = surname[0] if isinstance(surname, tuple) else surname
            return "%s %s %s" % (given, maiden, married_surname[0] if isinstance(married_surname, tuple) else married_surname), native
        return name, native

    # -- a full pedigree: the father's line keeps its surname, each mother brings her own ---------------
    def pedigree(self, child_id, child_birth, father_surname, culture, generations):
        if generations == 0:
            return
        fb = child_birth - self.r.randint(25, 36)
        mb = fb + self.r.randint(-1, 6)
        surs = {"A": ANGLO_SUR, "K": KO_SUR, "C": ZH_SUR}[culture]
        msur = self.r.choice(surs)
        while msur == father_surname or (isinstance(msur, tuple) and isinstance(father_surname, tuple) and msur[0] == father_surname[0]):
            msur = self.r.choice(surs)
        ids = []
        for sex, born, sur in (("m", fb, father_surname), ("f", mb, msur)):
            nm = self.name(culture, sex, sur)
            gap = self.r.random()
            death = "?" if gap < 0.08 else str(born + self.r.randint(48, 92))     # a few deaths without a date
            birth = "" if gap > 0.95 else str(born)                                 # and a few unknown births
            grave = self.r.choice(GRAVES[culture]) if self.r.random() < 0.55 else ""
            pid = self.person(nm, sex, birth, death, burial=grave)
            ids.append(pid)
            self.pedigree(pid, born, sur, culture, generations - 1)
        self.couple(ids[0], ids[1], child_id)


def build(con, background="korean_anglo", seed=7):
    """Fill an empty database with the example family for this background. Returns the id of the man at the center."""
    if con.execute("SELECT 1 FROM person LIMIT 1").fetchone():
        raise SystemExit("The database already holds people; use --reset to replace them with the example.")
    F, Mo, W = LINES[background]
    B = Builder(con, seed)
    P, M, C = B.person, B.marry, B.couple
    fam, mom, wfam = FAMILY[F], MOTHERS[Mo], WIVES[W]
    n = lambda sex, given=None, culture=F, sur=fam: B.name(culture, sex, sur, given)
    anglo_names = F == "A"
    g = lambda m_or_f, english: english if anglo_names else None        # the Anglo line's own given names

    # The man at the center, his parents and grandparents (generations 1-2 written out; 3-8 generated)
    center = P(n("m", g("m", "Daniel")), "m", 1988, notes="The man at the center of the example. Stand as anyone to see the family from his or her place.")
    father = P(n("m", g("m", "James")), "m", 1958)
    mother = P(B.wife(Mo, F, mom, fam), "f", 1961)
    gfather = P(n("m", g("m", "Robert")), "m", 1930, 2012, burial=GRAVES[F][0])
    gmother = P(B.wife(F, F, B.r.choice({"A": ANGLO_SUR, "K": KO_SUR, "C": ZH_SUR}[F]), fam), "f", 1933)   # a widow, aged, living
    mgfather = P(n("m", culture=Mo, sur=mom), "m", 1932, 2015, burial=GRAVES[Mo][0])
    mgmother = P(B.name(Mo, "f", {"A": "Morgan", "K": ("Park", "박"), "C": ("Zhou", "周")}[Mo]), "f", 1936, 2019, burial=GRAVES[Mo][0])
    B.pedigree(gfather, 1930, fam, F, 6)
    B.pedigree(gmother, 1933, ("Ellis", "") if F == "A" else B.r.choice({"K": KO_SUR, "C": ZH_SUR}[F]), F, 6)
    B.pedigree(mgfather, 1932, mom, Mo, 6)
    B.pedigree(mgmother, 1936, ("Park", "박") if Mo == "K" else ("Zhou", "周") if Mo == "C" else "Morgan", Mo, 6)

    # His father's brothers and sister: the Head of the family by rule, an adoption, a widow
    uncle = P(n("m", g("m", "William")), "m", 1955)                            # the eldest: Head of the family by rule
    uncle_w = P(B.wife(F, F, ("Hale", "") if F == "A" else B.r.choice({"K": KO_SUR, "C": ZH_SUR}[F]), fam), "f", 1957)
    uncle2 = P(n("m", g("m", "John")), "m", 1964)
    uncle2_w = P(B.wife(F, F, ("Bennett", "") if F == "A" else B.r.choice({"K": KO_SUR, "C": ZH_SUR}[F]), fam), "f", 1965)
    aunt = P(n("f", g("f", "Elizabeth")), "f", 1962)
    aunt_h = P(B.name(F, "m", ("Grant", "") if F == "A" else B.r.choice({"K": KO_SUR, "C": ZH_SUR}[F])), "m", 1960, 2020, burial=GRAVES[F][1])
    C(gfather, gmother, uncle, father, aunt, uncle2)
    heir = P(n("m", g("m", "Benjamin")), "m", 1982)                            # the main-line heir after his father
    cousin_f = P(n("f", g("f", "Anna")), "f", 1985)
    C(uncle, uncle_w, heir, cousin_f)
    heir_w = P(B.wife(F, F, ("Foster", "") if F == "A" else B.r.choice({"K": KO_SUR, "C": ZH_SUR}[F]), fam), "f", 1984)
    C(heir, heir_w, P(n("m", g("m", "Owen")), "m", 2010))
    M(cousin_f, P(B.name(F, "m", ("Bell", "") if F == "A" else B.r.choice({"K": KO_SUR, "C": ZH_SUR}[F])), "m", 1983), "divorced")
    adopted = P(n("m", g("m", "Aaron")), "m", 2001, notes="Adopted as an infant.")
    B.child(adopted, uncle2, uncle2_w, kind="adopted")
    M(uncle2, uncle2_w)
    M(aunt, aunt_h)
    surname_of = lambda pid: (lambda r: (r[0].split()[-1], "") if F == "A" else (r[0].split()[0], (r[1] or "")[:1]))(
        con.execute("SELECT name, ko_name FROM person WHERE id=?", (pid,)).fetchone())
    B.child(P(B.name(F, "m", surname_of(aunt_h), "Luke" if F == "A" else None), "m", 2009), aunt_h, aunt)   # a minor in his widowed mother's house

    # His mother's family: her elder brother carried the line (his son now); her widowed sister's house has no man left
    m_brother = P(n("m", culture=Mo, sur=mom), "m", 1958, 2019, burial=GRAVES[Mo][0])
    m_brother_w = P(B.name(Mo, "f", ("Lee", "이") if Mo == "K" else ("Huang", "黄") if Mo == "C" else "Pierce"), "f", 1960)
    m_sister = P(B.name(Mo, "f", mom), "f", 1965)
    m_sister_h = P(B.name(Mo, "m", ("Choi", "최") if Mo == "K" else ("Wu", "吴") if Mo == "C" else "Draper"), "m", 1963, 2021)
    C(mgfather, mgmother, m_brother, mother, m_sister)
    C(m_brother, m_brother_w, P(n("m", culture=Mo, sur=mom), "m", 1987))
    C(m_sister_h, m_sister, P(B.name(Mo, "f", ("Choi", "최") if Mo == "K" else ("Wu", "吴") if Mo == "C" else "Draper"), "f", 1992))

    # His brothers and sister, their spouses and children
    brother = P(n("m", g("m", "Michael")), "m", 1985)
    brother_w = P(B.wife(F, F, ("Collins", "") if F == "A" else B.r.choice({"K": KO_SUR, "C": ZH_SUR}[F]), fam), "f", 1986)
    sister = P(n("f", g("f", "Hannah")), "f", 1991)
    sister_h = P(B.name(F, "m", ("Reed", "") if F == "A" else B.r.choice({"K": KO_SUR, "C": ZH_SUR}[F])), "m", 1989,
                 headship="abandoned", headship_note="Left his wife and children in 2022.")
    youngest = P(n("m", g("m", "Samuel")), "m", 1995, standing="estranged", standing_note="Has not answered the family for two years.")
    C(father, mother, brother, center, sister, youngest)
    nephew = P(n("m", g("m", "Ethan")), "m", 2012)
    niece = P(n("f", g("f", "Lily")), "f", 2015)
    C(brother, brother_w, nephew, niece)
    hs = surname_of(sister_h)
    C(sister_h, sister, P(B.name(F, "m", hs, "Noah" if F == "A" else None), "m", 2016), P(B.name(F, "f", hs, "Ella" if F == "A" else None), "f", 2019))

    # His wife and her family, three generations back
    wife = P(B.wife(W, F, wfam, fam), "f", 1990)
    w_father = P(B.name(W, "m", wfam), "m", 1960)
    w_mother = P(B.name(W, "f", {"A": "Morgan", "K": ("Park", "박"), "C": ("Zhao", "赵")}[W]), "f", 1962)
    B.pedigree(w_father, 1960, wfam, W, 2)
    B.pedigree(w_mother, 1962, {"A": "Morgan", "K": ("Park", "박"), "C": ("Zhao", "赵")}[W], W, 2)
    w_brother = P(B.name(W, "m", wfam), "m", 1987)
    w_sister = P(B.name(W, "f", wfam), "f", 1994)
    C(w_father, w_mother, wife, w_brother, w_sister)
    C(w_brother, P(B.name(W, "f", {"A": "Price", "K": ("Oh", "오"), "C": ("Ma", "马")}[W]), "f", 1988), P(B.name(W, "m", wfam), "m", 2017))
    C(P(B.name(W, "m", {"A": "Shaw", "K": ("Seo", "서"), "C": ("Guo", "郭")}[W]), "m", 1986), w_sister)   # her sister's husband: older than he

    # His own house
    kids = [P(n("m", g("m", "Josiah")), "m", 2016), P(n("f", g("f", "Naomi")), "f", 2019), P(n("m", g("m", "Eli")), "m", 2024)]
    C(center, wife, *kids)
    for kid, guardian in ((kids[0], brother), (kids[1], brother), (nephew, center)):     # some guardians named, some not
        con.execute("UPDATE person SET guardian_id=? WHERE id=?", (guardian, kid))

    for key, value in (("me", center), ("background", background)):
        con.execute("INSERT INTO setting(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    # A little use, so the screens are not empty: bonds, a few marks, and a matter before the family
    now = time.time()
    for a, b, st, note in ((center, youngest, "strained", "He does not answer."), (sister, sister_h, "broken", "He left in 2022."),
                           (center, father, "kept", ""), (center, uncle, "kept", "")):
        con.execute("INSERT INTO bond(from_id,to_id,state,note,at) VALUES(?,?,?,?,?)", (a, b, st, note, now))
    honor = con.execute("SELECT id FROM duty WHERE seed_ix=29").fetchone()                 # "Honor father and mother all their days."
    if honor:
        for parent in (father, mother):
            con.execute("INSERT INTO mark(person_id,toward_id,duty_id,state,note,at) VALUES(?,?,?,?,?,?)", (center, parent, honor[0], "kept", "", now))
    cur = con.execute("INSERT INTO matter(person_id,kind,title,status,at) VALUES(?,?,?,?,?)",
                      (youngest, "drifting", "Has drawn away from the family and does not answer", "open", now))
    con.execute("INSERT INTO matter_step(matter_id,step,day,by_ids,text,at) VALUES(?,?,?,?,?,?)",
                (cur.lastrowid, "private", "2025-03-02", "[%d]" % center, "His brother went to see him alone; he listened but said little.", now))
    con.commit()
    return center


def main(argv):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import db
    path = next((a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--background")), None)
    bg = argv[argv.index("--background") + 1] if "--background" in argv else "korean_anglo"
    if bg not in LINES:
        sys.exit("background must be one of: " + ", ".join(LINES))
    con = db.connect(path)
    if "--reset" in argv:
        for t in ("matter_step", "matter", "mark", "bond", "parent_child", "union_", "person", "household"):
            con.execute("DELETE FROM " + t)
        con.execute("DELETE FROM setting WHERE key IN ('me','clan_elder')")
        con.commit()
    center = build(con, bg)
    n = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    name = con.execute("SELECT name FROM person WHERE id=?", (center,)).fetchone()[0]
    print("Example family (%s) written: %d people; %s is #%d." % (bg, n, name, center))


if __name__ == "__main__":
    main(sys.argv[1:])
