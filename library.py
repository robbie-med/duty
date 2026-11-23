"""Full-text library over the books and house documents listed in way/library.json.
SQLite FTS5, no network, no model. The index (data/library.db) is disposable:
rebuild it any time with ./run.sh index. Source files are only read."""
import glob, html as _html, json, os, re, sqlite3, subprocess, tempfile, urllib.parse, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(ROOT, "way", "library.json")
LIB = os.environ.get("FAMILY_LIB") or os.path.join(os.environ.get("FAMILY_DATA") or os.path.join(ROOT, "data"), "library.db")
CHUNK = 1400


def _connect():
    os.makedirs(os.path.dirname(LIB), exist_ok=True)
    con = sqlite3.connect(LIB)
    cols = [r[1] for r in con.execute("PRAGMA table_info(chunk)")]
    if cols and "src" not in cols:                 # older index layout: it is disposable, start over
        con.execute("DROP TABLE chunk")
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunk USING fts5("
                "book, heading, body, path UNINDEXED, src UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
    return con


EXTS = (".epub", ".mobi", ".azw3", ".pdf", ".txt", ".md")       # also the order of preference


def _html_text(html):
    html = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", html)
    html = re.sub(r"(?is)<h[1-3][^>]*>(.*?)</h[1-3]>", lambda m: "\n\n# " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))) + "\n\n", html)
    html = re.sub(r"(?i)</(p|div|li|blockquote|tr|h[4-6])>|<br\s*/?>", "\n\n", html)
    return _html.unescape(re.sub(r"<[^>]+>", "", html))


def _epub_text(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        order = []
        try:                                        # reading order from the package spine
            opf = re.search(r'full-path="([^"]+)"', z.read("META-INF/container.xml").decode("utf-8", "replace")).group(1)
            pkg = z.read(opf).decode("utf-8", "replace")
            items = {}
            for tag in re.findall(r"<item\b[^>]*>", pkg):
                i, h = re.search(r'\bid="([^"]+)"', tag), re.search(r'\bhref="([^"]+)"', tag)
                if i and h:
                    items[i.group(1)] = h.group(1)
            base = os.path.dirname(opf)
            for ref in re.findall(r'<itemref\b[^>]*idref="([^"]+)"', pkg):
                if ref in items:
                    name = os.path.normpath(os.path.join(base, urllib.parse.unquote(items[ref]))).replace("\\", "/")
                    if name in names:
                        order.append(name)
        except Exception:
            order = []
        if not order:
            order = [n for n in names if n.lower().endswith((".xhtml", ".html", ".htm"))]
        return "\n\n".join(_html_text(z.read(n).decode("utf-8", "replace")) for n in order)


def extract(path):
    """Plain text of a book, or '' if it cannot be read (scanned PDF, DRM, damaged file)."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".txt", ".md"):
            return open(path, encoding="utf-8", errors="replace").read()
        if ext == ".epub":
            return _epub_text(path)
        if ext == ".pdf":
            r = subprocess.run(["pdftotext", "-q", path, "-"], capture_output=True, timeout=180)
            return r.stdout.decode("utf-8", "replace").replace("\f", "\n\n")
        if ext in (".mobi", ".azw3"):
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "book.txt")
                subprocess.run(["ebook-convert", path, out], capture_output=True, timeout=300)
                return open(out, encoding="utf-8", errors="replace").read() if os.path.exists(out) else ""
    except Exception:
        return ""
    return ""


def _title(path):
    t = os.path.splitext(os.path.basename(path))[0].replace("꞉", ":").replace("_", " ")
    return re.sub(r"\s+", " ", t).strip()


def _key(path):
    """Normalised title, so the same book in another format or a re-download can be recognized."""
    t = re.sub(r"\([^)]*\)", " ", _title(path).lower())
    t = re.sub(r"^[\d\s.\-]+", "", t)
    t = re.sub(r"^(a|an|the)\s+", "", t)
    t = re.sub(r"[\W_]+", "", t, flags=re.U)
    return re.sub(r"\d+$", "", t)[:40]


def _dupe(key, seen):
    if key in seen:
        return True
    return len(key) >= 12 and any(len(k) >= 12 and (k.startswith(key) or key.startswith(k)) for k in seen)


def _chunks(text):
    """Yield (heading, body) pieces of roughly CHUNK characters, split on paragraphs."""
    heading, buf, size = "", [], 0
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        m = re.match(r"^#{1,6}\s+(.*)", para)
        if m:
            if buf:
                yield heading, "\n\n".join(buf)
                buf, size = [], 0
            heading = m.group(1).strip()[:160]
            para = para[m.end():].strip()
            if not para:
                continue
        while len(para) > CHUNK * 2:                 # a wall of text with no breaks
            cut = para.rfind(". ", 0, CHUNK) + 1 or CHUNK
            buf.append(para[:cut]); para = para[cut:].strip()
            yield heading, "\n\n".join(buf)
            buf, size = [], 0
        buf.append(para); size += len(para)
        if size >= CHUNK:
            yield heading, "\n\n".join(buf)
            buf, size = [], 0
    if buf:
        yield heading, "\n\n".join(buf)


def build(verbose=True):
    with open(CONF, encoding="utf-8") as f:
        conf = json.load(f)
    sub = lambda v: re.sub(r"@(\w+)", lambda m: conf.get(m.group(1), ""), v) if v else ""
    con = _connect()
    where = lambda p: p if os.path.isabs(os.path.expanduser(p)) else os.path.join(ROOT, p)   # relative to the project
    wanted = {where(os.path.expanduser(s["path"])) for s in conf["sources"]}
    for (old,) in con.execute("SELECT DISTINCT src FROM chunk").fetchall():
        if old not in wanted:                       # a folder removed from the config
            con.execute("DELETE FROM chunk WHERE src=?", (old,))
    seen = {_key(p) for (p,) in con.execute("SELECT DISTINCT path FROM chunk")}
    books = n = 0
    unread = []
    for src in conf["sources"]:
        base = where(os.path.expanduser(src["path"]))
        if not os.path.isdir(base):
            if verbose:
                print("  (not mounted, keeping what is already indexed)  %s" % base)
            continue
        for (p,) in con.execute("SELECT DISTINCT path FROM chunk WHERE src=?", (base,)).fetchall():
            seen.discard(_key(p))
        con.execute("DELETE FROM chunk WHERE src=?", (base,))
        match, excl = sub(src.get("match")), sub(src.get("exclude"))
        files = [p for p in glob.glob(os.path.join(base, src.get("glob", "**/*")), recursive=True)
                 if os.path.isfile(p) and p.lower().endswith(EXTS)
                 and (not match or re.search(match, p[len(base):], re.I))
                 and not (excl and re.search(excl, p[len(base):], re.I))]
        files.sort(key=lambda p: (EXTS.index(os.path.splitext(p)[1].lower()), p))
        for path in files:
            key = _key(path)
            if _dupe(key, seen):
                continue
            text = extract(path)
            book = _title(path)
            fm = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
            if fm:                                  # sources/*.md carry a header: cite by its title and author
                meta = dict(re.findall(r"^(\w+):[ \t]*(.*)$", fm.group(1), flags=re.M))
                if meta.get("title"):
                    who = meta.get("translator") or meta.get("author") or ""
                    who = "" if not who or who.startswith("(") else who
                    lang = meta.get("language", "")
                    book = (meta["title"] + (" · " + meta["title_original"] if meta.get("title_original") else "")
                            + (" (" + who + ")" if who else "") + (" [" + lang + "]" if lang and lang != "en" else ""))[:200]
            text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
            text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
            pieces = [(h, b) for h, b in _chunks(text) if len(b) >= 80]
            if len(pieces) < 3:
                unread.append(path)
                continue
            seen.add(key)
            con.executemany("INSERT INTO chunk(book,heading,body,path,src) VALUES(?,?,?,?,?)",
                            [(book, h, b, path, base) for h, b in pieces])
            con.commit()
            books += 1; n += len(pieces)
            if verbose:
                print("%5d  %s" % (len(pieces), book[:100]), flush=True)
    con.commit(); con.close()
    os.chmod(LIB, 0o600)
    if verbose:
        print("Indexed %d passages from %d books this run." % (n, books))
        if unread:
            print("No readable text in %d files (scanned PDFs or protected):" % len(unread))
            for p in unread:
                print("   ", os.path.basename(p)[:100])
    return books, n


def stats():
    if not os.path.exists(LIB):
        return {"books": 0, "passages": 0}
    con = _connect()
    b, n = con.execute("SELECT COUNT(DISTINCT book), COUNT(*) FROM chunk").fetchone()
    con.close()
    return {"books": b, "passages": n}


def search(q, limit=20):
    words = re.findall(r"\w+", q or "", flags=re.U)
    words = [w for w in words if len(w) > 1][:12]
    if not words or not os.path.exists(LIB):
        return []
    con = _connect()
    out = []
    for joiner in (" ", " OR "):                      # all words first, then any word
        match = joiner.join('"%s"' % w for w in words)
        try:
            out = con.execute(
                "SELECT book, heading, snippet(chunk, 2, '[[', ']]', ' … ', 48), body "
                "FROM chunk WHERE chunk MATCH ? ORDER BY bm25(chunk, 4.0, 3.0, 1.0) LIMIT ?",
                (match, limit)).fetchall()
        except sqlite3.OperationalError:
            out = []
        if out:
            break
    con.close()
    return [{"book": b, "heading": h, "snippet": s, "body": body} for b, h, s, body in out]
