"""
테스트 공용 — app.py 를 불러오고, 테스트마다 빈 임시 폴더를 데이터 폴더로 쓴다.
프로젝트 폴더의 data.json 은 건드리지 않는다.
"""
import json, os, shutil, sys, tempfile, types, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# app.py 는 맨 위에서 webview 를 불러온다. 설치돼 있지 않은 환경(테스트 전용 venv 등)이면 빈 모듈로 대신한다.
try:
    import webview  # noqa: F401
except ImportError:
    sys.modules["webview"] = types.ModuleType("webview")

import app  # noqa: E402


class DataDirTest(unittest.TestCase):
    """TUITION_DATA_DIR 을 임시 폴더로 바꿔 두고 끝나면 지운다."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tuition-test-")
        self._old_env = os.environ.get("TUITION_DATA_DIR")
        os.environ["TUITION_DATA_DIR"] = self.dir
        self.path = os.path.join(self.dir, "data.json")
        self.lock = self.path + ".lock"

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("TUITION_DATA_DIR", None)
        else:
            os.environ["TUITION_DATA_DIR"] = self._old_env
        shutil.rmtree(self.dir, ignore_errors=True)

    # 디스크의 data.json 을 직접 쓰고 읽는다 (다른 사람이 쓴 상황 흉내)
    def write(self, obj=None, raw=None):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(obj, ensure_ascii=False))

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def names(self, kind="notes"):
        return [it["name"] for it in self.read()[kind]]
