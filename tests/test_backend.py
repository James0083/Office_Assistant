"""
app.py 의 Api 를 실제로 호출해 보는 테스트 (표준 라이브러리만 사용)
실행: .venv/bin/python -m unittest discover tests
"""
import copy, json, os, subprocess, sys, time, unittest

from _common import ROOT, DataDirTest, app

NOTE_A = {"name": "A", "content": "a"}
NOTE_B = {"name": "B", "content": "b"}


def short_lock_timeout(test, seconds=0.5):
    """잠금 대기 시간(기본 5초)을 줄여 테스트를 빠르게 한다."""
    fn = app.data_lock.__wrapped__
    old = fn.__defaults__
    fn.__defaults__ = (seconds, old[1])
    test.addCleanup(setattr, fn, "__defaults__", old)


class FirstRun(DataDirTest):
    def test_파일이_없으면_기본값으로_시작하고_파일은_만들지_않음(self):
        res = app.Api().load()
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"], app.DEFAULT_DATA)
        self.assertFalse(os.path.exists(self.path))

    def test_처음_저장할_때_파일이_생김(self):
        res = app.Api().save_item("notes", None, {"name": "새 메모", "content": "x"})
        self.assertTrue(res["ok"])
        self.assertEqual(self.names(), ["기본 정보", "새 메모"])
        self.assertIn("templates", self.read())

    def test_저장해도_DEFAULT_DATA_가_바뀌지_않음(self):
        before = copy.deepcopy(app.DEFAULT_DATA)
        api = app.Api()
        api.save_item("templates", app.DEFAULT_DATA["templates"][0],
                      {"name": "기본 수강료 안내(예시)", "content": "바뀜", "vars": []})
        api.save_item("notes", None, {"name": "추가", "content": ""})
        self.assertEqual(app.DEFAULT_DATA, before)

    def test_두_사람이_처음_실행해서_각자_다른_항목을_저장(self):
        # 둘 다 기본값을 보고 있다가 저장 → 서로의 변경이 남아야 함
        a, b = app.Api(), app.Api()
        base_t = a.load()["data"]["templates"][0]
        base_n = b.load()["data"]["notes"][0]
        self.assertTrue(a.save_item("templates", base_t, {**base_t, "content": "A가 고침"})["ok"])
        self.assertTrue(b.save_item("notes", base_n, {**base_n, "content": "B가 고침"})["ok"])
        d = self.read()
        self.assertEqual(d["templates"][0]["content"], "A가 고침")
        self.assertEqual(d["notes"][0]["content"], "B가 고침")


class BrokenFile(DataDirTest):
    def test_손상된_파일은_오류를_알리고_덮어쓰지_않음(self):
        self.write(raw="{망가짐")
        api = app.Api()
        res = api.load()
        self.assertFalse(res["ok"])
        self.assertIn("손상", res["error"])
        res = api.save_item("notes", None, {"name": "x", "content": ""})
        self.assertFalse(res["ok"])
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "{망가짐")
        self.assertFalse(os.path.exists(self.lock))

    def test_빈_파일도_손상으로_처리(self):
        self.write(raw="")
        self.assertFalse(app.Api().load()["ok"])

    def test_삭제도_손상된_파일을_덮어쓰지_않음(self):
        self.write(raw="[1,")
        self.assertFalse(app.Api().delete_item("notes", "x")["ok"])
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "[1,")

    # 고친 버그: Windows 메모장 등으로 열었다 저장하면 UTF-8 BOM 이 붙는데, 이를 '손상'으로 처리함
    #       (app.py:86 encoding="utf-8" → "utf-8-sig" 로 읽으면 해결)
    def test_BOM_이_붙은_파일도_읽음(self):
        self.write(raw="﻿" + json.dumps({"notes": [NOTE_A]}))
        self.assertTrue(app.Api().load()["ok"])

    # 고친 버그: JSON 은 맞지만 모양이 다르면(최상위가 목록, 이름 없는 항목, null) 예외가 api_call 을 빠져나가
    #       화면에는 아무 안내 없이 빈 창만 남음 (app.py:93-104, api_call 은 UserError/OSError 만 잡음)
    def test_모양이_다른_JSON_은_오류로_알림(self):
        for raw in ("[]", "null", '{"notes": null}', '{"notes": [{"content": "x"}]}'):
            with self.subTest(raw=raw):
                self.write(raw=raw)
                res = app.Api().load()   # 지금은 AttributeError/TypeError/KeyError 가 그대로 올라옴
                self.assertFalse(res["ok"])

    # 고친 버그: notes/templates 가 빈 목록이면 그대로 돌려줘서 화면이 시작하다 멈춤 (ui.html:498 items()[0])
    #       (app.py:99-100 setdefault 는 키가 없을 때만 채움)
    def test_빈_목록이면_기본_항목을_채움(self):
        self.write({"notes": [], "templates": []})
        d = app.Api().load()["data"]
        self.assertTrue(d["notes"] and d["templates"])

    # 고친 버그: 손으로 고친 파일에 "content": null 이 있으면 normalize 가 "None" 으로 바꿔
    #       화면이 보낸 원본("")과 영원히 달라 → 매번 충돌, 덮어쓰기도 다시 충돌 (app.py:146, 148-149)
    def test_null_값이_있어도_저장됨(self):
        self.write({"notes": [{"name": "A", "content": None}]})
        base = {"name": "A", "content": ""}   # 화면의 shape() 는 null → ""
        res = app.Api().save_item("notes", base, {"name": "A", "content": "new"})
        self.assertTrue(res["ok"], res)


class OldFormat(DataDirTest):
    def test_info_list_를_메모로_변환(self):
        self.write({"info_list": [
            {"name": "학원", "계좌": "123-45", "빈칸": ""},
            {"전화": "010-0000-0000"},
        ]})
        notes = app.Api().load()["data"]["notes"]
        self.assertEqual(notes, [
            {"name": "학원", "content": "계좌: 123-45"},     # 빈 값은 뺌
            {"name": "정보", "content": "전화: 010-0000-0000"},
        ])

    def test_저장하면_새_형식으로_바뀜(self):
        self.write({"info_list": [{"name": "학원", "계좌": "1"}]})
        app.Api().save_item("notes", None, {"name": "새", "content": ""})
        d = self.read()
        self.assertNotIn("info_list", d)
        self.assertEqual([n["name"] for n in d["notes"]], ["학원", "새"])
        self.assertIn("templates", d)

    def test_vars_없는_템플릿은_빈_목록으로(self):
        self.write({"templates": [{"name": "t", "content": "c"}]})
        self.assertEqual(app.Api().load()["data"]["templates"][0]["vars"], [])


class Names(DataDirTest):
    def test_예전_데이터의_중복_이름은_번호를_붙임(self):
        self.write({"notes": [NOTE_A, {"name": "A", "content": "2"}, {"name": "A", "content": "3"}]})
        names = [n["name"] for n in app.Api().load()["data"]["notes"]]
        self.assertEqual(names, ["A", "A (2)", "A (3)"])

    def test_번호_붙은_이름도_저장_삭제됨(self):
        self.write({"notes": [NOTE_A, {"name": "A", "content": "2"}, NOTE_B]})
        api = app.Api()
        res = api.save_item("notes", {"name": "A (2)", "content": "2"}, {"name": "A (2)", "content": "고침"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(self.read()["notes"][1], {"name": "A (2)", "content": "고침"})
        self.assertTrue(api.delete_item("notes", "A (2)")["ok"])
        self.assertEqual(self.names(), ["A", "B"])

    def test_새_항목_이름이_이미_있으면_거부(self):
        self.write({"notes": [NOTE_A]})
        res = app.Api().save_item("notes", None, {"name": "A", "content": "x"})
        self.assertFalse(res["ok"])
        self.assertFalse(res["conflict"])
        self.assertIn("이미 있습니다", res["error"])

    def test_이름_앞뒤_공백은_지우고_빈_이름은_거부(self):
        api = app.Api()
        self.assertFalse(api.save_item("notes", None, {"name": "   ", "content": ""})["ok"])
        self.assertTrue(api.save_item("notes", None, {"name": "  공백  ", "content": ""})["ok"])
        self.assertIn("공백", self.names())
        self.assertFalse(api.save_item("notes", None, {"name": " 공백", "content": ""})["ok"])

    def test_이름_바꾸기(self):
        self.write({"notes": [NOTE_A, NOTE_B]})
        res = app.Api().save_item("notes", NOTE_A, {"name": "A2", "content": "a"})
        self.assertTrue(res["ok"])
        self.assertEqual(self.names(), ["A2", "B"])   # 자리는 그대로

    def test_있는_이름으로_바꾸기는_거부(self):
        self.write({"notes": [NOTE_A, NOTE_B]})
        res = app.Api().save_item("notes", NOTE_A, {"name": "B", "content": "a"})
        self.assertFalse(res["ok"])
        self.assertEqual(self.read()["notes"], [NOTE_A, NOTE_B])

    def test_잘못된_kind(self):
        api = app.Api()
        self.assertFalse(api.save_item("hack", None, {"name": "x"})["ok"])
        self.assertFalse(api.delete_item("hack", "x")["ok"])


class Content(DataDirTest):
    def test_긴_글_이모지_특수문자_그대로_저장(self):
        text = "가" * 100_000 + '\n😀🎉 <b>&amp;</b> "따옴표" \\ \t {month} ' + "​"
        api = app.Api()
        self.assertTrue(api.save_item("notes", None, {"name": "특수 😀 <>&\"'", "content": text})["ok"])
        it = api.load()["data"]["notes"][-1]
        self.assertEqual(it, {"name": "특수 😀 <>&\"'", "content": text})
        with open(self.path, encoding="utf-8") as f:
            self.assertIn("가가가", f.read())   # 사람이 열어 봐도 한글이 보이게 저장

    def test_템플릿_변수는_key_label_value_만_문자열로(self):
        api = app.Api()
        api.save_item("templates", None, {"name": "t", "content": "{x}",
                                          "vars": [{"key": "x", "value": 3, "extra": 1}]})
        t = api.load()["data"]["templates"][-1]
        self.assertEqual(t["vars"], [{"key": "x", "label": "", "value": "3"}])

    def test_임시_파일이_남지_않음(self):
        app.Api().save_item("notes", None, {"name": "x", "content": ""})
        self.assertEqual(os.listdir(self.dir), ["data.json"])


class TwoUsers(DataDirTest):
    """같은 data.json 을 두 사람이 쓰는 상황 (화면이 보내는 base 를 그대로 흉내)"""

    def setUp(self):
        super().setUp()
        self.write({"notes": [NOTE_A, NOTE_B], "templates": app.DEFAULT_DATA["templates"]})
        self.me, self.other = app.Api(), app.Api()

    def test_서로_다른_항목을_고치면_둘_다_남음(self):
        self.assertTrue(self.other.save_item("notes", NOTE_B, {"name": "B", "content": "남이 고침"})["ok"])
        self.assertTrue(self.me.save_item("notes", NOTE_A, {"name": "A", "content": "내가 고침"})["ok"])
        self.assertEqual(self.read()["notes"], [{"name": "A", "content": "내가 고침"},
                                                {"name": "B", "content": "남이 고침"}])

    def test_같은_항목을_먼저_고쳤으면_충돌(self):
        self.other.save_item("notes", NOTE_A, {"name": "A", "content": "남"})
        res = self.me.save_item("notes", NOTE_A, {"name": "A", "content": "나"})
        self.assertFalse(res["ok"])
        self.assertTrue(res["conflict"])
        self.assertIn("먼저 수정", res["error"])
        self.assertEqual(self.read()["notes"][0]["content"], "남")

    def test_충돌_후_취소하고_다시_저장해도_또_충돌(self):
        self.other.save_item("notes", NOTE_A, {"name": "A", "content": "남"})
        for _ in range(2):   # 화면은 취소해도 base 를 그대로 두므로 같은 요청이 다시 간다
            self.assertTrue(self.me.save_item("notes", NOTE_A, {"name": "A", "content": "나"})["conflict"])

    def test_충돌_후_덮어쓰기(self):
        self.other.save_item("notes", NOTE_A, {"name": "A", "content": "남"})
        latest = next(n for n in self.me.load()["data"]["notes"] if n["name"] == "A")
        res = self.me.save_item("notes", latest, {"name": "A", "content": "나"})
        self.assertTrue(res["ok"])
        self.assertEqual(self.read()["notes"][0]["content"], "나")

    def test_고치는_중에_남이_삭제하면_충돌_덮어쓰면_다시_추가(self):
        self.assertTrue(self.other.delete_item("notes", "A")["ok"])
        res = self.me.save_item("notes", NOTE_A, {"name": "A", "content": "나"})
        self.assertTrue(res["conflict"])
        self.assertIn("삭제", res["error"])
        self.assertTrue(self.me.save_item("notes", None, {"name": "A", "content": "나"})["ok"])
        self.assertEqual(self.names(), ["B", "A"])

    def test_고치는_중에_남이_이름을_바꾸면_삭제로_안내됨(self):
        # 현재 동작: 이름 변경과 삭제를 구분하지 못한다. 덮어쓰기를 고르면 옛 이름으로 하나 더 생김.
        self.other.save_item("notes", NOTE_A, {"name": "A2", "content": "a"})
        res = self.me.save_item("notes", NOTE_A, {"name": "A", "content": "나"})
        self.assertTrue(res["conflict"])
        self.assertIn("삭제", res["error"])

    def test_내가_이름을_바꾸는_사이_남이_같은_이름으로_추가(self):
        self.other.save_item("notes", None, {"name": "C", "content": ""})
        res = self.me.save_item("notes", NOTE_A, {"name": "C", "content": "a"})
        self.assertFalse(res["ok"])
        self.assertIn("이미 있습니다", res["error"])

    def test_남이_이미_지운_항목을_지워도_오류_없음(self):
        self.other.delete_item("notes", "A")
        self.assertTrue(self.me.delete_item("notes", "A")["ok"])
        self.assertEqual(self.names(), ["B"])

    def test_마지막_하나는_지울_수_없음(self):
        self.other.delete_item("notes", "A")
        res = self.me.delete_item("notes", "B")
        self.assertFalse(res["ok"])
        self.assertIn("최소 1개", res["error"])
        self.assertEqual(self.names(), ["B"])


class Lock(DataDirTest):
    def test_다른_사람이_저장_중이면_기다리다_안내(self):
        short_lock_timeout(self)
        self.write({"notes": [NOTE_A]})
        open(self.lock, "w").close()          # 방금 만든 잠금 = 다른 사람이 저장 중
        start = time.time()
        res = app.Api().save_item("notes", None, {"name": "x", "content": ""})
        self.assertFalse(res["ok"])
        self.assertIn("저장 중", res["error"])
        self.assertGreaterEqual(time.time() - start, 0.5)
        self.assertEqual(self.names(), ["A"])
        self.assertTrue(os.path.exists(self.lock))   # 남의 잠금은 지우지 않음

    def test_잠금이_곧_풀리면_이어서_저장(self):
        import threading
        open(self.lock, "w").close()
        threading.Timer(0.5, os.remove, [self.lock]).start()
        self.assertTrue(app.Api().save_item("notes", None, {"name": "x", "content": ""})["ok"])

    def test_오래된_잠금은_무시(self):
        open(self.lock, "w").close()
        old = time.time() - 31
        os.utime(self.lock, (old, old))       # 앱이 비정상 종료돼 남은 잠금
        self.assertTrue(app.Api().save_item("notes", None, {"name": "x", "content": ""})["ok"])
        self.assertFalse(os.path.exists(self.lock))

    def test_충돌이나_오류가_나도_잠금을_풂(self):
        self.write({"notes": [NOTE_A, NOTE_B]})
        api = app.Api()
        api.save_item("notes", {"name": "A", "content": "옛날"}, {"name": "A", "content": "x"})
        api.save_item("notes", NOTE_A, {"name": "B", "content": "x"})
        api.delete_item("notes", "없음")
        self.write({"notes": [NOTE_A]})
        api.delete_item("notes", "A")
        self.assertFalse(os.path.exists(self.lock))

    def test_읽기_전용_폴더면_파일_오류로_안내(self):
        if os.name == "nt" or os.geteuid() == 0:
            self.skipTest("POSIX 일반 사용자에서만")
        os.chmod(self.dir, 0o555)
        try:
            res = app.Api().save_item("notes", None, {"name": "x", "content": ""})
        finally:
            os.chmod(self.dir, 0o755)
        self.assertFalse(res["ok"])
        self.assertIn("파일 오류", res["error"])

    def test_여러_프로세스가_동시에_저장해도_빠짐없이_남음(self):
        code = ("import sys; sys.path.insert(0, sys.argv[2]); import _common\n"
                "for i in range(10):\n"
                "    r = _common.app.Api().save_item('notes', None, {'name': f'p{sys.argv[1]}-{i}', 'content': ''})\n"
                "    assert r['ok'], r\n")
        tests_dir = os.path.join(ROOT, "tests")
        procs = [subprocess.Popen([sys.executable, "-c", code, str(k), tests_dir], env=dict(os.environ))
                 for k in range(4)]
        self.assertEqual([p.wait(timeout=60) for p in procs], [0] * 4)
        self.assertEqual(len(self.names()), 1 + 40)
        self.assertEqual(sorted(os.listdir(self.dir)), ["data.json"])


class DataDir(DataDirTest):
    def test_환경변수로_폴더를_바꿈(self):
        self.assertEqual(app.data_path(), os.path.join(self.dir, "data.json"))

    def test_없는_폴더면_저장은_파일_오류(self):
        os.environ["TUITION_DATA_DIR"] = os.path.join(self.dir, "없음")
        api = app.Api()
        self.assertTrue(api.load()["ok"])
        self.assertIn("파일 오류", api.save_item("notes", None, {"name": "x", "content": ""})["error"])


class Misc(unittest.TestCase):
    def test_창이_없으면_set_dirty_는_무시(self):
        app.Api().set_dirty(True)

    def test_set_dirty_는_창의_닫기_확인을_켬(self):
        api = app.Api()
        api._window = type("W", (), {"confirm_close": False})()
        api.set_dirty(1)
        self.assertIs(api._window.confirm_close, True)
        api.set_dirty(0)
        self.assertIs(api._window.confirm_close, False)


if __name__ == "__main__":
    unittest.main()
