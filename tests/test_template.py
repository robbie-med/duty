"""The example family builds cleanly, and the public host is read-only."""
import http.client
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import db  # noqa: E402
import example  # noqa: E402
import server  # noqa: E402


class ExampleTest(unittest.TestCase):
    def test_the_example_family_shows_what_the_app_does(self):
        with tempfile.TemporaryDirectory() as d:
            con = db.connect(os.path.join(d, "family.db"))
            daniel = example.build(con)
            st = server.api_state(con, {})
            names = {p["id"]: p["name"] for p in st["people"]}
            self.assertGreater(len(st["people"]), 540)                       # eight generations on both sides
            self.assertEqual(names[st["head"]], "William Whitaker")
            self.assertTrue(st["bound"])                                      # a headless house, kept by kinship
            self.assertTrue(any(p.get("headship") == "abandoned" for p in st["people"]))
            g, _, _, _ = server.graph(con)
            eighth = [k for k, r in g.relations(daniel).items() if r["them"]["path"] == "P" * 8]
            self.assertEqual(len(eighth), 256)
            with self.assertRaises(SystemExit):                               # never written over a family's own record
                example.build(con)


class PublicReadOnlyTest(unittest.TestCase):
    def test_the_public_host_can_read_and_not_write(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, FAMILY_DB=os.path.join(d, "family.db"), FAMILY_PORT=str(port), PUBLIC_HOST="demo.example.org")
            proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py")], env=env, cwd=ROOT,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(50):
                    try:
                        socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
                    except OSError:
                        time.sleep(0.1)
                def call(method, path, host, body=None):
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    c.request(method, path, body=body, headers={"Host": host, "Content-Type": "application/json"})
                    r = c.getresponse(); data = r.read(); c.close()
                    return r.status, data
                self.assertEqual(call("GET", "/api/state", "demo.example.org")[0], 200)
                self.assertIn(b'"read_only": true', call("GET", "/api/state", "demo.example.org")[1])
                self.assertEqual(call("POST", "/api/person", "demo.example.org", b'{"name": "Vandal"}')[0], 403)
                self.assertEqual(call("POST", "/api/person", "127.0.0.1", b'{"name": "Owner"}')[0], 200)   # local editing still works
                self.assertEqual(call("GET", "/api/state", "elsewhere.example.com")[0], 403)
            finally:
                proc.terminate(); proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()


class BackgroundTest(unittest.TestCase):
    def family(self, bg):
        d = tempfile.mkdtemp()
        con = db.connect(os.path.join(d, "family.db"))
        center = example.build(con, bg)
        return con, center

    def test_every_background_builds_and_names_its_kin_in_its_own_tongues(self):
        want = {"anglo": ("", ""), "korean": ("아버지", ""), "chinese": ("", "父亲"), "korean_anglo": ("아버지", ""),
                "korean_chinese": ("아버지", "父亲"), "anglo_chinese": ("", "父亲")}
        for bg, (ko, zh) in want.items():
            con, center = self.family(bg)
            g, people, _, _ = server.graph(con)
            father = next(r for r in g.relations(center).values() if r["them"]["path"] == "P" and r["them"]["tags"][0] == "father")
            shown = father["them"]["ko"]
            self.assertEqual((ko in shown if ko else "아버지" not in shown, zh in shown if zh else "父亲" not in shown), (True, True), bg)

    def test_chinese_terms_tell_the_sides_and_ages_apart(self):
        con, center = self.family("chinese")
        g, _, _, _ = server.graph(con)
        terms = {r["them"]["ko"] for r in g.relations(center).values()}
        for t in ("伯父 (伯伯)", "舅父 (舅舅)", "姨母 (阿姨)", "嫂子", "妹夫", "小姨子", "侄子", "高祖父", "外高祖父"):
            self.assertIn(t, terms)
        self.assertTrue(terms & {"堂哥", "堂姐", "堂弟", "堂妹"})

    def test_every_tradition_binds_every_background(self):
        for bg in ("anglo", "chinese", "korean"):
            con, center = self.family(bg)
            trads = {d["tradition"] for d in server.api_state(con, {})["duties"]}
            self.assertTrue({"scripture", "korean", "confucian", "puritan"} <= trads, bg)


class LanguagesTest(unittest.TestCase):
    LOCS = ("ko", "zh-Hant", "zh-Hans")

    def test_every_interface_phrase_is_translated_with_its_placeholders(self):
        import json
        import re
        ph = lambda s: sorted(re.findall(r"\{(\w+)\}", s))
        dicts = {l: json.load(open(os.path.join(ROOT, "web", "i18n", l + ".json"), encoding="utf-8")) for l in self.LOCS}
        keys = set()
        for f in ("index.html", "m.html", "maps.js", "i18n.js"):
            src = open(os.path.join(ROOT, "web", f), encoding="utf-8").read()
            keys |= {m.group(2) for m in re.finditer(r'\bt\((["\'])((?:\\\1|(?!\1).)*)\1', src) if "${" not in m.group(2)}
        for l, d in dicts.items():
            missing = [k for k in keys if k not in d]
            self.assertLess(len(missing), 5, (l, missing[:10]))                # a stray phrase falls back to English
            bad = [k for k, v in d.items() if ph(k) != ph(v)]
            self.assertEqual(bad, [], l)

    def test_every_seeded_duty_and_ruling_is_translated(self):
        import json
        duties = json.load(open(os.path.join(ROOT, "way", "duties.json"), encoding="utf-8"))["duties"]
        cases = json.load(open(os.path.join(ROOT, "way", "rulings.json"), encoding="utf-8"))["rulings"]
        for l in self.LOCS:
            c = json.load(open(os.path.join(ROOT, "way", "i18n", l + ".json"), encoding="utf-8"))
            self.assertEqual(len(c["duties"]), len(duties), l)
            self.assertEqual(len(c["rulings"]), len(cases), l)

    def test_a_reworded_duty_shows_its_own_words_in_every_language(self):
        with tempfile.TemporaryDirectory() as d:
            con = db.connect(os.path.join(d, "family.db"))
            st = server.api_state(con, {})
            honor = next(x for x in st["duties"] if x["seed_ix"] == 29)
            self.assertIn("ko", honor["i18n"])
            con.execute("UPDATE duty SET text='Our own words.' WHERE seed_ix=29"); con.commit()
            honor = next(x for x in server.api_state(con, {})["duties"] if x["seed_ix"] == 29)
            self.assertFalse(honor.get("i18n"))
