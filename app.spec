# PyInstaller 빌드 설정 — macOS 와 Windows 공용
#   macOS  : dist/수학의힘 행정도우미.app
#   Windows: dist/수학의힘 행정도우미.exe  (파일 하나)
# PyInstaller 는 교차 빌드가 안 되므로 각 OS 에서 따로 빌드해야 한다.
#
# Copyright (c) 2026 유재원 (GitHub: James0083). All rights reserved.
import sys

NAME      = "수학의힘 행정도우미"
VERSION   = "1.0.1"
AUTHOR    = "유재원 (GitHub: James0083)"
COPYRIGHT = "Copyright (c) 2026 유재원 (GitHub: James0083). All rights reserved."

a = Analysis(
    ["app.py"],
    datas=[("ui.html", "."), ("LICENSE", ".")],   # LICENSE 도 앱 안에 함께 넣는다
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
        version=VERSION,
        # Finder 의 '정보 가져오기' 에 표시됨
        info_plist={"NSHighResolutionCapable": True, "NSHumanReadableCopyright": COPYRIGHT},
    )
else:
    # exe 파일 속성 → 자세히 탭에 표시됨
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct)
    nums = tuple(map(int, VERSION.split("."))) + (0,)
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums),
        kids=[
            StringFileInfo([StringTable("041204B0", [   # 한국어, 유니코드
                StringStruct("CompanyName", AUTHOR),
                StringStruct("FileDescription", NAME),
                StringStruct("FileVersion", VERSION),
                StringStruct("InternalName", NAME),
                StringStruct("LegalCopyright", COPYRIGHT),
                StringStruct("OriginalFilename", f"{NAME}.exe"),
                StringStruct("ProductName", NAME),
                StringStruct("ProductVersion", VERSION),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0412, 1200])]),
        ],
    )
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, name=NAME, console=False, version=version_info)
