"""
ui.html 을 실제 브라우저(Chromium)로 띄워 클릭해 보는 테스트.
window.pywebview.api 는 이 프로세스의 진짜 app.Api 로 이어 준다 (임시 폴더의 data.json 사용).
Playwright 가 없으면 건너뛴다 — 설치 방법은 tests/README.md 참고.
"""
import json, os, unittest

from _common import ROOT, DataDirTest, app

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

# 화면이 부르는 pywebview.api 흉내 — fetch 로 아래 route 에 넘긴다.
# __delay / __delayAfter: 호출 전·후에 기다리는 시간(ms), 공유 폴더가 느린 상황 흉내
SHIM = r"""
window.__delay = {}; window.__delayAfter = {}; window.__dirty = null; window.__copied = null;
window.__confirms = []; window.__confirmAnswer = true; window.__errors = [];
window.addEventListener('error', e => __errors.push(String(e.message)));
window.addEventListener('unhandledrejection', e => __errors.push(String(e.reason)));
window.confirm = m => { __confirms.push(m); return __confirmAnswer; };
const __call = name => async (...args) => {
  const d = __delay[name], a = __delayAfter[name];
  if (d) await new Promise(r => setTimeout(r, d));
  const r = await fetch('/api/' + name, { method: 'POST', body: JSON.stringify(args) });
  if (!r.ok) throw new Error(await r.text());
  const j = await r.json();
  if (a) await new Promise(r => setTimeout(r, a));
  return j;
};
window.pywebview = { api: {
  load: __call('load'), save_item: __call('save_item'), delete_item: __call('delete_item'),
  open_folder: async () => ({ ok: true }),
  copy: async t => { __copied = t; return true; },
  set_dirty: async d => { __dirty = d; },
} };
"""
URL = "http://app.test/"
N, T = "#tab-notes", "#tab-templates"
THREE = [{"name": "A", "content": "a"}, {"name": "B", "content": "b"}, {"name": "C", "content": "c"}]


@unittest.skipIf(sync_playwright is None, "playwright 미설치 (tests/README.md 참고)")
class UITest(DataDirTest):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception:
            try:   # 내려받은 Chromium 이 없으면 설치된 Chrome 사용
                cls.browser = cls.pw.chromium.launch(channel="chrome")
            except Exception as e:
                cls.pw.stop()
                raise unittest.SkipTest(f"브라우저를 띄울 수 없음: {e}")
        with open(os.path.join(ROOT, "ui.html"), encoding="utf-8") as f:
            cls.html = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        super().setUp()
        self.write({"notes": THREE, "templates": app.DEFAULT_DATA["templates"]})

    # 한 사람 = 브라우저 창 하나 + Api 하나 (같은 임시 폴더를 공유)
    def user(self, start=True):
        ctx = self.browser.new_context()
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.add_init_script(SHIM)
        api = app.Api()

        def handle(route):
            path = route.request.url[len(URL) - 1:]
            if path == "/":
                return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=self.html)
            try:
                res = getattr(api, path[len("/api/"):])(*json.loads(route.request.post_data or "[]"))
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(res, ensure_ascii=False))
            except Exception as e:   # pywebview 처럼 JS 쪽 Promise 를 실패시킴
                route.fulfill(status=500, body=f"{type(e).__name__}: {e}")
        page.route(URL + "**", handle)
        page.goto(URL)
        if start:
            self.ready(page)
        return page

    def ready(self, page):
        page.evaluate("window.dispatchEvent(new Event('pywebviewready'))")
        page.wait_for_timeout(300)

    # 자주 쓰는 동작
    def tab(self, u, name):
        u.click(f"nav button[data-tab={name}]")

    def state(self, u, sec=N):
        return u.text_content(sec + " .status"), u.input_value(sec + " .name"), u.input_value(sec + " .content")

    def errors(self, u):
        return u.evaluate("__errors")

    def conflict_open(self, u):
        return u.evaluate("document.querySelector('#conflict').open")

    def choose(self, u, value):
        u.wait_for_selector("#conflict[open]")
        u.click(f"#conflict button[value='{value}']")
        u.wait_for_timeout(300)

    def reload(self, u):
        u.evaluate("reloadData()")   # 15초마다 / 창 포커스 때 하는 다시 불러오기
        u.wait_for_timeout(100)

    def disk(self, kind="notes"):
        return self.read()[kind]


class Calc(UITest):
    def calc(self, u, tuition, start):
        self.tab(u, "calc")
        u.fill("#tuition", "")
        u.type("#tuition", tuition)
        u.fill("#start", start)
        u.click("#calc-form button")
        return u.text_content("#amount")

    def test_일할_계산(self):
        u = self.user()
        cases = [
            ("30", "2026-03-01", "310,000원"),   # 31일 달 1일 시작
            ("30", "2026-03-31", "10,000원"),    # 말일 시작
            ("30", "2026-04-01", "300,000원"),   # 30일 달
            ("30", "2028-02-01", "290,000원"),   # 윤년 2월
            ("30", "2027-02-01", "280,000원"),   # 평년 2월
            ("30", "2027-02-15", "140,000원"),
            ("27", "2026-10-20", "108,000원"),   # 270000/30*12 = 108000
            ("25", "2026-10-07", "208,330원"),   # 10원 단위 절삭
        ]
        for t, d, want in cases:
            with self.subTest(t=t, d=d):
                self.assertEqual(self.calc(u, t, d), want)
        self.assertEqual(self.errors(u), [])

    def test_빈_값_숫자_아닌_값(self):
        u = self.user()
        self.assertEqual(self.calc(u, "", "2026-10-01"), "—")
        self.assertEqual(u.text_content("#detail"), "수강료를 입력해주세요")
        self.calc(u, "abc", "2026-10-01")
        self.assertEqual(u.input_value("#tuition"), "")     # 숫자 말고는 입력이 안 됨
        self.assertEqual(u.text_content("#detail"), "수강료를 입력해주세요")
        self.calc(u, "30", "")
        self.assertEqual(u.text_content("#detail"), "시작일을 선택해주세요")

    def test_계산하면_문자_만들기_버튼(self):
        u = self.user()
        self.assertTrue(u.is_hidden("#to-tmpl"))
        self.calc(u, "30", "2026-11-16")
        u.click("#to-tmpl")
        self.assertTrue(u.is_visible(T + " .name"))

    # 고친 버그: 소수점이 조용히 지워져 32.5(만 원)가 325(만 원)로 계산됨 → 10배 금액 (ui.html:271)
    def test_소수점_수강료(self):
        u = self.user()
        amount = self.calc(u, "32.5", "2026-10-01")
        # 바르게 계산(335,830원)하거나, 적어도 입력을 막고 안내해야 함
        self.assertIn(amount, ("335,830원", "—"))


class Templates(UITest):
    def preview_text(self, u):
        u.click(T + " .preview")
        u.wait_for_timeout(100)
        return u.text_content("#pv-text")

    def test_자동변수는_계산_전엔_이번_달_계산_후엔_시작일의_달(self):
        u = self.user()
        self.tab(u, "templates")
        month = u.evaluate("new Date().getMonth() + 1")
        # 계산 전에는 금액 변수가 있으면 미리보기가 막히므로, 월 변수만 쓴 내용으로 확인
        original = u.input_value(T + " .content")
        u.fill(T + " .content", "{month}월 수강료 안내")
        self.assertIn(f"{month}월 수강료 안내", self.preview_text(u))
        u.click("#pv-close")
        u.fill(T + " .content", original)
        self.tab(u, "calc")
        u.type("#tuition", "30")
        u.fill("#start", "2027-02-15")
        u.click("#calc-form button")
        u.click("#to-tmpl")
        text = self.preview_text(u)
        self.assertIn("2월 수강료 안내", text)
        self.assertIn("수강료: 140,000원", text)
        u.click("#pv-copy")
        u.wait_for_timeout(100)
        self.assertEqual(u.evaluate("__copied"), text)
        self.assertEqual(u.text_content("#pv-copy"), "✓ 복사됨")

    def test_미정의_변수는_경고하고_미리보기를_안_띄움(self):
        u = self.user()
        self.tab(u, "templates")
        u.fill(T + " .content", "{학생} 님 {month}월 {없음} {없음}")
        u.click(T + " .preview")
        self.assertIn("미정의 변수:", u.text_content(T + " .status"))
        self.assertIn("{없음}", u.text_content(T + " .status"))
        self.assertFalse(u.evaluate("document.querySelector('#pv').open"))

    def test_한글_변수_이모지_긴_글_저장(self):
        u = self.user()
        self.tab(u, "templates")
        body = "{학생이름} 학생 😀 <b>&amp;</b> " + "가" * 3000
        u.fill(T + " .content", body)
        u.click(T + " .add-var")
        u.keyboard.type("학생이름")
        u.fill(T + " .var-row:last-child input:not(.key)", "홍길동")
        self.assertTrue(self.preview_text(u).startswith("홍길동 학생 😀 <b>&amp;</b> 가"))
        u.click("#pv-close")
        u.click(T + " .save")
        u.wait_for_timeout(300)
        t = self.disk("templates")[0]
        self.assertEqual(t["content"], body)
        self.assertIn({"key": "학생이름", "label": "", "value": "홍길동"}, t["vars"])

    def test_이름이_빈_변수는_저장할_때_빠짐(self):
        u = self.user()
        self.tab(u, "templates")
        u.click(T + " .add-var")
        u.keyboard.press("Backspace")   # 기본 이름 '변수명' 이 선택돼 있음 → 지움
        u.click(T + " .save")
        u.wait_for_timeout(300)
        self.assertEqual(len(self.disk("templates")[0]["vars"]), 2)

    def test_자동변수_중복_추가_안_됨(self):
        u = self.user()
        self.tab(u, "templates")
        u.select_option(T + " .auto", "__auto_month__")   # 이미 있음
        u.select_option(T + " .auto", "__auto_year__")
        u.select_option(T + " .auto", "__auto_year__")
        self.assertEqual(u.locator(T + " .var-row").count(), 3)

    # 고친 버그: 수강료 계산 전이면 "(수강료 계산 먼저)원" 이 그대로 문자에 들어가 복사까지 됨 (ui.html:251, 481-490)
    def test_계산_전_금액_변수는_경고(self):
        u = self.user()
        self.tab(u, "templates")
        u.click(T + " .preview")
        u.wait_for_timeout(100)
        self.assertFalse(u.evaluate("document.querySelector('#pv').open"))

    # 고친 버그: {constructor} {toString} 처럼 Object 기본 속성 이름은 정의 안 해도 통과하고
    #       "function Object() { [native code] }" 로 바뀜 (ui.html:482 kw = {} → Object.create(null) 또는 Map)
    def test_객체_속성_이름_변수도_미정의로_경고(self):
        u = self.user()
        self.tab(u, "templates")
        u.fill(T + " .content", "{constructor}")
        u.click(T + " .preview")
        u.wait_for_timeout(100)
        self.assertIn("미정의 변수", u.text_content(T + " .status"))


class Notes(UITest):
    def test_새로_만들기_저장(self):
        u = self.user()
        self.tab(u, "notes")
        u.click(N + " .add")
        self.assertEqual(self.state(u)[0], "새 항목 — 저장하면 목록에 추가됩니다")
        u.keyboard.type("계좌 안내")
        u.fill(N + " .content", "국민 123")
        u.keyboard.press("Meta+s")   # 단축키 저장
        u.wait_for_timeout(300)
        self.assertEqual(self.state(u)[0], "✓ 추가됨")
        self.assertEqual(self.disk()[-1], {"name": "계좌 안내", "content": "국민 123"})
        self.assertEqual(u.text_content(N + " .items button.active .t"), "계좌 안내")

    def test_같은_이름이면_저장_버튼이_꺼짐(self):
        u = self.user()
        self.tab(u, "notes")
        u.fill(N + " .name", "B")
        self.assertTrue(u.is_disabled(N + " .save"))
        self.assertTrue(u.is_visible(N + " .name-err"))
        u.fill(N + " .name", "  ")
        self.assertTrue(u.is_disabled(N + " .save"))
        u.fill(N + " .name", "A 새이름")
        u.click(N + " .save")
        u.wait_for_timeout(300)
        self.assertEqual([n["name"] for n in self.disk()], ["A 새이름", "B", "C"])

    def test_삭제_확인_후_다음_항목으로(self):
        u = self.user()
        self.tab(u, "notes")
        u.click(N + " .items button >> text=B")
        u.evaluate("__confirmAnswer = false")
        u.click(N + " .del")
        self.assertEqual(len(self.disk()), 3)
        u.evaluate("__confirmAnswer = true")
        u.click(N + " .del")
        u.wait_for_timeout(300)
        self.assertEqual([n["name"] for n in self.disk()], ["A", "C"])
        self.assertEqual(self.state(u)[1], "C")

    def test_마지막_하나는_삭제_안_됨(self):
        self.write({"notes": [{"name": "A", "content": ""}]})
        u = self.user()
        self.tab(u, "notes")
        u.click(N + " .del")
        self.assertEqual(self.state(u)[0], "최소 1개는 있어야 합니다")
        self.assertEqual(u.evaluate("__confirms"), [])

    def test_검색(self):
        u = self.user()
        self.tab(u, "notes")
        u.fill(N + " .q", "b")
        self.assertEqual(u.locator(N + " .items button").all_text_contents(), ["Bb"])
        u.fill(N + " .q", "없는말")
        self.assertEqual(u.text_content(N + " .items .empty"), "검색 결과 없음")

    def test_저장_안_한_내용_확인(self):
        u = self.user()
        self.tab(u, "notes")
        u.fill(N + " .content", "고치는 중")
        u.wait_for_timeout(100)
        self.assertTrue(u.evaluate("__dirty"))           # 창 닫기 확인이 켜짐
        self.assertEqual(self.state(u)[0], "저장되지 않은 변경사항")
        u.evaluate("__confirmAnswer = false")
        u.click(N + " .items button >> text=B")          # 다른 항목 → 묻고, 취소하면 그대로
        u.click(N + " .add")
        self.assertEqual(self.state(u)[1:], ("A", "고치는 중"))
        self.assertEqual(len(u.evaluate("__confirms")), 2)
        self.tab(u, "templates")                         # 탭을 옮겨도 내용은 남음
        self.tab(u, "notes")
        self.assertEqual(self.state(u)[2], "고치는 중")
        self.reload(u)                                   # 다시 불러오기도 편집 중인 내용은 건드리지 않음
        self.assertEqual(self.state(u)[2], "고치는 중")
        u.evaluate("__confirmAnswer = true")
        u.click(N + " .items button >> text=B")
        self.assertEqual(self.state(u)[1], "B")
        self.assertFalse(u.evaluate("__dirty"))

    # 고친 버그: 메모(또는 템플릿)가 빈 목록인 data.json 이면 시작하다 TypeError 로 멈추고 빈 화면 (ui.html:498)
    def test_빈_목록_파일로_시작(self):
        self.write({"notes": [], "templates": app.DEFAULT_DATA["templates"]})
        u = self.user()
        self.assertEqual(self.errors(u), [])
        self.assertTrue(u.is_visible("#tab-calc"))


class Startup(UITest):
    def test_손상된_파일이면_안내문(self):
        self.write(raw="{망가짐")
        u = self.user()
        self.assertIn("data.json 을 읽을 수 없습니다", u.inner_text("body"))

    # 고친 버그: JSON 모양이 다르면 파이썬 예외가 그대로 JS 로 넘어가 아무 안내 없는 빈 화면 (app.py:93-104, 156-165)
    def test_모양이_다른_파일이면_안내문(self):
        self.write(raw="[]")
        u = self.user()
        self.assertIn("data.json", u.inner_text("body"))


class TwoUsers(UITest):
    def setUp(self):
        super().setUp()
        self.u1, self.u2 = self.user(), self.user()
        for u in (self.u1, self.u2):
            self.tab(u, "notes")

    def both_edit_A(self):
        self.u1.fill(N + " .content", "u1")
        self.u2.fill(N + " .content", "u2")
        self.u1.click(N + " .save")
        self.u1.wait_for_timeout(300)
        self.u2.click(N + " .save")

    def test_다른_사람_변경이_다시_불러오기로_보임(self):
        self.u1.click(N + " .items button >> text=B")
        self.u1.fill(N + " .content", "u1 이 고친 B")
        self.u1.click(N + " .save")
        self.u1.wait_for_timeout(300)
        self.u2.click(N + " .items button >> text=B")
        self.reload(self.u2)
        self.assertEqual(self.state(self.u2)[2], "u1 이 고친 B")

    def test_충돌_최신_내용_불러오기(self):
        self.both_edit_A()
        self.choose(self.u2, "load")
        self.assertEqual(self.state(self.u2)[1:], ("A", "u1"))
        self.assertEqual(self.disk()[0]["content"], "u1")

    def test_충돌_덮어쓰기(self):
        self.both_edit_A()
        self.choose(self.u2, "overwrite")
        self.assertEqual(self.state(self.u2)[0], "✓ 저장됨")
        self.assertEqual(self.disk()[0]["content"], "u2")

    def test_충돌_취소_후_다시_저장하면_다시_묻기(self):
        self.both_edit_A()
        self.choose(self.u2, "")
        self.assertIn("저장 안 됨", self.state(self.u2)[0])
        self.assertEqual(self.state(self.u2)[2], "u2")   # 내 입력은 남음
        self.assertEqual(self.disk()[0]["content"], "u1")
        self.u2.click(N + " .save")
        self.choose(self.u2, "overwrite")
        self.assertEqual(self.disk()[0]["content"], "u2")

    def test_고치는_중에_남이_삭제_덮어쓰면_다시_추가(self):
        self.u2.fill(N + " .content", "u2 가 고치는 A")
        self.u1.click(N + " .del")
        self.u1.wait_for_timeout(300)
        self.u2.click(N + " .save")
        self.u2.wait_for_selector("#conflict[open]")
        self.assertIn("삭제", self.u2.text_content("#conflict-text"))
        self.choose(self.u2, "overwrite")
        self.assertEqual(self.disk(), [THREE[1], THREE[2], {"name": "A", "content": "u2 가 고치는 A"}])

    def test_보고만_있던_항목을_남이_삭제하면_첫_항목으로(self):
        self.u2.click(N + " .items button >> text=B")
        self.u1.click(N + " .items button >> text=B")
        self.u1.click(N + " .del")
        self.u1.wait_for_timeout(300)
        self.reload(self.u2)
        self.assertEqual(self.state(self.u2)[1], "A")
        self.assertEqual(self.errors(self.u2), [])

    # 고친 버그: 고치는 중인 항목을 남이 지운 뒤(다시 불러오기 후) 내가 '삭제'를 누르면
    #       findIndex 가 -1 → items()[-1] 에서 TypeError, 화면은 지운 항목에 멈춤 (ui.html:471-473)
    def test_남이_지운_항목을_내가_삭제(self):
        self.u2.fill(N + " .content", "고치는 중")
        self.u1.click(N + " .del")
        self.u1.wait_for_timeout(300)
        self.reload(self.u2)
        self.u2.click(N + " .del")
        self.u2.wait_for_timeout(300)
        self.assertEqual(self.errors(self.u2), [])
        self.assertNotEqual(self.state(self.u2)[1], "A")


class SlowShare(UITest):
    """공유 폴더가 느릴 때 (응답 지연을 넣어 흉내)"""

    def setUp(self):
        super().setUp()
        self.u = self.user()
        self.tab(self.u, "notes")

    # 고친 버그: 저장 중 버튼·단축키를 막지 않아, 저장을 두 번 누르면 두 번째 요청이 옛 base 로 가서
    #       '다른 사용자가 먼저 수정' 충돌창이 내 저장 때문에 뜸 (ui.html:440-447, 548-554)
    def test_저장_두_번_눌러도_충돌_안_남(self):
        self.u.evaluate("__delay.save_item = 200")
        self.u.fill(N + " .content", "x")
        self.u.click(N + " .save")
        self.u.click(N + " .save")
        self.u.wait_for_timeout(900)
        self.assertFalse(self.conflict_open(self.u))

    # 고친 버그: 위와 같은 원인 — 충돌창이 떠 있을 때 ⌘/Ctrl+S 를 누르면 저장이 하나 더 돌아,
    #       덮어쓰기를 골라도 내 덮어쓰기 때문에 충돌창이 다시 뜸
    def test_충돌창에서_단축키_눌러도_한_번만(self):
        other = self.user()
        self.tab(other, "notes")
        other.fill(N + " .content", "남")
        other.click(N + " .save")
        other.wait_for_timeout(300)
        self.u.fill(N + " .content", "나")
        self.u.click(N + " .save")
        self.u.wait_for_selector("#conflict[open]")
        self.u.keyboard.press("Meta+s")
        self.u.wait_for_timeout(300)
        self.choose(self.u, "overwrite")
        self.u.wait_for_timeout(300)
        self.assertFalse(self.conflict_open(self.u))

    # 고친 버그: 저장 전에 시작된 다시 불러오기(15초 주기·창 포커스) 응답이 저장 뒤에 도착하면
    #       편집기가 옛 내용으로 되돌아가고, 이어서 고쳐 저장하면 내 저장과 충돌 (ui.html:424-432, 541-544)
    def test_늦게_온_다시_불러오기가_저장을_되돌리지_않음(self):
        self.u.evaluate("__delayAfter.load = 800; reloadData(); 0")   # 기다리지 않음
        self.u.wait_for_timeout(150)
        self.u.evaluate("__delayAfter = {}")
        self.u.fill(N + " .content", "저장한 내용")
        self.u.click(N + " .save")
        self.u.wait_for_timeout(1200)
        self.assertEqual(self.disk()[0]["content"], "저장한 내용")
        self.assertEqual(self.state(self.u)[2], "저장한 내용")


if __name__ == "__main__":
    unittest.main()
