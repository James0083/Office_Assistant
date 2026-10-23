# PyInstaller 빌드 설정 — macOS 와 Windows 공용
#   macOS  : dist/수학의힘 행정도우미.app
#   Windows: dist/수학의힘 행정도우미.exe  (파일 하나)
# PyInstaller 는 교차 빌드가 안 되므로 각 OS 에서 따로 빌드해야 한다.
import sys

NAME = "수학의힘 행정도우미"

a = Analysis(
    ["app.py"],
    datas=[("ui.html", ".")],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False)
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME)
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        bundle_identifier="kr.mathpower.admin-helper",
        info_plist={"NSHighResolutionCapable": True},
    )
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, name=NAME, console=False)
