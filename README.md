# The Way — family structure, roles and duties

The Way shows where each person stands in a family, what they owe and are owed, who heads each house and who
is in whose care, and the state of each bond. Its duties are drawn from Scripture, the Westminster Standards, the
Puritans, English and New England law and custom, Catholic teaching, the classical writers, Confucian texts and
Korean custom, each recorded with its sources and weighed in that order.

It comes with a fictional **example family**: Daniel Whitaker, his Anglo-American father's line and his Korean
mother's line each traced eight generations back, his wife's family three generations back, and brothers, sisters,
uncles, aunts and cousins with the situations the app is built to handle (a Head of the family, a main-line heir,
widows, a headless house kept by a bound kinsman, a man who abandoned his family, an adoption, a divorce, one
drifting away, minors with and without a guardian named, and gaps in the record).

- **Download and run:** take `TheWay-windows.exe`, `TheWay-macos` or `TheWay-linux` from the Releases page and
  double-click it. It starts on your computer and opens in your usual browser; a small window shows it is running
  (close it to stop). Your records stay on your computer, in `%APPDATA%\The Way` (Windows),
  `~/Library/Application Support/The Way` (macOS) or `~/.local/share/the-way` (Linux). The programs are not signed:
  Windows may warn that it "protected your PC" (choose *More info*, then *Run anyway*), and on a Mac right-click it
  and choose *Open* the first time.
- **Stack:** Python 3 standard library + SQLite + vanilla JavaScript (`web/`). No dependencies.
- **Run from source:** `./run.sh serve` (or `python3 app.py`, which also opens the browser), then
  http://127.0.0.1:3517/.
- **Examples, then your own:** until you start your own record, the site shows the example families, one per
  background. *Start your own family* (the banner at the top) begins your own, empty record in `data/family.db`
  (from source) or your user folder (the download); the examples stay out of it. Or import a Gramps tree
  (`./run.sh import-gramps`).

### Backgrounds and languages
The **background** selector (Anglo, Korean, Chinese, Korean-Anglo, Korean-Chinese, Anglo-Chinese) decides which
kinship terms appear beside the English relation: Korean (`way/kinterms.json`: 큰아버지, 외삼촌, 처제…), Chinese
(`way/kinterms.zh.json` and `kinterms.zh-hant.json`: 伯父, 舅舅, 堂哥, 外甥…), both, or neither. The Chinese terms tell a
brother's child (侄) from a sister's (外甥) and an elder cousin from a younger (堂哥 / 堂弟). While you look at the
examples it also switches between six example families, one of each. Every tradition applies to every family,
whatever its background.

The **language** selector sets the whole site in English, 한국어, 繁體中文 or 简体中文. Interface phrases are in
`web/i18n/<locale>.json`, keyed by the English (`web/i18n.js`); the seeded duties and rulings are in
`way/i18n/<locale>.json`, keyed by their row in the seed. A duty the family has reworded shows its own words in every
language. Kinship terms are never translated: the English relation stays English, Korean terms stay in hangul and
Chinese terms in characters (traditional for 繁體中文 and 한국어, simplified otherwise). Quotations stay in the
language of their source.

**About** (a tab on the full site, a section under Clan on the phone) and the welcome shown on a first visit are in
`web/about.js`, in all four languages.

### Building the downloads
`pyinstaller the-way.spec` builds `dist/TheWay` (`TheWay.exe` on Windows) on the machine it runs on. Pushing a tag
`v*` to GitHub has `.github/workflows/build.yml` build all three on GitHub's machines and attach them to the release.

## How it works
Only three facts are stored: **people**, **marriages**, **parent-child links**. `kin.py` derives the rest
for any two people: the English relation, the Korean term of address (`way/kinterms.json`), generation,
degree (촌), and the role tags (father, eldest_son, daughter_in_law, superior…) that duties attach to.
A person's **standing** (being received, estranged, cut off) is a role tag too, so duties can be written
toward, or for, someone in that standing.

**Headship is derived and is always a living man.** Every house is under one: the husband; for a widow,
her eldest living son; for the unmarried, the father, then the mother's husband, then the eldest living
brother, then the father's father. There is always one **Head of the family**: the man you name on the Clan
tab, or failing that the senior living man of the father's line (oldest living generation, eldest first):
your own line once "This is me" is set, until then the largest male line in the tree. It is the same Head
whoever you stand as. Re-importing from Gramps never blanks a birth or death entered here.

**Order of succession and acting heads.** Every house has an ordered line, shown on each person's panel:
husband; the man whose household one lives in; a widow's grown sons; father; mother's husband; for a child
under 18, whoever heads the mother; brothers (for a man, only elder ones); father's father. A man can be
marked as having *stepped down* or *abandoned his family*: he stays head **by right** and keeps the duties
he left, and the next man in line who still holds is the **acting head**. The Head of the family has the
same kind of line (Clan tab). Adoption is permanent: a son adopted out belongs to his adoptive father's line
and leaves his birth house's succession. A house with no man left to act in its own line is **headless**,
and a kinsman is **bound** to act for it (the nearer kinsman of Lev 25:25, 48-49; Ruth 3:12; 4:1-6): kin are
taken nearest first (fewest steps, blood before marriage); within the nearest tier the eldest man is bound,
either a grown kinsman himself or the man acting at the head of a kinswoman's house. Only if no kinsman is
bound does the house fall to the Head of the family. A man who abandons his own house is not put under another. Separately, "carried by" records who actually bears someone's load without
making him their head. "Birth order" orders brothers and sisters whose dates are unknown.
The server refuses a Head who is not a living man. People with no dates are treated as dead when their
relatives' dates show they lived long ago; anyone born 1915 or later with no death recorded counts as living.

**The Way** is a list of duties, each `from role → to role`, with a sphere, a tradition
(Scripture, Westminster, Puritan, Catholic, Confucian, Korean custom, Our house) and a citation.
`way/duties.json` seeds an empty database; every seeded duty is a **draft** until confirmed in the app.

## Screens
- **Stand here** — the web: one person in the center, a spoke out to each relationship, colored by
  the state of the bond; people reached through someone sit further out on that person's spoke. (A
  generation-row *Tree* is the alternative view.) Click a person for the roles held toward them, what each
  owes the other, the bond each way and their standing; double-click to stand in their place. *Examine*
  walks one person through every duty they owe. *Print sheet* gives a one-page handout (confirmed duties
  only; assessments only if you choose).
  Four drawings of the same people: **Web**, **Tree**, **Fan** (ancestors above, descendants below; a
  dashed "+ father / + mother" wedge is a missing parent, click to add one) and **Duties** (a grid of what
  you owe each person by sphere: kept, not doing well, failing, n/a or not yet examined; click a cell to mark those duties, or
  "Examine next"). Every map zooms (wheel, +/−, ⤢ fit) and pans (drag); hovering a person on the Web
  lights the chain of kin back to the center.
- **Color by** (every map shares it): bond with me, my duties examined, side of the family, standing,
  father's line, missing facts. Click a legend entry to pick out just those people.
- **Atlas** — the whole family. *Network*: everyone as a dot at the height of their birth year, with
  parent and marriage lines, and a list of groups not joined to the main tree. *Authority*: the Head of
  the family over every house, who keeps whom, bound kinsmen, men who have left their headship, headless
  houses. *Lifelines*: a bar per life, grouped by generation, with a year crosshair and the stages the
  duties turn on (children under 18, coming of age, elders 75+, living with no birth date).
- **Family map** — the whole house drawn as boxes inside boxes (a couple, their children inside), so there
  are no lines to cross. Each person shows their standing (member, being received, estranged, cut off,
  dead) and the bond with whoever you stand as. Click anyone for your roles and duties toward them.
  Houses fold (▾) and the dot beside each name follows Color by.
- **Between** — pick several people or a household: a circle of their ties (color = the worse bond,
  thickness = what they owe each other), the table of what each is to each, and the duties; judge both
  directions of a bond right there.
- **The Way** — confirm, edit, add and retire duties. Search the books and turn a passage into a duty.
- **Clan** — *What needs attention* (tiles that open the right map), torn bonds, failing duties, roll-ups by sphere and person, households, clan elder, the living web.

**Phone view** (`web/m.html`): phones get it at `/` automatically (the server reads the browser's name; a small
touch screen it misses is sent on by the page itself). Five tabs: *Today* (where you stand, your duties to
those closest, what needs attention), *Family* (tap through parents, spouse, children, brothers and sisters),
*People* (search; close / all kin / not judged / torn / failing), *Examine* (one duty at a time: kept, not doing well, failing or n/a; swipe right
kept, left failing, with undo; what I owe or what they owe me) and *Clan*: **Authority** (the Head of the
family and succession, then every house as a card that opens to who is in that man's keeping, who he acts
for by another's right, who he is bound by kinship to keep; filters and a "who is under whom?" search),
**The clan** (bonds torn, duties failing or not doing well, by sphere and person, standing, households)
and **You** (standing as, the full-site switch). Each person has a page for the bond both ways and the
duties each way. Duties are marked kept, not doing well (stored as `poorly`), failing, or n/a.
`/m` always shows the phone view and `/full` the full site; "Use the full site on this device" sets a
`way_ui=full` cookie, and "Phone view" in the full site's header (touch screens only) clears it.

Deep links (the address bar keeps up as you move): `/#ego=12&sel=30`, `/#ego=12&reach=wide`,
`/#ego=12&view=fan`, `/#tab=atlas&av=authority`, `/#tab=way&q=filial`.
The page is `web/index.html` plus `web/maps.js` (lenses, zoom, Fan, Duties, Atlas, Between circle, attention tiles).


- **For a head** (buttons on a person's page): *Print charge* lists who is under his headship and in his care
  (and, for the Head of the family, the heads of its houses), with room for notes. *Print register* gives the
  house's register back to the great-great-grandparents with dates and graves (and, for the heir and the Head, every
  grave of the family). *If he dies…* shows, without changing anything, who would take up each house he heads or
  keeps, the next Head of the family, and which minors would have no guardian named (set on the child's Edit).
- **Matters before the family** (Clan tab and a person's page): a fault, a dispute, one drifting, or whether to cut
  one off, recorded step by step (privately, with witnesses, before the family, decided, restored) with who acted
  and how it ended; closing one as cut off or restored offers to set the person's standing to match.
- **What is missing** (Clan tab): placeholders, missing birth years, unknown sexes, deaths without dates, minors with
  no guardian named, forebears whose grave is not recorded: the records the headship and duty logic depend on.
- **Reviewing the drafts** (The Way): the drafts a few at a time by role, sources open: confirm, retire with a
  reason, or pass. Print sheets carry confirmed duties only.
- Who is *of the family* (under the Head's authority) is decided once, on the server: the living related to the Head
  by blood or marriage, not as a paramour, and not set outside it. Views of houses and heads use only them.
## Commands
| | |
|---|---|
| `./run.sh serve` | start the server (127.0.0.1:3517; `FAMILY_PORT`, `FAMILY_HOST`, `FAMILY_DB` change it) |
| `python3 app.py` | start and open it in the browser (what the downloads run) |
| `python3 example.py [DB] [--background BG] [--reset]` | write an example family into a database (`--reset` clears the people first) |
| `./run.sh import-gramps [--tree NAME] [--apply]` | import a Gramps tree (dry run without `--apply`; safe to repeat) |
| `./run.sh merge KEEP_ID DROP_ID` | fold a person entered twice into one |
| `./run.sh index` | build the search index of the books in `way/library.json` |
| `./run.sh export-way` | write the current duties to `way/the-way-export.json` |
| `./run.sh test` | the tests |

## The published site (duty.robbiemed.org)
The site at duty.robbiemed.org is GitHub Pages: plain files on the `gh-pages` branch, rebuilt from `main` on every push
(`.github/workflows/pages.yml`, `tools/build_static.py`). It has no server: `web/static-api.js` loads Python in the
visitor's browser (Pyodide) and `static_api.py` answers the page there, exactly as `server.py` would, over the six
example families, read-only. The book search is only in the program itself.

## A public, read-only copy on your own server
Set `PUBLIC_HOST` to the site's host name and serve it on the open port (`FAMILY_HOST=0.0.0.0`) or behind a reverse
proxy that passes the `Host` header. Requests for that host can read everything and change nothing: the server
refuses every write, and the page shows a banner and says so when someone tries. Requests for 127.0.0.1 still edit
normally unless `READ_ONLY=1`. Any other host name is refused. The background selector still works for visitors
(it is a choice of what to look at, not a change). To reset the demo, delete `data/examples/`; each example is
rebuilt the first time it is shown.

## Data and privacy
`data/family.db` holds the tree and every judgment made about named relatives; `data/library.db` is a rebuildable
index of book text. Both are created mode 600 and gitignored. In local use the server answers only on 127.0.0.1 and
refuses requests from other web origins. Gramps files and book folders are only ever read.

## The books
`way/library.json` lists the folders to index for the library search (here, the public-domain texts in
`sources/`). Add your own folders (absolute paths, or relative to this project), then `./run.sh index`. Books you
own but may not publish belong in `sources/private/`, which is gitignored and never indexed for a public copy.

## Mining the sources (`mine.py`, `way/rulings.json`)
`sources/` holds public-domain texts by tradition (Scripture, Westminster, Puritan and Calvin, English and
New England law and custom, Catholic, classical, Confucian, Korean), each folder with a `MANIFEST.json`.
The traditions weigh in the order `way/duties.json` lists them; "Our house" (AI-drafted protocols) weighs least.

- `python3 mine.py extract` has DeepSeek read every passage (key in `.env`, read at call time; it waits out
  DeepSeek's peak hours and stops before the balance runs out). Answers go to `way/mined/extract/*.jsonl`.
- Consolidation (matching findings to existing duties, merging new ones, flagging rites and contested
  practices) was done by hand with an AI assistant, into `way/mined/consolidated.json`; `mine.py consolidate` is the
  DeepSeek fallback.
- `python3 mine.py seed` appends the new duties (as drafts) and the attestations to `way/duties.json` and
  writes `way/mined/review.md`. The seed is append-only: what you change in the app is never overwritten.
- `way/rulings.json` feeds the Rulings tab: the cases against rites to the dead, saints, divination and
  contested practices, and the judgment of every "Our house" protocol. Every quotation in a ruling has been
  checked word for word against its source. Accepting a case retires the practice with its reasons;
  accepting a house judgment keeps, revises or retires that protocol. "Duties the newly read books question"
  works the same way for any duty that further books qualify or contradict: Apply puts in the proposed wording
  (and the passages behind it), or retires the duty.
- Anthologies (A Theology of the Family, the Free Grace Broadcaster issues) count each essay under its own
  author's tradition: `way/mined/authors.json` maps each passage to its author, and `mine.py extract` applies it.
