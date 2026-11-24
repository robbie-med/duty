/* The Way in four languages: English, Korean, Traditional and Simplified Chinese.
 *
 * t("English text {name}", {name}) gives the text in the reader's language: the English itself is the key, so the
 * English site needs no dictionary and a missing translation falls back to English. Dictionaries are
 * web/i18n/<locale>.json: {"English text {name}": "번역 {name}"}.
 * Kinship terms are never translated: the English relation stays English, Korean terms stay in hangul and Chinese
 * terms in characters, whatever the language of the page. Quotations stay in the language of their source.
 * The text of duties and rulings comes translated from the server (way/i18n/<locale>.json), unless the family has
 * reworded it, when its own words are shown. */
const LOCALES = {en: "English", ko: "한국어", "zh-Hant": "繁體中文", "zh-Hans": "简体中文"};
let LANG = (() => {
  try { const v = localStorage.getItem("way-lang"); if (v && LOCALES[v]) return v; } catch (e) { /* private window */ }
  const n = (navigator.language || "en").toLowerCase();
  return n.startsWith("ko") ? "ko" : /^zh-(tw|hk|mo|hant)/.test(n) ? "zh-Hant" : n.startsWith("zh") ? "zh-Hans" : "en";
})();
let DICT = {};
document.documentElement.lang = LANG;

async function loadLang() {
  DICT = {};
  if (LANG !== "en") {
    try { DICT = await (await fetch("/i18n/" + LANG + ".json", {cache: "no-cache"})).json(); } catch (e) { DICT = {}; }
  }
  document.documentElement.lang = LANG;
  translateStatic(document);
}
function t(key, vars) {
  let s = (LANG !== "en" && DICT[key]) || key;
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
  return s;
}
/* fixed text in the page's own HTML: <button data-i18n>Stand here</button>, placeholder/title via data-i18n-attr */
function translateStatic(root) {
  root.querySelectorAll("[data-i18n]").forEach(el => {
    if (!el.hasAttribute("data-i18n-en")) el.setAttribute("data-i18n-en", el.textContent.trim());   // the English, kept once
    const key = el.dataset.i18nKey || el.getAttribute("data-i18n-en");                           // a key of its own where one word means two things
    el.textContent = (LANG !== "en" && DICT[key]) || el.getAttribute("data-i18n-en");
  });
  root.querySelectorAll("[data-i18n-attr]").forEach(el => {
    for (const a of el.dataset.i18nAttr.split(",").map(x => x.trim()).filter(Boolean)) {
      const k = "data-i18n-orig-" + a;                 // the English, kept once, so a later language starts from it
      if (!el.hasAttribute(k)) el.setAttribute(k, el.getAttribute(a) || "");
      el.setAttribute(a, t(el.getAttribute(k)));
    }
  });
}
async function setLang(lang) {
  if (!LOCALES[lang]) return;
  LANG = lang;
  try { localStorage.setItem("way-lang", lang); } catch (e) { /* private window */ }
  await loadLang();
  if (typeof onLangChange === "function") onLangChange();
}
const langOptions = () => Object.entries(LOCALES).map(([k, v]) => `<option value="${k}"${k === LANG ? " selected" : ""}>${v}</option>`).join("");

/* duties, rulings and labels in the reader's language (the server sends what it has) */
const dtext = d => (d && d.i18n && d.i18n[LANG]) || (d ? d.text : "");
const rtext = (r, field) => (r && r.i18n && r.i18n[LANG] && r.i18n[LANG][field]) || (r ? r[field] : "");
const gpoint = (r, i) => (r && r.i18n && r.i18n[LANG] && r.i18n[LANG].points && r.i18n[LANG].points[i]) || (r && r.grounds[i] ? r.grounds[i].point : "");
const label = (kind, key) => t((S && S.meta && S.meta[kind] && S.meta[kind][key]) || key);   // roles, spheres, traditions, standings…
/* Chinese kinship terms in the script of the page: traditional for 繁體中文 and 한국어 (hanja), simplified otherwise */
const zhScript = () => (LANG === "zh-Hant" || LANG === "ko" ? "hant" : "hans");
/* the kinship terms of the family's own peoples beside the English one (Korean in hangul, Chinese in characters) */
const native = rel => !rel ? "" : ((S && S.native_langs) || ["ko"]).map(l => l === "ko" ? rel.ko_term : zhScript() === "hant" ? rel.zh_hant : rel.zh).filter(Boolean).join(" · ");
/* the reason the server gives for a man's place in a line of succession ("her husband", "with the mother: father"…) */
function whyText(why) {
  if (!why) return "";
  let m = why.match(/^with the mother: (.*)$/);
  if (m) return t("with the mother: {why}", {why: whyText(m[1])});
  m = why.match(/^bound by kinship: nearest kinsman \((.*)\)$/);
  if (m) return t("bound by kinship: nearest kinsman ({rel})", {rel: m[1]});
  m = why.match(/^bound by kinship: head of the house of (.*) \((.*)\)$/);
  if (m) return t("bound by kinship: head of the house of {name} ({rel})", {name: m[1], rel: m[2]});
  return t(why);
}
