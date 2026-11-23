"use strict";
/* maps.js: the visual layer of The Way. Loaded before index.html's own script and only called after
   it has loaded the state, so it may use that script's globals (S, E, P, nm, egoId, sel, …).
     · lenses: one "Color by" choice shared by every map, with a legend that counts and filters
     · zoomable(): wheel-zoom, drag-pan and fit for any SVG map
     · Stand here: Fan (ancestors above, descendants below, gaps clickable) and Duties (coverage grid)
     · Atlas: Network (whole family, by birth year), Authority (who answers to whom), Lifelines
     · Between: the circle of ties; Clan: what needs attention */

/* ---------- indexes over the state (rebuilt when the state is reloaded) ---------- */
let _ix = null;
function IX() {
  if (_ix && _ix.S === S) return _ix;
  const kids = {}, parents = {}, spouses = {}, people = Object.values(S.people);
  for (const l of S.links) { (kids[l.parent_id] ||= []).push(l.child_id); (parents[l.child_id] ||= []).push(l.parent_id); }
  for (const u of S.unions) { (spouses[u.a_id] ||= []).push(u.b_id); (spouses[u.b_id] ||= []).push(u.a_id); }
  const yr = {}, dy = {}, est = {};
  for (const p of people) {
    const b = parseInt((p.birth || "").slice(0, 4)), d = parseInt((p.death || "").slice(0, 4));
    if (b) yr[p.id] = est[p.id] = b;
    if (d) dy[p.id] = d;
  }
  for (let pass = 0; pass < 8; pass++) for (const p of people) {       // a rough year for the undated, from kin
    if (yr[p.id] != null) continue;
    const g = [];
    for (const x of parents[p.id] || []) if (est[x] != null) g.push(est[x] + 28);
    for (const x of kids[p.id] || []) if (est[x] != null) g.push(est[x] - 28);
    for (const x of spouses[p.id] || []) if (est[x] != null) g.push(est[x]);
    if (g.length) est[p.id] = Math.round(g.reduce((a, b) => a + b) / g.length);
  }
  const line = {};                       // the father's line a person was born into, by its surname
  const lineOf = id => {
    if (line[id]) return line[id];
    let v = id; const seen = new Set([id]);
    for (;;) { const f = (parents[v] || []).find(x => P(x) && P(x).sex === "m"); if (f == null || seen.has(f)) break; seen.add(f); v = f; }
    const w = P(v).name.trim().split(/\s+/);
    return line[id] = w.length > 1 && !/^\(/.test(w[0]) ? w[w.length - 1] : "unknown";
  };
  const tally = {};
  for (const p of people) { const l = lineOf(p.id); if (l !== "unknown") tally[l] = (tally[l] || 0) + 1; }
  const lines = Object.entries(tally).sort((a, b) => b[1] - a[1]).slice(0, 6).map(x => x[0]);
  const root = {}, find = x => root[x] === x ? x : (root[x] = find(root[x] ?? (root[x] = x)));
  for (const p of people) root[p.id] = p.id;
  const join = (a, b) => { if (root[a] != null && root[b] != null) root[find(a)] = find(b); };
  S.links.forEach(l => join(l.parent_id, l.child_id)); S.unions.forEach(u => join(u.a_id, u.b_id));
  const comp = {}, size = {};
  for (const p of people) { comp[p.id] = find(p.id); size[comp[p.id]] = (size[comp[p.id]] || 0) + 1; }
  const main = +Object.entries(size).sort((a, b) => b[1] - a[1])[0]?.[0];
  return _ix = {S, kids, parents, spouses, yr, dy, est, lineOf, lines, comp, size, main};
}
const THIS_YEAR = new Date().getFullYear();
const ageOf = id => { const x = IX(); return x.yr[id] != null ? (dead(P(id)) ? (x.dy[id] ?? null) : THIS_YEAR) - x.yr[id] : null; };

/* ---------- lenses: what the color on every map means ---------- */
const CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"];   // validated, fixed order
const NONE = "#b9b0a0";
let lens = localStorage.getItem("way-lens") || "side", lensPick = null;
function sideOf(id) {
  if (!E || id === egoId) return "self";
  const r = E.rels[id]; if (!r) return "none";
  const p = r.them.path;
  if (/^[SXKQ]$/.test(p)) return "spouse";
  if (/^[SXKQ]/.test(p)) return "inlaws";
  if (p[0] === "C") return "children";
  if (/^PS?C/.test(p)) return "siblings";
  let v = id;
  for (let i = 0; i < 12 && E.rels[v] && E.rels[v].via !== egoId; i++) v = E.rels[v].via;
  return P(v) && P(v).sex === "f" ? "mother" : "father";
}
function dutyCounts(ids, marks) {
  const c = {kept: 0, poorly: 0, failing: 0, na: 0, open: 0, all: 0};
  for (const d of ids) { if (!S.duties[d] || S.duties[d].status === "retired") continue;
    c.all++; const m = marks && marks[d]; c[m && c[m.state] != null ? m.state : "open"]++; }
  return c;
}
function dutyState(id) {
  const r = E && E.rels[id]; if (!r) return "none";
  const c = dutyCounts(r.owe, r.marks_out);
  return !c.all ? "none" : c.failing ? "failing" : c.poorly ? "poorly" : !c.open ? "kept" : c.open < c.all ? "partial" : "open";
}
function gapOf(id) {
  const p = P(id);
  if (p.sex !== "m" && p.sex !== "f") return "sex";
  if (!p.birth) return "dates";
  if (!(IX().parents[id] || []).length) return "parents";
  return "complete";
}
const bondWord = s => ({kept: t("kept"), strained: t("strained"), broken: t("broken"), severed: t("severed"), unset: t("unset")})[s] || s;
const LENSES = {
  bond: {label: () => t("Bond with me"), ego: true, of: id => egoBond(id),
    cats: () => [["kept", t("kept"), "var(--kept)"], ["strained", t("strained"), "var(--strained)"], ["broken", t("broken"), "var(--broken)"], ["severed", t("severed"), "var(--severed)"], ["unset", t("not judged"), NONE]]},
  duties: {label: () => t("My duties examined"), ego: true, of: dutyState,
    cats: () => [["failing", t("a duty failing"), "var(--broken)"], ["poorly", t("not doing well"), "var(--strained)"], ["open", t("not examined"), "#2f6f9f"], ["partial", t("partly examined"), "#8fb0cf"], ["kept", t("all kept"), "var(--kept)"], ["none", t("no duties"), NONE]]},
  side: {label: () => t("Side of the family"), ego: true, of: sideOf,
    cats: () => [["father", t("father’s side"), CAT[0]], ["mother", t("mother’s side"), CAT[1]], ["siblings", t("brothers & sisters"), CAT[2]], ["spouse", t("spouse"), CAT[3]], ["children", t("descendants"), CAT[4]], ["inlaws", t("spouse’s side"), CAT[5]], ["none", t("no known tie"), NONE], ["self", t("me"), "var(--ink)"]]},
  standing: {label: () => t("Standing"), of: id => dead(P(id)) ? "dead" : standing(P(id)) || "member",
    cats: () => [["member", t("member"), "#8d8473"], ["entering", t("being received"), "#2f6f9f"], ["estranged", t("estranged"), "#c98a1b"], ["cut_off", t("cut off"), "#1d1b19"], ["outside", t("not of the family"), "#c4bdb0"], ["dead", t("dead"), "#e2dacb"]]},
  line: {label: () => t("Father’s line"), of: id => { const l = IX().lineOf(id); return IX().lines.includes(l) ? l : "other"; },
    cats: () => [...IX().lines.map((l, i) => [l, l, CAT[i]]), ["other", t("other lines"), NONE]]},
  gaps: {label: () => t("Missing facts"), of: gapOf,
    cats: () => [["sex", t("sex unknown"), "var(--broken)"], ["dates", t("no birth date"), "var(--strained)"], ["parents", t("no parents on record"), "#2f6f9f"], ["complete", t("complete"), "var(--kept)"]]},
};
const lensKey = () => (LENSES[lens] && (!LENSES[lens].ego || E)) ? lens : "standing";
const lensOf = id => LENSES[lensKey()].of(+id);
function lensColor(id) { const k = lensOf(id), c = LENSES[lensKey()].cats().find(x => x[0] === k); return c ? c[2] : NONE; }
const faded = id => lensPick != null && lensOf(id) !== lensPick;
const REDRAW = {stand: () => { draw(); panel(); }, atlas: () => drawAtlas(), map: () => drawMap()};
function setLens(v, where) { lens = v; lensPick = null; localStorage.setItem("way-lens", v); REDRAW[where](); }
function pickLens(k, where) { lensPick = lensPick === k ? null : k; REDRAW[where](); }
function lensControls(ids, where) {
  const L = LENSES[lensKey()], counts = {};
  for (const i of ids) { const k = L.of(+i); counts[k] = (counts[k] || 0) + 1; }
  const opts = Object.entries(LENSES).filter(([, v]) => !v.ego || E).map(([k, v]) => `<option value="${k}"${k === lensKey() ? " selected" : ""}>${esc(v.label())}</option>`).join("");
  return `<label class="mute" style="font-size:13px">${t("Color by")} <select class="lens" onchange="setLens(this.value,'${where}')">${opts}</select></label>
    <span class="legend">${L.cats().filter(c => counts[c[0]]).map(([k, label, col]) =>
      `<span class="lchip${lensPick === k ? " on" : ""}${lensPick != null && lensPick !== k ? " off" : ""}" title="${t("show only these")}" onclick="pickLens('${k}','${where}')"><i style="background:${col}"></i>${esc(label)} <b>${counts[k]}</b></span>`).join("")}</span>`;
}

/* ---------- zoom and pan for any SVG map ---------- */
const VB = {};
function zoomable(host, key, box, reset, focus) {
  const svg = host.querySelector("svg"); if (!svg || !host.clientWidth) return;
  svg.setAttribute("width", "100%"); svg.setAttribute("height", "100%");
  const W = host.clientWidth, H = host.clientHeight, PAD = 30;
  const fitTo = (cap) => {
    let s = Math.max((box.w + 2 * PAD) / W, (box.h + 2 * PAD) / H);
    if (cap) s = Math.min(s, cap);
    const cx = focus && s === cap ? focus.x : box.x + box.w / 2, cy = focus && s === cap ? focus.y : box.y + box.h / 2;
    return [cx - W * s / 2, cy - H * s / 2, W * s, H * s];
  };
  let vb = (!reset && VB[key]) || fitTo(focus && focus.cap || 1.6);
  const apply = () => { VB[key] = vb; svg.setAttribute("viewBox", vb.map(v => v.toFixed(1)).join(" "));
    const k = vb[2] / W; svg.classList.toggle("far", k > 1.25); svg.classList.toggle("near", k < 0.8); };
  apply();
  const toSvg = (cx, cy) => { const r = svg.getBoundingClientRect(); return [vb[0] + (cx - r.left) / r.width * vb[2], vb[1] + (cy - r.top) / r.height * vb[3]]; };
  const zoom = (k, cx, cy) => {
    const w = Math.min(Math.max(vb[2] * k, 120), Math.max(box.w, box.h, W) * 4); k = w / vb[2];
    const [px, py] = cx == null ? [vb[0] + vb[2] / 2, vb[1] + vb[3] / 2] : toSvg(cx, cy);
    vb = [px - (px - vb[0]) * k, py - (py - vb[1]) * k, vb[2] * k, vb[3] * k]; apply();
  };
  svg.onwheel = e => { e.preventDefault(); zoom(Math.exp(Math.max(-60, Math.min(60, e.deltaY)) * 0.004), e.clientX, e.clientY); };
  let drag = null, moved = false;
  svg.onpointerdown = e => { if (e.button !== 0) return; drag = {x: e.clientX, y: e.clientY, vb: vb.slice()}; moved = false; };
  svg.onpointermove = e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!moved && Math.hypot(dx, dy) < 4) return;
    if (!moved) { moved = true; svg.setPointerCapture(e.pointerId); svg.classList.add("panning"); }
    const r = svg.getBoundingClientRect();
    vb = [drag.vb[0] - dx * vb[2] / r.width, drag.vb[1] - dy * vb[3] / r.height, vb[2], vb[3]]; apply();
  };
  svg.onpointerup = svg.onpointercancel = () => { drag = null; svg.classList.remove("panning"); };
  svg.addEventListener("click", e => { if (moved) { e.stopPropagation(); e.preventDefault(); moved = false; } }, true);
  const z = document.createElement("div");
  z.className = "zbtns";
  z.innerHTML = `<button title="${t("zoom in")}">+</button><button title="${t("zoom out")}">−</button><button title="${t("fit everything")}">⤢</button>`;
  const [bi, bo, bf] = z.querySelectorAll("button");
  bi.onclick = () => zoom(1 / 1.4); bo.onclick = () => zoom(1.4); bf.onclick = () => { vb = fitTo(); apply(); };
  host.appendChild(z);
  host.zoomTo = (x, y, w) => { const ww = w || Math.min(vb[2], W * 1.1); vb = [x - ww / 2, y - ww * H / W / 2, ww, ww * H / W]; apply(); };
}

/* ---------- Stand here · Fan: ancestors above, descendants below ---------- */
const BANDS = [56, 150, 236, 312, 380, 440, 494];
const fanPt = (r, a) => `${(r * Math.cos(a)).toFixed(1)} ${(r * Math.sin(a)).toFixed(1)}`;
function wedge(r0, r1, a0, a1) {
  const L = a1 - a0 > Math.PI ? 1 : 0;
  return `M${fanPt(r1, a0)}A${r1} ${r1} 0 ${L} 1 ${fanPt(r1, a1)}L${fanPt(r0, a1)}A${r0} ${r0} 0 ${L} 0 ${fanPt(r0, a0)}Z`;
}
function wedgeText(r0, r1, a0, a1, lines, cls) {
  const am = (a0 + a1) / 2, rm = (r0 + r1) / 2, arc = rm * (a1 - a0), depth = r1 - r0, deg = am * 180 / Math.PI;
  const along = arc > depth * 1.15;
  let rot, room;
  if (along) { rot = deg + 90; if (Math.sin(am) > 0.05) rot -= 180; room = arc - 10; }
  else { rot = Math.cos(am) < 0 ? deg + 180 : deg; room = depth - 12; }
  if (!along && arc < 13) return "";
  const n = Math.max(3, Math.floor(room / 6.6)), [x, y] = fanPt(rm, am).split(" ");
  const ls = along ? lines : lines.slice(0, arc > 26 ? 2 : 1);
  return `<g transform="translate(${x},${y}) rotate(${rot.toFixed(1)})">${ls.map((ln, i) =>
    `<text class="${i ? "rl" : cls}" text-anchor="middle" y="${(i - (ls.length - 1) / 2) * 13 + 4}">${esc(clip(ln, n))}</text>`).join("")}</g>`;
}
function drawFan() {
  const box = $("#tree"), x = IX(), G = 6, DG = 4;
  const parentsBySex = id => { const ps = x.parents[id] || []; let f = ps.find(p => P(p).sex === "m"), m = ps.find(p => P(p).sex === "f");
    const rest = ps.filter(p => p !== f && p !== m); if (f == null && rest.length) f = rest.shift(); if (m == null && rest.length) m = rest.shift(); return [f, m]; };
  let s = "", ids = [];
  const slot = (id, g, a0, a1, what, child) => {
    const r0 = BANDS[g - 1], r1 = BANDS[g];
    if (id == null) {
      if (child == null || g > 4) return;
      s += `<g class="fgap" onclick="addParentOf(${child},'${what}')"><title>${what === "mother" ? t("No mother on record for {name}. Click to add.", {name: esc(nm(child))}) : t("No father on record for {name}. Click to add.", {name: esc(nm(child))})}</title>
        <path d="${wedge(r0 + 2, r1 - 2, a0 + 0.004, a1 - 0.004)}"/>${wedgeText(r0, r1, a0, a1, [what === "mother" ? t("+ mother") : t("+ father")], "rl")}</g>`;
      return;
    }
    ids.push(id);
    const p = P(id), col = lensColor(id), r = E.rels[id];
    s += `<g class="fw${dead(p) ? " dead" : ""}${sel === id ? " sel" : ""}${faded(id) ? " faded" : ""}" data-id="${id}">
      <title>${esc(p.name)} ${esc(life(p))}${r ? " — " + esc(r.them.en) : ""}</title>
      <path d="${wedge(r0, r1, a0, a1)}" style="fill:${col};stroke:${col}"/>
      ${wedgeText(r0, r1, a0, a1, [p.name, [life(p), r ? native(r.them).split(" (")[0] : ""].filter(Boolean).join(" · ")], "nm")}</g>`;
  };
  const up = (id, g, a0, a1) => {                 // father on the left, mother on the right
    if (g > G) return;
    const [f, m] = parentsBySex(id), mid = (a0 + a1) / 2;
    slot(f, g, a0, mid, "father", id); slot(m, g, mid, a1, "mother", id);
    if (f != null) up(f, g + 1, a0, mid);
    if (m != null) up(m, g + 1, mid, a1);
  };
  up(egoId, 1, Math.PI, 2 * Math.PI);
  const kidsOf = id => [...new Set(x.kids[id] || [])].sort((a, b) => (x.est[a] ?? 9999) - (x.est[b] ?? 9999));
  const leaves = (id, g) => g >= DG ? 1 : Math.max(1, kidsOf(id).reduce((n, k) => n + leaves(k, g + 1), 0));
  const down = (id, g, a1, a0) => {                // eldest on the left: angles run from π down to 0
    if (g > DG) return;
    const ks = kidsOf(id), tot = ks.reduce((n, k) => n + leaves(k, g), 0); let c = a1;
    for (const k of ks) { const span = (a1 - a0) * leaves(k, g) / tot; slot(k, g, c - span, c); down(k, g + 1, c, c - span); c -= span; }
  };
  const nk = kidsOf(egoId).length;
  if (nk) down(egoId, 1, Math.PI, 0);
  const e = E.ego, words = e.name.split(" "), first = words.slice(0, -1).join(" ") || e.name, last = words.length > 1 ? words[words.length - 1] : "";
  const R = BANDS[G];
  let svg = `<svg viewBox="${-R - 20} ${-R - 20} ${2 * R + 40} ${2 * R + 40}">
    <line x1="${-R}" x2="${R}" y1="0" y2="0" class="axis"/>
    <text class="fanlabel" x="${-R}" y="-8">${t("ancestors ↑")}</text>${nk ? `<text class="fanlabel" x="${-R}" y="18">${t("descendants ↓")}</text>` : `<text class="fanlabel" x="0" y="40" text-anchor="middle">${t("no children on record")}</text>`}
    ${s}<g class="fw ego" data-id="${egoId}"><circle r="${BANDS[0] - 4}"/><text class="nm" y="${last ? -3 : 4}" text-anchor="middle">${esc(clip(first, 12))}</text>${last ? `<text class="nm" y="12" text-anchor="middle">${esc(clip(last, 12))}</text>` : ""}</g></svg>`;
  box.innerHTML = svg;
  box.querySelectorAll(".fw").forEach(n => {
    n.onclick = () => { const id = +n.dataset.id; sel = id === egoId ? null : id; examine = false; draw(); panel(); };
    n.ondblclick = () => standAs(+n.dataset.id);
  });
  zoomable(box, "fan" + egoId, {x: -R, y: -R, w: 2 * R, h: nk ? 2 * R : R + 60}, recenter, {x: 0, y: nk ? 0 : -R / 2});
  recenter = false;
  return ids;
}
function addParentOf(child, what) {
  personDialog(child);
  $("#k_type").value = "parent"; $("#k_sex").value = what === "mother" ? "f" : "m";
  $("#k_name").placeholder = what === "mother" ? t("mother's name, or pick someone already in the tree") : t("father's name, or pick someone already in the tree"); $("#k_name").focus();
}

/* ---------- Stand here · Duties: what I owe each person, by sphere ---------- */
let dutySort = "near";
function drawDuties() {
  const box = $("#tree"), spheres = Object.keys(S.meta.spheres);
  let rows = shown().filter(id => E.rels[id].owe.length);
  const cnt = {}, cell = {};
  for (const id of rows) { const r = E.rels[id]; cnt[id] = dutyCounts(r.owe, r.marks_out);
    for (const k of spheres) cell[id + k] = dutyCounts(r.owe.filter(d => S.duties[d] && S.duties[d].sphere === k), r.marks_out); }
  const near = (a, b) => E.rels[a].them.path.length - E.rels[b].them.path.length || rank(a) - rank(b);
  rows.sort(dutySort === "open" ? (a, b) => cnt[b].open - cnt[a].open || near(a, b) : dutySort === "failing" ? (a, b) => cnt[b].failing - cnt[a].failing || near(a, b) : near);
  const used = spheres.filter(k => rows.some(id => cell[id + k].all) || dutyCounts(E.collective.filter(d => S.duties[d].sphere === k)).all);
  const tot = rows.reduce((t, id) => { for (const k in t) t[k] += cnt[id][k]; return t; }, {kept: 0, poorly: 0, failing: 0, na: 0, open: 0, all: 0});
  const max = Math.max(1, ...rows.flatMap(id => used.map(k => cell[id + k].all)));
  const bar = (c, w) => !c.all ? "" : `<span class="sbar" style="width:${Math.max(6, w * c.all / max)}px">${["failing", "poorly", "kept", "na", "open"].filter(k => c[k]).map(k => `<i class="${k}" style="flex:${c[k]}"></i>`).join("")}</span>`;
  const next = rows.slice().sort((a, b) => near(a, b)).find(id => cnt[id].open);
  const col = E.collective, cc = dutyCounts(col, E.marks_collective);
  box.innerHTML = `<div class="dgrid">
    <div class="row" style="margin-bottom:10px">
      <div>${t("{n} duties {name} owes {people} people on screen", {n: `<b>${tot.all}</b>`, name: esc(nm(egoId)), people: rows.length})} ·
        <span style="color:var(--kept)">${t("{n} kept", {n: tot.kept})}</span> · <span style="color:var(--strained)">${t("{n} not doing well", {n: tot.poorly})}</span> · <span style="color:var(--broken)">${t("{n} failing", {n: tot.failing})}</span> · ${t("{n} n/a", {n: tot.na})} · ${t("{n} not yet examined", {n: `<b>${tot.open}</b>`})}</div>
      ${tot.all ? `<span class="sbar" style="width:220px">${["failing", "poorly", "kept", "na", "open"].filter(k => tot[k]).map(k => `<i class="${k}" style="flex:${tot[k]}"></i>`).join("")}</span>` : ""}
      <span class="grow"></span>
      ${next ? `<button class="btn sm pri" onclick="openDuties(${next},null)">${t("Examine next: {name} ({n}) →", {name: esc(nm(next)), n: cnt[next].open})}</button>` : ""}
      <label class="mute" style="font-size:13px">${t("order")} <select onchange="dutySort=this.value;draw()">${[["near", t("nearest first")], ["open", t("most unexamined")], ["failing", t("most failing")]].map(([k, v]) => `<option value="${k}"${dutySort === k ? " selected" : ""}>${v}</option>`).join("")}</select></label></div>
    <table class="dtab"><tr><th>${t("Toward")}</th><th class="num">${t("all")}</th>${used.map(k => `<th>${esc(label("spheres", k))}</th>`).join("")}</tr>
    ${rows.map(id => { const r = E.rels[id], c = cnt[id];
      return `<tr class="${sel === id ? "on" : ""}"><th class="who" onclick="openDuties(${id},null)"><i class="dot" style="background:var(--${egoBond(id)})" title="${t("bond: {state}", {state: bondWord(egoBond(id))})}"></i>${esc(nm(id))}<small>${esc(r.them.en.split(" (")[0])}</small></th>
        <td class="num" onclick="openDuties(${id},null)">${c.all}${c.failing ? ` <b style="color:var(--broken)">✕${c.failing}</b>` : ""}${c.poorly ? ` <b style="color:var(--strained)">~${c.poorly}</b>` : ""}</td>
        ${used.map(k => { const x = cell[id + k];
          return x.all ? `<td class="dc" onclick="openDuties(${id},'${k}')" title="${t("{name} · {sphere}: {all} duties — {kept} kept, {poorly} not doing well, {failing} failing, {na} n/a, {open} not examined", {name: esc(nm(id)), sphere: esc(label("spheres", k)), all: x.all, kept: x.kept, poorly: x.poorly, failing: x.failing, na: x.na, open: x.open})}">${bar(x, 90)}<span>${x.all}</span></td>` : `<td class="dc empty"></td>`; }).join("")}</tr>`; }).join("")}
    ${cc.all ? `<tr><th class="who" onclick="openDuties(null,null)">${t("To the house and clan")}<small>${t("collective duties")}</small></th><td class="num">${cc.all}</td>${used.map(k => { const x = dutyCounts(col.filter(d => S.duties[d].sphere === k), E.marks_collective); return x.all ? `<td class="dc" onclick="openDuties(null,'${k}')">${bar(x, 90)}<span>${x.all}</span></td>` : `<td class="dc empty"></td>`; }).join("")}</tr>` : ""}
    </table>
    <div class="legend" style="margin-top:8px"><span><i class="failing"></i>${t("failing")}</span><span><i class="poorly"></i>${t("not doing well")}</span><span><i class="kept"></i>${t("kept")}</span><span><i class="na"></i>${t("does not apply")}</span><span><i class="open"></i>${t("not examined")}</span>
      <span>· ${t("bar length = number of duties · click a cell to mark those duties in the panel")}</span></div></div>`;
  return rows;
}
function openDuties(id, sphere) {
  sel = id; examine = false; panel();
  const el = $("#panel"), at = sphere ? el.querySelector(`.sphere[data-sphere="${sphere}"]`) : el.querySelector(".sect h3 + *")?.parentElement;
  if (at) { at.scrollIntoView({block: "start", behavior: "smooth"}); at.classList.add("flash"); setTimeout(() => at.classList.remove("flash"), 1400); }
  else el.scrollTop = 0;
  if (view === "duties") draw();
}

/* ---------- Atlas: the whole family ---------- */
let atlasView = localStorage.getItem("way-atlas") || "network", atlasSel = null, atlasWho = "all", atlasByYear = true, lifeBand = null, NETPOS = null;
function setAtlas(v) { atlasView = v; atlasSel = null; localStorage.setItem("way-atlas", v); recenterAtlas = true; drawAtlas(); syncHash(); }
let recenterAtlas = true;
function atlasPeople() {
  const all = Object.values(S.people).map(p => p.id), x = IX();
  if (atlasWho === "living") return all.filter(id => !dead(P(id)));
  if (atlasWho === "near") { const set = new Set(all.filter(id => !dead(P(id))));
    for (const id of [...set]) for (const q of [...(x.parents[id] || []), ...(x.kids[id] || []), ...(x.spouses[id] || [])]) set.add(q);
    return [...set]; }
  return all;
}
function drawAtlas() {
  const host = $("#atlas"), seg = [["network", t("Network")], ["authority", t("Authority")], ["lifelines", t("Lifelines")]];
  host.classList.toggle("scroll", atlasView !== "network");
  let ids = atlasPeople();
  const who = `<select onchange="atlasWho=this.value;NETPOS=null;recenterAtlas=true;drawAtlas()">${[["all", t("everyone")], ["near", t("the living and their nearest")], ["living", t("only the living")]].map(([k, v]) => `<option value="${k}"${atlasWho === k ? " selected" : ""}>${v}</option>`).join("")}</select>`;
  const find = `<div class="find"><input type="search" id="aq" placeholder="${t("find on the map…")}" autocomplete="off" style="width:170px"><div class="drop" id="adrop" hidden></div></div>`;
  if (atlasView === "network") ids = drawNetwork(ids);
  else if (atlasView === "authority") ids = drawAuthority();
  else ids = drawLifelines(ids);
  $("#atools").innerHTML = `<span class="seg">${seg.map(([k, v]) => `<button class="${atlasView === k ? "on" : ""}" onclick="setAtlas('${k}')">${v}</button>`).join("")}</span>
    ${atlasView !== "authority" ? who : ""}${atlasView === "network" ? `<label class="mute" style="font-size:13px"><input type="checkbox" ${atlasByYear ? "checked" : ""} onchange="atlasByYear=this.checked;NETPOS=null;recenterAtlas=true;drawAtlas()"> ${t("top to bottom by birth year")}</label>` : ""}
    ${find}${atlasView !== "authority" ? lensControls(ids, "atlas") : ""}`;
  attachFinder($("#aq"), $("#adrop"), id => { atlasSel = id; drawAtlas(); const h = $("#atlas"); if (h.zoomTo && NETPOS && NETPOS.pos[id]) h.zoomTo(NETPOS.pos[id].x, NETPOS.pos[id].y, 700);
    else { const el = h.querySelector(`[data-id="${id}"]`); if (el) el.scrollIntoView({block: "center"}); } });
  atlasPanel(); syncHash();
}
const MISSB = {b: '<b style="color:var(--strained)">', _b: "</b>"};
const lineName = l => l === "unknown" ? t("unknown line") : t("{line} line", {line: esc(l)});
function atlasPanel() {
  const el = $("#apanel"), id = atlasSel;
  if (id != null && P(id)) {
    const p = P(id), r = E && E.rels[id], x = IX();
    const kin = (label, list) => list.length ? `<div style="font-size:13px;margin:2px 0"><span class="mute">${label}:</span> ${list.map(k => `<a href="#" onclick="atlasSel=${k};drawAtlas();return false">${esc(nm(k))}</a>`).join(", ")}</div>` : "";
    const c = r ? dutyCounts(r.owe, r.marks_out) : null;
    el.innerHTML = `<h2>${esc(p.name)} ${p.ko_name ? `<span class="ko">${esc(p.ko_name)}</span>` : ""} ${stBadge(p)}</h2>
      <div class="mute">${esc(life(p))}${ageOf(id) != null ? ` · ${dead(p) ? t("died at {n}", {n: ageOf(id)}) : t("age {n}", {n: ageOf(id)})}` : x.est[id] ? ` · ${t("born about {y} (estimated)", {y: x.est[id]})}` : ""} · ${lineName(x.lineOf(id))}</div>
      ${headLine(id)}
      ${r ? `<div class="rel">${t("{rel} of {name}", {rel: `<b>${esc(r.them.en)}</b>`, name: esc(nm(egoId))})}${native(r.them) ? ` <span class="ko">${esc(native(r.them))}</span>` : ""}${r.them.chon ? ` <span class="mute">· ${r.them.chon}촌</span>` : ""}</div>
        <div style="font-size:13px">${t("Bond: {state}", {state: `<b style="color:var(--${egoBond(id)})">${egoBond(id) === "unset" ? t("not judged") : bondWord(egoBond(id))}</b>`})} · ${t("{name} owes {all} duties: {kept} kept, {poorly} not doing well, {failing} failing, {open} not examined", {name: esc(nm(egoId)), all: c.all, kept: c.kept, poorly: c.poorly, failing: c.failing, open: c.open})}</div>`
        : E && id !== egoId ? `<p class="mute">${t("No known tie to {name}.", {name: esc(nm(egoId))})}</p>` : ""}
      <div class="sect">${kin(t("Parents"), x.parents[id] || [])}${kin(t("Spouses"), x.spouses[id] || [])}${kin(t("Children"), x.kids[id] || [])}</div>
      ${gapOf(id) !== "complete" ? `<p style="font-size:13px">${{sex: t("{b}Missing:{_b} sex.", MISSB), dates: t("{b}Missing:{_b} birth date.", MISSB), parents: t("{b}Missing:{_b} parents.", MISSB)}[gapOf(id)]} <a href="#" onclick="personDialog(${id});return false">${t("Fill it in")}</a></p>` : ""}
      <div class="row" style="margin-top:10px"><button class="btn sm pri" onclick="standAs(${id})">${t("Stand here")}</button>
        ${E && id !== egoId ? `<button class="btn sm" onclick="openToward(${id})">${t("My duties toward {name}", {name: esc(nm(id).split(" ")[0])})}</button>` : ""}
        <button class="btn sm" onclick="personDialog(${id})">${t("Edit")}</button>
        <button class="btn sm" onclick="addBetween([${id}]);showTab('between');render()">${t("+ Between")}</button>
        <button class="btn sm" onclick="atlasSel=null;drawAtlas()">${t("Clear")}</button></div>`;
    return;
  }
  el.innerHTML = ATLAS_HELP[atlasView]();
}
const BOUND_BADGE = () => `<span class="badge st-entering">${t("bound")}</span>`;
const ATLAS_HELP = {
  network: () => { const x = IX(), others = Object.entries(x.size).filter(([c]) => +c !== x.main).sort((a, b) => b[1] - a[1]);
    return `<h2>${t("The whole family")}</h2><p class="mute" style="font-size:13px">${t("Every person is a dot; lines join parents to children, double lines join husband and wife (dashed: divorced, dotted: paramour).")}
      ${atlasByYear ? t("Each person sits at the height of their birth year (estimated from kin when no date is recorded), so the generations read from top to bottom.") : ""}
      ${t("Wheel to zoom, drag to move, hover a dot for their nearest kin, click for their card, double-click to stand there.")} ${E ? t("Black ring: {name}.", {name: esc(nm(egoId))}) + " " : ""}${t("Red ring: the Head of the family.")}</p>
      <div class="sect"><h3>${t("Separate from the main tree")}</h3>${others.length ? `<p class="mute" style="font-size:13px">${others.length > 1 ? t("{n} groups are joined to no one in the main tree.", {n: others.length}) : t("{n} group is joined to no one in the main tree.", {n: others.length})} ${t("Link them to their kin, or mark them not of the family.")}</p>` +
        others.slice(0, 25).map(([c, n]) => { const ids = Object.keys(x.comp).filter(i => x.comp[i] === +c).map(Number);
          return `<div class="duty" style="cursor:pointer" onclick="atlasSel=${ids[0]};drawAtlas()"><div class="t"><span>${ids.slice(0, 3).map(i => esc(nm(i))).join(", ")}${n > 3 ? ` +${n - 3}` : ""}</span></div><span class="mute">${n}</span></div>`; }).join("")
        : `<p class="mute">${t("Everyone is joined to the main tree.")}</p>`}</div>`; },
  authority: () => `<h2>${t("Who answers to whom")}</h2><p class="mute" style="font-size:13px">${t("The Head of the family stands over every house. Each card is a house and the man who acts at its head; inside are those in his keeping.")}
      ${t("{bound} marks a house kept by a kinsman bound to act for it.", {bound: BOUND_BADGE()})} ${t("Amber chips are under someone {i}by right{_i} who has stepped down or abandoned them.", {i: "<i>", _i: "</i>"})} ${t("A red card is a headless house no kinsman is bound to.")}</p>
      <p class="mute" style="font-size:13px">${t("Click a person for their card; click a head's name to stand in his place.")}</p>`,
  lifelines: () => { const L = lifeGroups();
    return `<h2>${t("Lifelines")}</h2><p class="mute" style="font-size:13px">${t("Each bar runs from birth to death, or to today for the living. Pale bars with no end: dead, year unknown. Dashed: birth year estimated from kin.")}
      ${t("Hover the chart to see who was alive in a given year. The groups below are the stages of life the duties turn on; click one to pick them out.")}</p>
      ${Object.entries(L).map(([k, g]) => `<div class="duty" style="cursor:pointer" onclick="lifeBand=lifeBand==='${k}'?null:'${k}';drawAtlas()"><div class="t"><span>${lifeBand === k ? "<b>" : ""}${esc(g.label)}${lifeBand === k ? "</b>" : ""}</span><span class="src">${esc(g.why)}</span></div><b>${g.ids.length}</b></div>
        ${lifeBand === k ? `<div style="font-size:13px;margin:4px 0 10px">${g.ids.map(i => `<a href="#" onclick="atlasSel=${i};drawAtlas();return false">${esc(nm(i))}</a>${ageOf(i) != null ? ` <span class="mute">${ageOf(i)}</span>` : ""}`).join(" · ") || `<span class="mute">${t("no one")}</span>`}</div>` : ""}`).join("")}`; },
};

/* Network: the whole family, positioned by a small force layout (cached until the state changes) */
function drawNetwork(ids) {
  const host = $("#atlas"), x = IX(), set = new Set(ids);
  const key = ids.join(",") + "|" + atlasByYear;
  if (!NETPOS || NETPOS.key !== key || NETPOS.S !== S) NETPOS = {key, S, pos: netLayout(ids, x)};
  const pos = NETPOS.pos, YS = 7;
  const cy = Object.values(pos).map(p => p.y), cx = Object.values(pos).map(p => p.x);
  const bx = {x: Math.min(...cx) - 40, y: Math.min(...cy) - 40, w: Math.max(...cx) - Math.min(...cx) + 140, h: Math.max(...cy) - Math.min(...cy) + 80};
  let s = `<svg>`;
  if (atlasByYear) {
    const y0 = Math.min(...ids.map(i => x.est[i] ?? 9999)), y1 = Math.max(...ids.map(i => x.est[i] ?? 0));
    for (let y = Math.ceil(y0 / 25) * 25; y <= y1; y += 25) { const yy = (y - 1900) * YS;
      s += `<line class="grid" x1="${bx.x - 2000}" x2="${bx.x + bx.w + 2000}" y1="${yy}" y2="${yy}"/><text class="axislab" x="${bx.x}" y="${yy - 4}">${y}</text><text class="axislab" x="${bx.x + bx.w - 30}" y="${yy - 4}">${y}</text>`; }
    const now = (THIS_YEAR - 1900) * YS;
    s += `<line class="nowline" x1="${bx.x - 2000}" x2="${bx.x + bx.w + 2000}" y1="${now}" y2="${now}"/><text class="axislab" x="${bx.x + 40}" y="${now - 4}">${t("today")}</text>`;
  }
  for (const l of S.links) { const a = pos[l.parent_id], b = pos[l.child_id]; if (!a || !b) continue;
    s += `<path class="nl" data-a="${l.parent_id}" data-b="${l.child_id}" d="M${a.x.toFixed(1)} ${a.y.toFixed(1)}C${a.x.toFixed(1)} ${((a.y + b.y) / 2).toFixed(1)} ${b.x.toFixed(1)} ${((a.y + b.y) / 2).toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}"/>`; }
  for (const u of S.unions) { const a = pos[u.a_id], b = pos[u.b_id]; if (!a || !b) continue;
    s += `<line class="nu ${u.status}" data-a="${u.a_id}" data-b="${u.b_id}" x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}"/>`; }
  const top = theHead();
  for (const id of ids) { const p = P(id), q = pos[id], alive = !dead(p), r = alive ? 6 : 4.5;
    s += `<g class="nn${alive ? " alive" : ""}${atlasSel === id ? " sel" : ""}${faded(id) ? " faded" : ""}" data-id="${id}" transform="translate(${q.x.toFixed(1)},${q.y.toFixed(1)})">
      <title>${esc(p.name)} ${esc(life(p))}${E && E.rels[id] ? " — " + esc(E.rels[id].them.en) : ""}</title>
      ${id === egoId ? `<circle r="${r + 5}" class="ring ego"/>` : ""}${id === top ? `<circle r="${r + 3}" class="ring head"/>` : ""}
      <circle r="${r}" style="fill:${lensColor(id)}"${standing(p) === "entering" ? ' stroke-dasharray="2 2"' : ""}/>
      <text x="${r + 3}" y="3.5">${esc(clip(p.name, 22))}</text></g>`; }
  host.innerHTML = s + `</svg>`;
  const svg = host.querySelector("svg"), by = {};
  svg.querySelectorAll(".nl,.nu").forEach(e => { (by[e.dataset.a] ||= []).push([e, e.dataset.b]); (by[e.dataset.b] ||= []).push([e, e.dataset.a]); });
  host.querySelectorAll(".nn").forEach(n => {
    const id = n.dataset.id;
    n.onmouseenter = () => { svg.classList.add("focus"); n.classList.add("hi");
      for (const [e, o] of by[id] || []) { e.classList.add("hi"); const m = svg.querySelector(`.nn[data-id="${o}"]`); if (m) m.classList.add("hi"); } };
    n.onmouseleave = () => { svg.classList.remove("focus"); svg.querySelectorAll(".hi").forEach(e => e.classList.remove("hi")); };
    n.onclick = () => { atlasSel = +id; drawAtlas(); };
    n.ondblclick = () => standAs(+id);
  });
  const f = (E && pos[egoId]) || null;
  zoomable(host, "net" + key, bx, recenterAtlas, f);
  recenterAtlas = false;
  return ids;
}
function netLayout(ids, x) {
  const n = ids.length, idx = {}, YS = 7;
  ids.forEach((id, i) => idx[id] = i);
  const X = new Float64Array(n), Y = new Float64Array(n), TY = new Float64Array(n), VX = new Float64Array(n), VY = new Float64Array(n);
  const lines = {}; let li = 0;
  ids.forEach((id, i) => { const l = x.lineOf(id); if (!(l in lines)) lines[l] = li++;
    const seed = (id * 9301 + 49297) % 233280 / 233280;
    X[i] = (lines[l] % 12) * 90 + seed * 80; TY[i] = ((x.est[id] ?? 1950) - 1900) * YS; Y[i] = atlasByYear ? TY[i] : seed * 600; });
  const LAB = ids.map(id => !dead(P(id)));
  const springs = [];
  for (const l of S.links) if (l.parent_id in idx && l.child_id in idx) springs.push([idx[l.parent_id], idx[l.child_id], 70, 0.04]);
  for (const u of S.unions) if (u.a_id in idx && u.b_id in idx) springs.push([idx[u.a_id], idx[u.b_id], 26, 0.2]);
  const iters = n > 300 ? 260 : 340;
  for (let t = 0; t < iters; t++) {
    const alpha = 1 - t / iters;
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      let dx = X[i] - X[j], dy = Y[i] - Y[j]; const d2 = dx * dx + dy * dy;
      if (d2 > 90000) continue;
      if (d2 < 0.01) { dx = 0.1 * (i - j); dy = 0; }
      const f = 700 / Math.max(d2, 60);
      VX[i] += dx * f * 0.05; VX[j] -= dx * f * 0.05;
      if (!atlasByYear) { VY[i] += dy * f * 0.05; VY[j] -= dy * f * 0.05; }
    }
    if (atlasByYear && t > iters * 0.3) for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const dy = Y[i] - Y[j]; if (dy > 13 || dy < -13) continue;
      const gap = LAB[i] || LAB[j] ? 96 : 16, dx = X[i] - X[j];
      if (dx < gap && dx > -gap) { const push = (gap - Math.abs(dx)) * 0.25 * (dx >= 0 ? 1 : -1) || 1; X[i] += push; X[j] -= push; }
    }
    for (const [a, b, L, k] of springs) { const dx = X[b] - X[a], dy = Y[b] - Y[a], d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - L) * k / d;
      VX[a] += dx * f; VX[b] -= dx * f; if (!atlasByYear) { VY[a] += dy * f; VY[b] -= dy * f; } }
    for (let i = 0; i < n; i++) {
      VX[i] -= X[i] * 0.0008;                                   // a gentle pull to the middle
      if (atlasByYear) { Y[i] = TY[i]; VY[i] = 0; } else VY[i] -= (Y[i] - TY[i]) * 0.002;
      X[i] += Math.max(-30, Math.min(30, VX[i] * alpha)); Y[i] += Math.max(-30, Math.min(30, VY[i] * alpha));
      VX[i] *= 0.55; VY[i] *= 0.55;
    }
  }
  if (atlasByYear) for (let t = 0; t < 80; t++) {          // last, part any names still sitting on one another
    let moved = 0;
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      if (Math.abs(Y[i] - Y[j]) > 13) continue;
      const gap = LAB[i] || LAB[j] ? 100 : 14, dx = X[i] - X[j];
      if (Math.abs(dx) < gap) { const push = (gap - Math.abs(dx)) / 2 * (dx > 0 || (dx === 0 && i < j) ? 1 : -1); X[i] += push; X[j] -= push; moved++; }
    }
    if (!moved) break;
  }
  const pos = {}; ids.forEach((id, i) => pos[id] = {x: X[i], y: Y[i]});
  return pos;
}

/* Authority: the Head of the family over every house, and who is in each man's keeping */
function drawAuthority() {
  const host = $("#atlas"), top = theHead(), living = Object.values(S.people).filter(p => !dead(p) && ofFamily(p.id)).map(p => p.id);
  const keep = {}, headless = [];
  for (const id of living) { const h = S.heads[id];
    if (h == null) { headless.push(id); continue; }
    if (h !== id) (keep[h] ||= []).push(id); }
  const heads = [...new Set([...Object.keys(keep).map(Number), ...living.filter(isHouseHead)])].filter(h => P(h));
  const minors = ids => ids.filter(i => ageOf(i) != null && ageOf(i) < 18).length, elders = ids => ids.filter(i => ageOf(i) != null && ageOf(i) >= 75).length;
  const chip = (id, extra = "") => { const p = P(id); return `<span class="pchip${p.sex === "f" ? " f" : ""}${standing(p) ? " st-" + standing(p) : ""}${id === egoId ? " is-ego" : ""}${atlasSel === id ? " picked" : ""} ${extra}" data-id="${id}" onclick="atlasSel=${id};drawAtlas()" ondblclick="standAs(${id})" title="${esc(p.name)} ${esc(life(p))}">
    <b style="font-weight:600">${esc(p.name)}</b><small>${ageOf(id) != null ? ageOf(id) : ""}</small></span>`; };
  const card = h => {
    const ms = (keep[h] || []).sort((a, b) => (IX().est[a] ?? 9999) - (IX().est[b] ?? 9999));
    const bound = ms.filter(i => S.bound[i]), byRight = ms.filter(i => i in S.heads_right && S.heads_right[i] !== h && !S.bound[i]);
    const own = ms.filter(i => !bound.includes(i) && !byRight.includes(i));
    const p = P(h), mine = (E && (h === egoId || ms.includes(egoId)));
    return `<div class="hcard${h === top ? " top" : ""}${mine ? " mine" : ""}${P(h).headship ? " gone" : ""}" data-n="${ms.length}">
      <div class="hhead"><a href="#" onclick="standAs(${h});return false"><b>${esc(p.name)}</b></a> <small class="mute">${ageOf(h) ?? ""}</small>
        ${h === top ? `<span class="badge" style="background:var(--seal)">${t("Head of the family")}</span>` : ""}${gone(h)}
        <div class="mute" style="font-size:12px">${ms.length ? `${t("{n} in his keeping", {n: ms.length})}${minors(ms) ? ` · ${t("{n} under 18", {n: minors(ms)})}` : ""}${elders(ms) ? ` · ${t("{n} aged 75+", {n: elders(ms)})}` : ""}` : t("his own house; no one else in his keeping")}</div></div>
      ${own.length ? `<div class="chips">${own.map(i => chip(i)).join("")}</div>` : ""}
      ${byRight.length ? `<div class="hsub">${t("acting for another, who by right heads them:")}</div><div class="chips">${byRight.map(i => chip(i, "byright")).join("")}</div>
        <div class="mute" style="font-size:12px">${t("by right: {names}", {names: [...new Set(byRight.map(i => S.heads_right[i]))].map(r => esc(nm(r)) + (P(r) && P(r).headship ? " (" + esc(label("headship", P(r).headship)) + ")" : "")).join(", ")})}</div>` : ""}
      ${bound.length ? `<div class="hsub">${t("{bound} by kinship to act as head for:", {bound: BOUND_BADGE()})}</div><div class="chips">${bound.map(i => chip(i, "bound")).join("")}</div>` : ""}
    </div>`; };
  const sorted = heads.filter(h => h !== top).sort((a, b) => (keep[b] || []).length - (keep[a] || []).length || nm(a).localeCompare(nm(b)));
  const busy = heads.filter(h => (keep[h] || []).length >= 8);
  const left = living.filter(i => P(i).headship);
  host.innerHTML = `<div class="auth">
    <div class="astats">
      <div class="tile"><b>${heads.length}</b><span>${t("houses with a man acting at their head")}</span></div>
      <div class="tile${Object.keys(S.bound).length ? " warn" : ""}"><b>${Object.keys(S.bound).length}</b><span>${t("souls kept by a kinsman bound to act")}</span></div>
      <div class="tile${left.length ? " warn" : ""}"><b>${left.length}</b><span>${t("men who have stepped down or abandoned their family")}</span></div>
      <div class="tile${headless.length ? " bad" : ""}"><b>${headless.length}</b><span>${t("in a headless house no kinsman is bound to")}</span></div>
      <div class="tile"><b>${busy.length}</b><span>${busy.length ? t("men keeping eight or more: {names}", {names: busy.map(h => esc(nm(h))).join(", ")}) : t("men keeping eight or more")}</span></div></div>
    ${top != null ? `<div class="topwrap">${card(top)}</div><div class="trunk"></div>` : `<div class="hcard bad">${t("{b}No Head of the family:{_b} no living man found. Name one on the Clan tab.", {b: "<b>", _b: "</b>"})}</div>`}
    <div class="hgrid">${sorted.map(card).join("")}</div>
    ${headless.length ? `<div class="hcard bad"><div class="hhead"><b>${t("Headless, and no kinsman bound")}</b><div class="mute" style="font-size:12px">${t("These fall directly under the Head of the family. Record a husband, father or brother, or a household, to set them under a man.")}</div></div><div class="chips">${headless.map(i => chip(i)).join("")}</div></div>` : ""}
  </div>`;
  return living;
}

/* Lifelines: a bar per life, grouped by generation (from whoever you stand as) or by line */
function lifeGroups() {
  const x = IX(), living = Object.values(S.people).filter(p => !dead(p)).map(p => p.id);
  return {
    minors: {label: t("Children under 18"), why: t("under a father's or guardian's care"), ids: living.filter(i => ageOf(i) != null && ageOf(i) < 18)},
    coming: {label: t("Coming of age within two years"), why: t("turning 18 by {year}", {year: THIS_YEAR + 2}), ids: living.filter(i => ageOf(i) != null && ageOf(i) >= 16 && ageOf(i) < 18)},
    elders: {label: t("Elders, 75 and older"), why: t("the care of elders"), ids: living.filter(i => ageOf(i) != null && ageOf(i) >= 75)},
    undated: {label: t("Living, with no birth date"), why: t("fill these in so the rules about age apply"), ids: living.filter(i => x.yr[i] == null)},
  };
}
const GEN_NAME = g => {
  if (g === 0) return t("own generation");
  if (g > 0) return [null, t("parents’ generation"), t("grandparents’ generation"), t("great-grandparents’ generation"), t("great-great-grandparents’ generation"), t("great-great-great-grandparents’ generation")][g]
    || (LANG === "en" ? `${"great-".repeat(g - 2)}grandparents’ generation` : t("{n}× great-grandparents’ generation", {n: g - 2}));
  return [null, t("children’s generation"), t("grandchildren’s generation"), t("great-grandchildren’s generation"), t("great-great-grandchildren’s generation"), t("great-great-great-grandchildren’s generation")][-g]
    || (LANG === "en" ? `${"great-".repeat(-g - 2)}grandchildren’s generation` : t("{n}× great-grandchildren’s generation", {n: -g - 2}));
};
function drawLifelines(ids) {
  const host = $("#atlas"), x = IX(), W = Math.max(host.clientWidth - 24, 700), GUT = 190, RH = 17;
  const band = lifeBand ? new Set(lifeGroups()[lifeBand].ids) : null;
  const known = ids.filter(i => x.est[i] != null);
  if (!known.length) { host.innerHTML = `<p class="mute" style="padding:20px">${t("No birth years to draw.")}</p>`; return ids; }
  const groupOf = id => E ? (E.rels[id] ? GEN_NAME(E.rels[id].them.gen) : id === egoId ? GEN_NAME(0) : t("no known tie")) : lineName(x.lineOf(id));
  const gorder = id => E ? (E.rels[id] ? -E.rels[id].them.gen : id === egoId ? 0 : 99) : 0;
  const rows = known.slice().sort((a, b) => gorder(a) - gorder(b) || groupOf(a).localeCompare(groupOf(b)) || x.est[a] - x.est[b]);
  const y0 = Math.floor((Math.min(...rows.map(i => x.est[i])) - 3) / 10) * 10, y1 = THIS_YEAR + 4;
  const sx = y => GUT + (y - y0) / (y1 - y0) * (W - GUT - 20);
  let s = "", yy = 34, last = null;
  const step = [10, 20, 25, 50, 100].find(t => (W - GUT) / ((y1 - y0) / t) >= 48) || 100;
  for (let y = Math.ceil(y0 / step) * step; y <= y1; y += step) s += `<line class="grid" x1="${sx(y)}" x2="${sx(y)}" y1="22" y2="__H__"/><text class="axislab" x="${sx(y)}" y="14" text-anchor="middle">${y}</text>`;
  s += `<rect class="band" x="${sx(THIS_YEAR - 18)}" width="${sx(THIS_YEAR) - sx(THIS_YEAR - 18)}" y="22" height="__HH__"><title>${t("born in the last 18 years: under 18 today")}</title></rect>
    <line class="nowline" x1="${sx(THIS_YEAR)}" x2="${sx(THIS_YEAR)}" y1="18" y2="__H__"/><text class="axislab" x="${sx(THIS_YEAR) + 3}" y="30">${t("today")}</text>`;
  for (const id of rows) {
    const g = groupOf(id);
    if (g !== last) { yy += last == null ? 0 : 8; s += `<text class="ghead" x="6" y="${yy + 10}">${esc(g)}</text>`; yy += RH; last = g; }
    const p = P(id), b = x.est[id], est = x.yr[id] == null, alive = !dead(p), d = alive ? THIS_YEAR : x.dy[id];
    const end = d ?? Math.min(b + 70, THIS_YEAR), col = lensColor(id), off = (band && !band.has(id)) || faded(id);
    const age = alive ? (est ? "" : `, ${THIS_YEAR - b}`) : d ? ", " + t("died at {n}", {n: d - b}) : "";
    s += `<g class="lrow${off ? " faded" : ""}${atlasSel === id ? " sel" : ""}" data-id="${id}" transform="translate(0,${yy})">
      <rect class="hit" x="0" y="-2" width="${W}" height="${RH}"/>
      <text class="lname" x="${GUT - 8}" y="10" text-anchor="end">${esc(clip(p.name, 26))}</text>
      <rect class="life${est ? " est" : ""}${!alive && !d ? " open" : ""}" x="${sx(b)}" y="2" width="${Math.max(3, sx(end) - sx(b))}" height="10" rx="3" style="fill:${col};stroke:${col}"/>
      <title>${esc(p.name)} ${esc(life(p))}${est ? " " + t("(born about {y}, estimated)", {y: b}) : ""}${age}</title></g>`;
    yy += RH;
  }
  const H = yy + 10;
  host.innerHTML = `<svg class="lifesvg" width="${W}" height="${H}">${s.replaceAll("__HH__", H - 22).replaceAll("__H__", H)}<line class="cross" y1="18" y2="${H}" x1="-10" x2="-10"/><text class="crosslab" y="12" x="-10"></text></svg>`;
  const svg = host.querySelector("svg"), cross = svg.querySelector(".cross"), lab = svg.querySelector(".crosslab");
  svg.onmousemove = e => { const r = svg.getBoundingClientRect(), px = e.clientX - r.left;
    if (px < GUT) { cross.setAttribute("x1", -10); cross.setAttribute("x2", -10); lab.textContent = ""; return; }
    const year = Math.round(y0 + (px - GUT) / (W - GUT - 20) * (y1 - y0));
    const n = rows.filter(i => x.est[i] <= year && (!dead(P(i)) ? year <= THIS_YEAR : (x.dy[i] ?? x.est[i] + 70) >= year)).length;
    cross.setAttribute("x1", px); cross.setAttribute("x2", px); lab.setAttribute("x", px + 4); lab.textContent = t("{year}: {n} alive", {year, n}); };
  svg.querySelectorAll(".lrow").forEach(n => { n.onclick = () => { atlasSel = +n.dataset.id; drawAtlas(); }; n.ondblclick = () => standAs(+n.dataset.id); });
  return rows;
}

/* ---------- Between: the circle of ties ---------- */
function betweenCircle(ids, B) {
  const n = ids.length, R = Math.max(110, n * 22), pos = {};
  ids.forEach((id, i) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; pos[id] = {x: R * Math.cos(a), y: R * Math.sin(a), a}; });
  let s = "";
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
    const a = ids[i], b = ids[j], ab = (B[a] || {})[b], ba = (B[b] || {})[a];
    if (!ab && !ba) continue;
    const st = [ab && ab.bond && ab.bond.state, ba && ba.bond && ba.bond.state].filter(Boolean).sort((p, q) => SEV[q] - SEV[p])[0] || "unset";
    const w = 1.2 + Math.min(((ab ? ab.owe.length : 0) + (ba ? ba.owe.length : 0)) / 12, 5);
    const on = betweenCell && ((betweenCell[0] === a && betweenCell[1] === b) || (betweenCell[0] === b && betweenCell[1] === a));
    s += `<path class="bline s-${st}${on ? " on" : ""}" style="stroke-width:${w.toFixed(1)}" d="M${pos[a].x.toFixed(1)} ${pos[a].y.toFixed(1)}Q0 0 ${pos[b].x.toFixed(1)} ${pos[b].y.toFixed(1)}" onclick="betweenCell=[${a},${b}];drawBetween()">
      <title>${esc(nm(a))} → ${esc(nm(b))}: ${esc(ab ? ab.en : "?")}${ab && ab.bond ? " (" + bondWord(ab.bond.state) + ")" : ""}\n${esc(nm(b))} → ${esc(nm(a))}: ${esc(ba ? ba.en : "?")}${ba && ba.bond ? " (" + bondWord(ba.bond.state) + ")" : ""}\n${t("click for the duties")}</title></path>`;
  }
  for (const id of ids) { const q = pos[id], right = Math.cos(q.a) >= -0.01, p = P(id);
    s += `<g class="wnode${dead(p) ? " dead" : ""}${standing(p) ? " st-" + standing(p) : ""}" transform="translate(${q.x.toFixed(1)},${q.y.toFixed(1)})" onclick="standAs(${id})"><title>${t("{name}: click to stand here", {name: esc(p.name)})}</title><circle class="dot" r="8"/>
      <text class="nm" x="${right ? 13 : -13}" y="4" text-anchor="${right ? "start" : "end"}">${esc(clip(p.name, 22))}</text></g>`; }
  const M = R + 170;
  return `<svg class="bcircle" viewBox="${-M} ${-R - 30} ${2 * M} ${2 * R + 60}" style="max-width:${2 * M}px">${s}</svg>`;
}

/* ---------- Clan: what needs attention ---------- */
function attentionTiles(R) {
  const living = Object.values(S.people).filter(p => !dead(p) && ofFamily(p.id)), x = IX();
  const headless = living.filter(p => S.heads[p.id] == null).length, bound = Object.keys(S.bound).filter(k => ofFamily(+k)).length, left = living.filter(p => p.headship).length;
  let unjudged = null, open = null;
  if (E) { const close = shownClose();
    unjudged = close.filter(id => !E.rels[id].bond_out).length;
    open = close.reduce((n, id) => n + dutyCounts(E.rels[id].owe, E.rels[id].marks_out).open, 0); }
  const undated = living.filter(p => x.yr[p.id] == null).length, nosex = Object.values(S.people).filter(p => p.sex !== "m" && p.sex !== "f").length;
  const islands = Object.keys(x.size).length - 1;
  const tile = (n, label, go, cls) => n == null ? "" : `<div class="tile ${n ? cls : "ok"}" onclick="${go}" title="${t("open")}"><b>${n}</b><span>${label}</span><i>→</i></div>`;
  return `<div class="card"><h3>${t("What needs attention")}</h3><div class="astats">
    ${tile(R.torn.length, t("bonds torn (strained, broken or severed)"), "document.querySelector('#clan .torn')?.scrollIntoView({behavior:'smooth'})", "bad")}
    ${tile(R.failing.length, t("duties marked failing or not doing well"), "document.querySelector('#clan .failing')?.scrollIntoView({behavior:'smooth'})", "bad")}
    ${E ? tile(unjudged, t("of {name}’s close living kin with no bond judged", {name: esc(nm(egoId))}), "goStand('web','bond')", "warn") : ""}
    ${E ? tile(open, t("duties {name} owes close kin, not yet examined", {name: esc(nm(egoId))}), "goStand('duties')", "warn") : ""}
    ${tile(headless, t("living in a headless house no kinsman is bound to"), "goAtlas('authority')", "bad")}
    ${tile(bound, t("kept by a kinsman bound to act"), "goAtlas('authority')", "warn")}
    ${tile(left, t("men who have stepped down or abandoned their family"), "goAtlas('authority')", "warn")}
    ${tile(undated, t("living people with no birth date"), "lifeBand='undated';goAtlas('lifelines')", "warn")}
    ${tile(nosex, t("people whose sex is unknown"), "lens='gaps';goAtlas('network')", "warn")}
    ${tile(islands, t("groups not joined to the main tree"), "atlasSel=null;goAtlas('network')", "warn")}
    ${tile((S.rulings || []).filter(r => r.status === "proposed" || r.status === "revise").length, t("rulings awaiting your word"), "showTab('rulings');render()", "warn")}
  </div></div>`;
}
function shownClose() { return Object.keys(E.rels).map(Number).filter(id => CLOSE.has(E.rels[id].them.path) && !dead(P(id))); }
function goAtlas(v) { atlasView = v; atlasSel = null; recenterAtlas = true; showTab("atlas"); render(); }
function goStand(v, l) { if (l) { lens = l; lensPick = "unset"; } view = v; recenter = true; showTab("stand"); render(); }
