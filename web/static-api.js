/* The Way as static files (GitHub Pages): its Python runs here in the browser (Pyodide), read-only.
   tools/build_static.py puts this script first on each page of the published site; the program itself never loads it. */
(() => {
  const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
  const overlay = () => {
    if (document.getElementById("py-loading") || !document.body) return;
    document.body.insertAdjacentHTML("beforeend", '<div id="py-loading" style="position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:10000;background:#2b2118;color:#fff;padding:8px 16px;border-radius:20px;font:14px system-ui">道 …</div>');
  };
  const done = () => { const x = document.getElementById("py-loading"); if (x) x.remove(); };
  const ready = (async () => {
    await new Promise((ok, no) => { const s = document.createElement("script"); s.src = PYODIDE + "pyodide.js"; s.onload = ok; s.onerror = no; document.head.appendChild(s); });
    const py = await loadPyodide({indexURL: PYODIDE});
    await py.loadPackage("sqlite3");
    const files = await (await fetch("/py/manifest.json")).json();
    for (const f of files) {
      const parts = ("/app/" + f).split("/"); let dir = "";
      for (const p of parts.slice(1, -1)) { dir += "/" + p; try { py.FS.mkdir(dir); } catch (e) { /* exists */ } }
      py.FS.writeFile("/app/" + f, new Uint8Array(await (await fetch("/py/" + f)).arrayBuffer()));
    }
    py.runPython('import sys, os\nsys.path.insert(0, "/app")\nos.environ["FAMILY_DATA"] = "/tmp/way"\nimport static_api');
    return py.pyimport("static_api");
  })();
  const realFetch = window.fetch.bind(window);
  window.fetch = async (url, opts = {}) => {
    const u = new URL(url, location.href);
    if (u.origin !== location.origin || !u.pathname.startsWith("/api/")) return realFetch(url, opts);
    overlay();
    try {
      const api = await ready;
      const bg = decodeURIComponent((document.cookie.match(/(?:^|; )way_bg=([^;]+)/) || [])[1] || "");
      const [status, body] = api.handle((opts.method || "GET").toUpperCase(), u.pathname, u.search.slice(1), bg).toJs();
      return new Response(body, {status, headers: {"Content-Type": "application/json"}});
    } finally { done(); }
  };
})();
