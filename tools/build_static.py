#!/usr/bin/env python3
"""Build The Way as static files for GitHub Pages (its Python runs in the visitor's browser, read-only).

  python3 tools/build_static.py [OUT_DIR] [--cname duty.example.org]      (default OUT_DIR: _site)
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = ["static_api.py", "server.py", "db.py", "kin.py", "library.py", "example.py"]


def main(argv):
    out = next((a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--cname")), "_site")
    cname = argv[argv.index("--cname") + 1] if "--cname" in argv else ""
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "py"))
    web = os.path.join(ROOT, "web")
    shutil.copytree(os.path.join(web, "i18n"), os.path.join(out, "i18n"))
    for f in ("maps.js", "i18n.js", "about.js", "static-api.js"):
        shutil.copy(os.path.join(web, f), os.path.join(out, f))
    tag = '<script src="/static-api.js"></script>\n'
    for src, names in (("index.html", ("index.html", "full.html")), ("m.html", ("m.html",))):
        html = open(os.path.join(web, src), encoding="utf-8").read()
        i = html.index("<script")                    # before every other script, so it answers their requests
        html = html[:i] + tag + html[i:]
        for n in names:
            open(os.path.join(out, n), "w", encoding="utf-8").write(html)
    files = list(PY)
    for f in PY:
        shutil.copy(os.path.join(ROOT, f), os.path.join(out, "py", f))
    for sub in ("way", os.path.join("way", "i18n")):
        os.makedirs(os.path.join(out, "py", sub), exist_ok=True)
        for f in sorted(os.listdir(os.path.join(ROOT, sub))):
            if f.endswith(".json") and ".bak" not in f:
                shutil.copy(os.path.join(ROOT, sub, f), os.path.join(out, "py", sub, f))
                files.append(os.path.join(sub, f).replace(os.sep, "/"))
    json.dump(files, open(os.path.join(out, "py", "manifest.json"), "w"))
    open(os.path.join(out, ".nojekyll"), "w").close()
    if cname:
        open(os.path.join(out, "CNAME"), "w").write(cname + "\n")
    print("Static site in %s: %d Python and data files%s" % (out, len(files), ", for " + cname if cname else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
