"""The seed file (way/duties.json) is append-only: these check that new duties, retired duties with their
reasons, and attestations arrive once, and that nothing the user changed is re-added or overwritten."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

BASE = {"spheres": {}, "traditions": {}, "roles": {}, "standings": {}}
ROW = lambda n: ["father", "child", "generation", "scripture", "Eph 6:4", "Duty %d." % n]


class SeedTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.seed = os.path.join(self.dir.name, "duties.json")
        self.path = os.path.join(self.dir.name, "family.db")
        self._old = db.SEED
        db.SEED = self.seed

    def tearDown(self):
        db.SEED = self._old
        self.dir.cleanup()

    def write(self, duties, attest=()):
        with open(self.seed, "w", encoding="utf-8") as f:
            json.dump(dict(BASE, duties=duties, attest=list(attest)), f)

    def duties(self, con):
        return db.rows(con, "SELECT * FROM duty ORDER BY id")

    def test_new_rows_reasons_and_attestations(self):
        self.write([ROW(0), ROW(1)])
        con = db.connect(self.path)
        self.assertEqual([d["seed_ix"] for d in self.duties(con)], [0, 1])
        con.close()
        retired = ["kin", "kin", "rites", "confucian", "Liji, Ji Tong 1", "Offer the seasonal sacrifices to the ancestors.",
                   {"status": "retired", "reason": "Worship belongs to God alone.", "counter": "Ex 20:3-5; WCF 21.2",
                    "attest": [["korean", "Gyeongmong Yogyeol, 祭禮", "..."]]}]
        self.write([ROW(0), ROW(1), retired], attest=[[0, "puritan", "Gouge 6.1", "quote"], [9, "english", "nowhere", ""]])
        con = db.connect(self.path)
        ds = self.duties(con)
        self.assertEqual(len(ds), 3)
        self.assertEqual((ds[2]["status"], ds[2]["reason"], ds[2]["counter"]), ("retired", "Worship belongs to God alone.", "Ex 20:3-5; WCF 21.2"))
        att = db.rows(con, "SELECT duty_id, tradition, citation FROM attest ORDER BY id")
        self.assertEqual(att, [{"duty_id": ds[2]["id"], "tradition": "korean", "citation": "Gyeongmong Yogyeol, 祭禮"},
                               {"duty_id": ds[0]["id"], "tradition": "puritan", "citation": "Gouge 6.1"}])   # row 9 does not exist: skipped
        con.close()
        con = db.connect(self.path)                      # offered once only
        self.assertEqual(len(self.duties(con)), 3)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM attest").fetchone()[0], 2)
        con.close()

    def test_user_changes_survive(self):
        self.write([ROW(0), ROW(1)])
        con = db.connect(self.path)
        con.execute("UPDATE duty SET text='Reworded.', status='confirmed' WHERE seed_ix=0")
        con.execute("DELETE FROM duty WHERE seed_ix=1")
        con.commit(); con.close()
        self.write([ROW(0), ROW(1), ROW(2)], attest=[[1, "puritan", "Gouge", ""], [0, "english", "Allestree", ""]])
        con = db.connect(self.path)
        ds = self.duties(con)
        self.assertEqual([(d["text"], d["status"]) for d in ds], [("Reworded.", "confirmed"), ("Duty 2.", "draft")])
        self.assertEqual(db.rows(con, "SELECT duty_id, tradition FROM attest"), [{"duty_id": ds[0]["id"], "tradition": "english"}])
        con.close()

    def test_old_database_gets_seed_rows_by_their_words(self):
        """A database made before seed_ix (like the live one) finds each offered duty by its text."""
        self.write([ROW(0), ROW(1)])
        con = sqlite3.connect(self.path)
        con.executescript(db.SCHEMA.split("CREATE TABLE IF NOT EXISTS attest")[0])
        con.executemany("INSERT INTO duty(from_role,to_role,sphere,tradition,citation,text) VALUES(?,?,?,?,?,?)", [ROW(0), ROW(1)])
        con.execute("INSERT INTO setting VALUES('seed_n', '2')")
        con.commit(); con.close()
        self.write([ROW(0), ROW(1)], attest=[[1, "newengland", "Wadsworth 1712", ""]])
        con = db.connect(self.path)
        self.assertEqual([d["seed_ix"] for d in self.duties(con)], [0, 1])
        self.assertEqual(db.rows(con, "SELECT duty_id FROM attest"), [{"duty_id": 2}])
        con.close()

    def test_role_fixes_reach_a_duty_unless_the_user_set_its_roles(self):
        self.write([ROW(0), ROW(1)])
        con = db.connect(self.path)
        con.execute("UPDATE duty SET from_role='mother' WHERE seed_ix=1")       # the user's own choice
        con.commit(); con.close()
        with open(self.seed, encoding="utf-8") as f:
            seed = json.load(f)
        seed["role_fixes"] = [[0, "father", "child", "parent", "minor"], [1, "father", "child", "parent", "minor"]]
        with open(self.seed, "w", encoding="utf-8") as f:
            json.dump(seed, f)
        con = db.connect(self.path)
        self.assertEqual([(d["from_role"], d["to_role"]) for d in self.duties(con)], [("parent", "minor"), ("mother", "child")])
        con.close()

    def test_a_revised_case_reaches_undecided_and_sent_back_cases_only(self):
        old = db.RULINGS
        db.RULINGS = os.path.join(self.dir.name, "rulings.json")
        try:
            case = lambda n, v, **k: dict({"topic": "Case %d" % n, "category": "contested", "verdict": v, "resolution": "first", "grounds": []}, **k)
            with open(db.RULINGS, "w", encoding="utf-8") as f:
                json.dump({"rulings": [case(i, "set aside") for i in range(4)]}, f)
            self.write([ROW(0)])
            con = db.connect(self.path)
            con.execute("UPDATE ruling SET status='accepted' WHERE seed_ix=1")
            con.execute("UPDATE ruling SET status='revise', note='keep the span' WHERE seed_ix=2")
            con.commit(); con.close()
            with open(db.RULINGS, "w", encoding="utf-8") as f:     # 0-2 revised; 3 edited without a new revision number
                json.dump({"rulings": [case(i, "keep in part", resolution="revised", rev=1) for i in range(3)] + [case(3, "keep")]}, f)
            con = db.connect(self.path)
            got = [(r["verdict"], r["resolution"], r["status"], r["note"]) for r in db.rows(con, "SELECT * FROM ruling ORDER BY seed_ix")]
            self.assertEqual(got, [("keep in part", "revised", "proposed", ""), ("set aside", "first", "accepted", ""),
                                   ("keep in part", "revised", "proposed", "keep the span"), ("set aside", "first", "proposed", "")])
            con.close()
        finally:
            db.RULINGS = old

if __name__ == "__main__":
    unittest.main()
