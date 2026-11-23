"""A duty reaches only the people its role pair names: a duty to a widowed mother is not owed to a living father,
and the duties between members, from the head of a house, and to the household are owed where they should be."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kin  # noqa: E402
import server  # noqa: E402

Y = kin.THIS_YEAR


def person(pid, sex, born, died=""):
    return pid, {"id": pid, "name": "P%d" % pid, "sex": sex, "birth": str(born), "death": str(died) if died else ""}


def duty(i, fr, to, text=""):
    return {"id": i, "from_role": fr, "to_role": to, "status": "draft", "text": text}


DUTIES = [duty(1, "child", "widow", "See that a widowed mother is cared for"), duty(2, "child", "parent"),
          duty(3, "member", "member"), duty(4, "household_head", "member"), duty(5, "married_daughter", "parent"),
          duty(6, "wife", "household"), duty(7, "child", "household"), duty(8, "clan_elder", "member"),
          duty(9, "member", "outside"), duty(10, "member", "clan_elder")]


class DutyRolesTest(unittest.TestCase):
    def family(self, father_dead=False):
        # 1 father, 2 mother, 3 son (minor, at home), 4 daughter married to 5
        people = dict([person(1, "m", 1950, 2020 if father_dead else ""), person(2, "f", 1952), person(3, "m", Y - 12),
                       person(4, "f", 1980), person(5, "m", 1978)])
        links = [{"parent_id": p, "child_id": c, "kind": "birth"} for p in (1, 2) for c in (3, 4)]
        unions = [{"a_id": 1, "b_id": 2, "status": "married"}, {"a_id": 4, "b_id": 5, "status": "married"}]
        return kin.Graph(people, unions, links), people

    def owe(self, g, people, a, b, head=1):
        r = server.with_standing(g.relation(a, b), people, a, b, server.acting_map(g, people), g, None, head)
        return {d["id"] for d in kin.duties_between(DUTIES, r["me"]["tags"], r["them"]["tags"])}

    def test_a_duty_to_a_widowed_mother_is_not_owed_to_a_living_father_or_a_wife(self):
        g, people = self.family()
        self.assertNotIn(1, self.owe(g, people, 3, 1))       # to my living father: no
        self.assertNotIn(1, self.owe(g, people, 3, 2))       # to my mother, whose husband lives: no
        self.assertIn(2, self.owe(g, people, 3, 1))          # the general duty to a parent still holds
        g, people = self.family(father_dead=True)
        self.assertIn(1, self.owe(g, people, 3, 2, head=None))   # once she is widowed: yes

    def test_members_owe_one_another_and_the_head_of_the_house_owes_those_in_it(self):
        g, people = self.family()
        self.assertIn(3, self.owe(g, people, 3, 4))
        self.assertIn(4, self.owe(g, people, 1, 3))          # the father heads his minor son's house
        self.assertNotIn(4, self.owe(g, people, 3, 1))       # not the other way round
        self.assertIn(8, self.owe(g, people, 1, 4))          # the Head of the family, toward a member
        self.assertNotIn(8, self.owe(g, people, 4, 1))
        self.assertNotIn(10, self.owe(g, people, 2, 3))      # nobody else is taken for the Head
        self.assertIn(10, self.owe(g, people, 3, 1))

    def test_a_married_daughter_owes_her_own_parents_as_such(self):
        g, people = self.family()
        self.assertIn(5, self.owe(g, people, 4, 2))
        self.assertNotIn(5, self.owe(g, people, 3, 2))       # her unmarried brother does not

    def test_a_wife_and_a_child_owe_their_household(self):
        g, _ = self.family()
        own = lambda pid: {d["id"] for d in kin.collective_duties(DUTIES, kin.standing_roles(pid, g, 1))}
        self.assertEqual(own(2) & {6, 7, 9}, {6, 9})         # the wife: to the household, and to those outside
        self.assertIn(7, own(3))                             # a son with living parents
        self.assertNotIn(6, own(3))


if __name__ == "__main__":
    unittest.main()


class FamilyTest(unittest.TestCase):
    def test_the_family_is_the_heads_kin_and_not_everyone_in_the_book(self):
        # 1 Head, 2 his wife, 3 her father, 4 their son, 5 a paramour of 4's sister 6, 7 the adoptive father of 2's brother 8
        people = dict([person(1, "m", 1950), person(2, "f", 1952), person(3, "m", 1925), person(4, "m", 1980),
                       person(5, "m", 1982), person(6, "f", 1984), person(7, "m", 1930), person(8, "m", 1955),
                       person(9, "m", 1960)])
        people[9]["standing"] = "outside"
        links = [{"parent_id": p, "child_id": c, "kind": k} for p, c, k in
                 ((1, 4, "birth"), (2, 4, "birth"), (1, 6, "birth"), (2, 6, "birth"), (3, 2, "birth"), (3, 8, "birth"), (7, 8, "adopted"))]
        unions = [{"a_id": 1, "b_id": 2, "status": "married"}, {"a_id": 5, "b_id": 6, "status": "paramour"},
                  {"a_id": 1, "b_id": 9, "status": "ex"}]
        g = kin.Graph(people, unions, links)
        fam = server.of_the_family(g, people, 1)
        self.assertEqual(set(fam) & {1, 2, 3, 4, 6, 8}, {1, 2, 3, 4, 6, 8})
        self.assertNotIn(5, fam)      # a paramour
        self.assertNotIn(7, fam)      # an in-law's own adoptive father: no kin to the Head
        self.assertNotIn(9, fam)      # set outside the family
