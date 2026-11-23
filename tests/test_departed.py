"""Toward the dead only the duties written for the departed apply; the dead owe nothing."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kin  # noqa: E402

D = [{"id": 1, "from_role": "child", "to_role": "parent", "status": "draft"},       # obey, provide …
     {"id": 2, "from_role": "child", "to_role": "departed", "status": "draft"},     # carry out a dead parent's just wishes
     {"id": 3, "from_role": "kin", "to_role": "departed", "status": "draft"},       # bury and mourn
     {"id": 4, "from_role": "kin", "to_role": "departed", "status": "retired"}]     # offerings to the dead: not kept


class DepartedTest(unittest.TestCase):
    def ids(self, mine, theirs):
        return [d["id"] for d in kin.duties_between(D, mine, theirs)]

    def test_living_parent_gets_living_duties_only(self):
        self.assertEqual(self.ids(["child", "kin"], ["parent", "kin"]), [1])

    def test_dead_parent_gets_departed_duties_only(self):
        self.assertEqual(self.ids(["child", "kin"], ["parent", "kin", "departed"]), [2, 3])

    def test_the_dead_owe_nothing(self):
        self.assertEqual(self.ids(["parent", "kin", "departed"], ["child", "kin"]), [])


if __name__ == "__main__":
    unittest.main()
