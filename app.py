"""
수학의힘 행정도우미

화면은 ui.html (HTML/CSS/JS), 창은 pywebview 로 띄운다.
화면 ↔ 파이썬은 Api 클래스의 메서드로만 주고받는다 (window.pywebview.api.*).

데이터는 앱(.app/.exe)과 같은 폴더의 data.json 에 저장한다.
공유 폴더에 앱을 두고 여러 명이 함께 쓸 수 있도록
  - 저장은 항목 하나 단위로, 디스크의 최신 파일에 반영하고 (다른 사람 변경을 덮어쓰지 않음)
  - 같은 항목을 다른 사람이 먼저 바꿨으면 저장을 멈추고 알리며
  - 동시에 저장하지 않도록 잠금 파일(data.json.lock)을 쓴다.
"""
import copy, json, os, sys, time, subprocess
from contextlib import contextmanager
import webview

APP_NAME = "수학의힘 행정도우미"
KINDS    = ("notes", "templates")

DEFAULT_DATA = {
    "notes": [{"name": "기본 정보", "content": "학원명: \n계좌번호: \n예금주: \n전화번호: "}],
    "templates": [{
        "name": "기본 수강료 안내(예시)",
        "content": "안녕하세요.\n{month}월 수강료 안내드립니다.\n\n▶ 수강료: {amount}원\n▶ 납부 기한: {month}월 10일까지\n\n감사합니다.",
        "vars": [
            {"key": "month",  "label": "월",         "value": "__auto_month__"},
            {"key": "amount", "label": "계산된 수강료", "value": "__auto_amount__"},
        ]
    }]
}

class UserError(Exception):
    """화면에 그대로 보여줄 오류"""

class Conflict(UserError):
    """다른 사용자가 같은 항목을 먼저 바꿈"""

# ── 경로 ─────────────────────────────────────────────────────────────────────
def resource_path(name):
    """앱에 함께 묶인 파일 경로 (PyInstaller 로 빌드하면 _MEIPASS 아래에 풀림)"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)

def data_dir():
    """
    앱이 놓인 폴더. 개발·테스트용으로 TUITION_DATA_DIR 환경변수로 바꿀 수 있다.
      소스 실행 : app.py 가 있는 폴더
      Windows   : .exe 가 있는 폴더
      macOS     : .app 이 있는 폴더 (실행파일은 X.app/Contents/MacOS/ 안에 있음)
    """
    if os.environ.get("TUITION_DATA_DIR"):
        return os.environ["TUITION_DATA_DIR"]
    if not getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(__file__))
    folder = os.path.dirname(os.path.abspath(sys.executable))
    if sys.platform == "darwin" and folder.endswith(".app/Contents/MacOS"):
        folder = os.path.dirname(os.path.dirname(os.path.dirname(folder)))
        # 내려받은 앱을 그대로 실행하면 macOS 가 읽기 전용 임시 위치에서 실행한다
        if "/AppTranslocation/" in folder:
            raise UserError(
                "macOS 보안 정책 때문에 앱이 임시 위치에서 실행되어 데이터 폴더를 찾을 수 없습니다.\n"
                "Finder 에서 앱을 다른 폴더로 한 번 옮긴 뒤 다시 실행해주세요.")
    return folder

def data_path():
    return os.path.join(data_dir(), "data.json")

# ── 데이터 ────────────────────────────────────────────────────────────────────
def unique_names(items):
    """항목은 이름으로 구분하므로, 예전 데이터에 남은 중복 이름은 '이름 (2)' 식으로 바꾼다."""
    seen = set()
    for it in items:
        base, name, n = it["name"], it["name"], 2
        while name in seen:
            name, n = f"{base} ({n})", n + 1
        it["name"] = name
        seen.add(name)

def load_data():
    try:
        with open(data_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return copy.deepcopy(DEFAULT_DATA)
    except ValueError:
        # 망가진 파일을 기본값으로 덮어쓰면 모두의 데이터가 사라지므로 멈춘다
        raise UserError(f"data.json 을 읽을 수 없습니다 (파일이 손상됨).\n{data_path()}")
    if "info_list" in data and "notes" not in data:   # 아주 예전 형식 변환
        data["notes"] = [
            {"name": item.get("name", "정보"),
             "content": "\n".join(f"{k}: {v}" for k, v in item.items() if k != "name" and v)}
            for item in data.pop("info_list")]
    # 복사본을 넣어야 저장할 때 DEFAULT_DATA 자체가 바뀌지 않는다
    for kind in KINDS:
        data.setdefault(kind, copy.deepcopy(DEFAULT_DATA[kind]))
    for t in data["templates"]:
        t.setdefault("vars", [])
    for kind in KINDS:
        unique_names(data[kind])
    return data

def save_data(data):
    # 임시 파일에 쓴 뒤 교체 → 저장 도중 꺼져도 기존 파일이 깨지지 않음
    tmp = f"{data_path()}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, data_path())

@contextmanager
def data_lock(timeout=5, stale=30):
    """
    여러 컴퓨터가 동시에 저장하지 않도록 잠금 파일을 만든다.
    앱이 비정상 종료돼 남은 잠금은 stale 초가 지나면 무시한다.
    """
    lock  = data_path() + ".lock"
    start = time.time()
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock) > stale:
                    os.remove(lock)
                    continue
            except OSError:
                pass
            if time.time() - start > timeout:
                raise UserError("다른 사용자가 저장 중입니다. 잠시 후 다시 시도해주세요.")
            time.sleep(0.2)
    try:
        yield
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass

def normalize(kind, item):
    """비교·저장용으로 항목 모양을 맞춘다 (화면의 shape() 와 같은 규칙)"""
    it = {"name": str(item.get("name", "")).strip(), "content": str(item.get("content", ""))}
    if kind == "templates":
        it["vars"] = [{"key": str(v.get("key", "")), "label": str(v.get("label", "")),
                       "value": str(v.get("value", ""))} for v in item.get("vars", [])]
    return it

def find_index(items, name):
    return next((i for i, it in enumerate(items) if it["name"] == name), None)

# ── 화면에서 호출하는 API ────────────────────────────────────────────────────
def api_call(fn):
    """결과를 {"ok": True, ...} / {"ok": False, "error": ...} 형태로 통일"""
    def wrapper(self, *args):
        try:
            return {"ok": True, **(fn(self, *args) or {})}
        except UserError as e:
            return {"ok": False, "error": str(e), "conflict": isinstance(e, Conflict)}
        except OSError as e:
            return {"ok": False, "error": f"파일 오류: {e}"}
    return wrapper

class Api:
    def __init__(self):
        # pywebview 는 공개 속성을 JS 에 노출하려 하므로 창 객체는 _ 로 숨긴다
        self._window = None

    @api_call
    def load(self):
        return {"data": load_data()}

    @api_call
    def save_item(self, kind, base, item):
        """
        base: 편집을 시작할 때의 원본 (새 항목이면 None).
        디스크의 최신 데이터에 이 항목 하나만 반영한다.
        """
        if kind not in KINDS:
            raise UserError("잘못된 요청")
        item = normalize(kind, item)
        if not item["name"]:
            raise UserError("이름을 입력해주세요")
        with data_lock():
            data  = load_data()
            items = data[kind]
            if base is None:
                idx = None
            else:
                idx = find_index(items, base["name"])
                if idx is None:
                    raise Conflict("다른 사용자가 이 항목을 삭제했습니다.")
                if normalize(kind, items[idx]) != normalize(kind, base):
                    raise Conflict("다른 사용자가 이 항목을 먼저 수정했습니다.")
            other = find_index(items, item["name"])
            if other is not None and other != idx:
                raise UserError(f"'{item['name']}' 이름이 이미 있습니다")
            if idx is None:
                items.append(item)
            else:
                items[idx] = item
            save_data(data)
        return {"data": data}

    @api_call
    def delete_item(self, kind, name):
        if kind not in KINDS:
            raise UserError("잘못된 요청")
        with data_lock():
            data = load_data()
            data[kind] = [it for it in data[kind] if it["name"] != name]
            if not data[kind]:
                raise UserError("최소 1개는 있어야 합니다")
            save_data(data)
        return {"data": data}

    @api_call
    def open_folder(self):
        folder = data_dir()
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])

    def copy(self, text):
        # 웹뷰 안의 클립보드 API 는 OS·보안 설정에 따라 막히므로 OS 명령으로 복사
        try:
            if sys.platform == "darwin":
                # .app 은 로케일 없이 실행될 수 있어 UTF-8 을 명시 (한글 깨짐 방지)
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True,
                               env={**os.environ, "LANG": "en_US.UTF-8"})
            elif sys.platform == "win32":
                # 환경변수로 넘기면 유니코드가 그대로 전달됨
                subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Set-Clipboard -Value $env:CLIP_TEXT"],
                               env={**os.environ, "CLIP_TEXT": text}, check=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.run(["xclip", "-selection", "clipboard"],
                               input=text.encode("utf-8"), check=True)
        except (OSError, subprocess.CalledProcessError):
            return False
        return True

    def set_dirty(self, dirty):
        # 저장 안 한 내용이 있을 때만 창 닫기 확인창을 띄움
        if self._window:
            self._window.confirm_close = bool(dirty)

def main():
    api = Api()
    with open(resource_path("ui.html"), encoding="utf-8") as f:
        html = f.read()
    api._window = webview.create_window(
        APP_NAME, html=html, js_api=api,
        width=960, height=720, min_size=(420, 560))
    webview.start(localization={
        "global.quitConfirmation": "저장하지 않은 변경사항이 있습니다. 종료할까요?",
        "global.quit": "종료",
        "global.cancel": "취소",
    })

if __name__ == "__main__":
    main()
