"""Roles a person holds by their own condition (departed, minor, fatherless, aged, widow) and the heir of the
main line (종손): eldest son after eldest son from the founder, down to the first living man."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kin  # noqa: E402

Y = kin.THIS_YEAR


def person(pid, sex, born, died=""):
    return pid, {"id": pid, "name": "P%d" % pid, "sex": sex, "birth": str(born), "death": str(died) if died else ""}


def graph(people, links, unions=()):
    return kin.Graph(dict(people), [{"a_id": a, "b_id": b, "status": st} for a, b, st in unions],
                     [{"parent_id": p, "child_id": c, "kind": k} for p, c, k in links])


class RolesTest(unittest.TestCase):
    def setUp(self):
        # 1 founder (dead) → 2 eldest son (dead) and 3 younger son (living); 2 → 4 (dead, no sons); 3 → 5 (minor)
        self.people = [person(1, "m", 1900, 1970), person(2, "m", 1930, 1990), person(3, "m", 1935),
                       person(4, "m", 1955, 1960), person(5, "m", Y - 10), person(6, "f", 1938),
                       person(7, "f", Y - 12)]
        self.links = [(1, 2, "birth"), (1, 3, "birth"), (2, 4, "birth"), (3, 5, "birth"), (3, 7, "birth")]

    def test_heir_passes_around_an_eldest_line_with_no_living_man(self):
        g = graph(self.people, self.links)
        self.assertEqual(g.lineage_heir(5), 3)

    def test_heir_stays_in_the_eldest_line_when_a_man_lives_there(self):
        g = graph(self.people + [person(8, "m", 1960)], self.links + [(2, 8, "birth")])
        self.assertEqual(g.lineage_heir(5), 8)       # the eldest son's living son, though younger than his uncle

    def test_a_son_adopted_out_leaves_the_line(self):
        g = graph(self.people + [person(8, "m", 1960), person(9, "m", 1925)],
                  self.links + [(2, 8, "birth"), (9, 8, "adopted")])
        self.assertEqual(g.lineage_heir(5), 3)

    def test_status(self):
        g = graph(self.people, self.links, [(3, 6, "married")])
        self.assertEqual(g.status_tags(1), ["departed"])
        self.assertIn("aged", g.status_tags(3))
        self.assertEqual(g.status_tags(5), ["minor"])
        g2 = graph([p for p in self.people if p[0] != 3] + [person(3, "m", 1935, 2020)], self.links, [(3, 6, "married")])
        self.assertIn("widow", g2.status_tags(6))
        self.assertEqual(g2.status_tags(5), ["minor", "orphan"])
        self.assertIn("lineage_heir", g.status_tags(3, g.lineage_heir(5)))

    def test_sibling_in_law_rank_as_the_sangbyeon_tonggo_records(self):
        """Men linked by marriage rank by their own ages, never by a wife's or sister's (常變通攷, 妻齒爲坐之非);
        a woman ranks by her husband (女坐以夫之齒); between a man and his wife's sister, no rank (男女異長)."""
        people = [person(10, "m", 1950), person(11, "f", 1952), person(12, "m", 1980), person(13, "f", 1985),
                  person(14, "f", 1975), person(15, "m", 1970), person(16, "m", 1990), person(17, "m", 1972),
                  person(18, "f", 1983), person(19, "f", 1982)]
        links = [(10, 12, "birth"), (11, 12, "birth"), (10, 13, "birth"), (11, 13, "birth"), (10, 14, "birth"),
                 (11, 14, "birth"), (10, 17, "birth"), (11, 17, "birth")]
        g = graph(people, links, [(10, 11, "married"), (13, 15, "married"), (14, 16, "married"), (17, 18, "married"), (12, 19, "married")])
        tags = lambda a, b: g.relation(a, b)["them"]["tags"]
        self.assertIn("elder_sibling_in_law", tags(12, 15))      # my younger sister's husband, ten years older: senior by his own age
        self.assertIn("younger_sibling_in_law", tags(12, 16))    # my elder sister's husband, ten years younger: junior
        self.assertIn("elder_sibling_in_law", tags(16, 12))      # and to him I am the senior
        self.assertIn("elder_sibling_in_law", tags(12, 18))      # my elder brother's wife ranks by her husband, though younger than me
        self.assertIn("elder_sibling_in_law", tags(19, 17))      # to my wife, my elder brother ranks through me
        self.assertNotIn("elder_sibling_in_law", tags(12, 14) + tags(15, 14))
        self.assertIn("son_in_law", tags(10, 15))

if __name__ == "__main__":
    unittest.main()
