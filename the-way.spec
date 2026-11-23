# PyInstaller recipe: one file that starts The Way and opens it in the browser.
#   pyinstaller the-way.spec        ->  dist/TheWay(.exe)
import glob
datas = [("web", "web"), ("sources", "sources")]
datas += [(f, "way") for f in glob.glob("way/*.json") if ".bak" not in f]
datas += [(f, "way/i18n") for f in glob.glob("way/i18n/*.json")]
a = Analysis(["app.py"], pathex=["."], datas=datas, hiddenimports=["example", "import_gramps"], excludes=["tkinter", "test", "unittest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="TheWay", console=True, upx=False)
