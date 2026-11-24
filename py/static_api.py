"""The Way without a server: the same answers server.py gives, computed in the browser (Pyodide) for the
published read-only site. Each example family is built in memory the first time it is shown."""
import json
import urllib.parse

import db
import example
import server

DBS = {}
READ_ONLY = "This is a read-only demonstration of The Way with an example family. Download it to keep your own family's record."


def con_for(bg):
    bg = bg if bg in server.BACKGROUNDS else server.DEFAULT_BG
    if bg not in DBS:
        con = db.connect(":memory:")          # seeds the duties and rulings
        example.build(con, bg)
        DBS[bg] = con
    return DBS[bg]


def handle(method, path, query, bg):
    """[status, JSON text] for one request."""
    if method != "GET":
        return [403, json.dumps({"error": READ_ONLY})]
    q = urllib.parse.parse_qs(query or "")
    try:
        if path == "/api/health":
            out = {"ok": True}
        elif path == "/api/library":
            out = {"results": [], "stats": {"books": 0, "passages": 0}}
        elif path in server.GET:
            out = server.GET[path](con_for(bg), q)
            if path == "/api/state":
                out.update(read_only=True, mode="example", library={"books": 0, "passages": 0})
        elif path.startswith("/api/ego/"):
            out = server.api_ego(con_for(bg), q, int(path.rsplit("/", 1)[1]))
        else:
            return [404, json.dumps({"error": "not found"})]
        return [200, json.dumps(out, ensure_ascii=False)]
    except (server.Bad, ValueError, KeyError) as e:
        return [400, json.dumps({"error": str(e) or "bad request"})]
