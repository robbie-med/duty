"""Matters before the family, the if-he-dies forecast, and the burial and guardian fields."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402
import kin  # noqa: E402
import server  # noqa: E402

Y = kin.THIS_YEAR


class FeaturesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.con = db.connect(os.path.join(self.dir.name, "family.db"))
        add = lambda **p: server.write(self.con, "POST", ["person"], p, {})["id"]
        self.father = add(name="Father", sex="m", birth="1960")
        self.mother = add(name="Mother", sex="f", birth="1962")
        self.son = add(name="Son", sex="m", birth="1990")
        self.child = add(name="Child", sex="f", birth=str(Y - 8))
        server.write(self.con, "POST", ["union"], {"a_id": self.father, "b_id": self.mother}, {})
        for c in (self.son, self.child):
            for p in (self.father, self.mother):
                server.write(self.con, "POST", ["link"], {"parent_id": p, "child_id": c}, {})
        db.set_setting(self.con, "me", self.son)

    def tearDown(self):
        self.con.close(); self.dir.cleanup()

    def test_a_matter_keeps_its_steps_in_order(self):
        mid = server.write(self.con, "POST", ["matter"], {"person_id": self.son, "kind": "fault", "title": "a hard word"}, {})["id"]
        server.write(self.con, "POST", ["matter_step"], {"matter_id": mid, "step": "witnesses", "day": "2026-02-01", "by_ids": [self.father]}, {})
        server.write(self.con, "POST", ["matter_step"], {"matter_id": mid, "step": "private", "day": "2026-01-01", "by_ids": [self.father]}, {})
        server.write(self.con, "PUT", ["matter", str(mid)], {"status": "restored", "outcome": "he owned it"}, {})
        m = server.api_state(self.con, {})["matters"][0]
        self.assertEqual([x["step"] for x in m["steps"]], ["private", "witnesses"])
        self.assertEqual((m["status"], m["steps"][0]["by_ids"]), ("restored", [self.father]))
        with self.assertRaises(server.Bad):
            server.write(self.con, "POST", ["matter_step"], {"matter_id": mid, "step": "trial by ordeal"}, {})
        server.write(self.con, "DELETE", ["matter", str(mid)], {}, {})
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM matter_step").fetchone()[0], 0)

    def test_if_he_dies_the_house_passes_and_an_unguarded_minor_is_named(self):
        r = server.api_ifdies(self.con, {"id": [str(self.father)]})
        self.assertEqual(r["head_after"], self.son)
        after = {c["id"]: c["after"] for c in r["changes"]}
        self.assertEqual(after.get(self.child), self.son)          # the grown son takes up his father's house
        self.assertIn(self.child, r["minors_unguarded"])
        server.write(self.con, "PUT", ["person", str(self.child)], {"guardian_id": self.son, "burial": ""}, {})
        self.assertNotIn(self.child, server.api_ifdies(self.con, {"id": [str(self.father)]})["minors_unguarded"])
        self.assertIsNone(self.con.execute("SELECT death FROM person WHERE id=?", (self.father,)).fetchone()[0] or None)  # nothing written

    def test_burial_is_kept(self):
        server.write(self.con, "PUT", ["person", str(self.mother)], {"burial": "Hillside, row 3"}, {})
        self.assertEqual(self.con.execute("SELECT burial FROM person WHERE id=?", (self.mother,)).fetchone()[0], "Hillside, row 3")


if __name__ == "__main__":
    unittest.main()
