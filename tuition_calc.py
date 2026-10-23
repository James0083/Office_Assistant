import tkinter as tk
from tkinter import ttk, messagebox
import calendar
from datetime import datetime
import json, os, sys, re

# ── 데이터 ────────────────────────────────────────────────────────────────────
def get_data_path():
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
           else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "data.json")

DEFAULT_DATA = {
    "notes": [{"name": "기본 정보", "content": "학원명: \n계좌번호: \n예금주: \n전화번호: "}],
    "templates": [{
        "name": "기본 수강료 안내",
        "content": "안녕하세요 😊\n{month}월 수강료 안내드립니다.\n\n▶ 수강료: {amount}원\n▶ 납부 기한: {month}월 10일까지\n\n감사합니다 🙏",
        "vars": [
            {"key": "month",  "label": "월",         "value": "__auto_month__"},
            {"key": "amount", "label": "계산된 수강료", "value": "__auto_amount__"},
        ]
    }]
}

def load_data():
    path = get_data_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "info_list" in data and "notes" not in data:
                data["notes"] = []
                for item in data.pop("info_list"):
                    lines = "\n".join(f"{k}: {v}" for k, v in item.items() if k != "name" and v)
                    data["notes"].append({"name": item.get("name", "정보"), "content": lines})
            data.setdefault("notes", DEFAULT_DATA["notes"])
            data.setdefault("templates", DEFAULT_DATA["templates"])
            for t in data["templates"]:
                t.setdefault("vars", [])
            return data
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_DATA))

def save_data(data):
    try:
        with open(get_data_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        messagebox.showerror("저장 오류", str(e))
        return False

app_data = load_data()

# ── 디자인 토큰 ──────────────────────────────────────────────────────────────
C = {
    "bg":       "#ffffff",
    "surface":  "#f7f8fa",
    "border":   "#e8eaed",
    "border2":  "#d1d5db",
    "blue":     "#3b82f6",
    "blue_dk":  "#2563eb",
    "blue_lt":  "#eff6ff",
    "blue_bd":  "#bfdbfe",
    "txt":      "#111827",
    "txt_md":   "#4b5563",
    "txt_lt":   "#9ca3af",
    "green":    "#10b981",
    "green_dk": "#059669",
    "red":      "#ef4444",
    "red_lt":   "#fef2f2",
    "amber":    "#f59e0b",
    "tag_bg":   "#f0fdf4",
    "tag_bd":   "#bbf7d0",
}
FG  = ("맑은 고딕", 10)
FGS = ("맑은 고딕", 9)
FGB = ("맑은 고딕", 10, "bold")
FGH = ("맑은 고딕", 20, "bold")
FGI = ("맑은 고딕", 11)
FMO = ("Consolas", 9)

# ── 메인 윈도우 ──────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("수강료 계산기")
root.geometry("460x560")
root.minsize(400, 480)
root.resizable(True, True)
root.configure(bg=C["bg"])

style = ttk.Style()
style.theme_use("default")
style.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=0)
style.configure("TNotebook.Tab",
                font=("맑은 고딕", 10), padding=[18, 8],
                background=C["bg"], foreground=C["txt_lt"],
                borderwidth=0, relief="flat")
style.map("TNotebook.Tab",
          background=[("selected", C["bg"]), ("active", C["surface"])],
          foreground=[("selected", C["txt"]), ("active", C["txt_md"])])
style.configure("TFrame", background=C["bg"])
style.configure("TCombobox", fieldbackground=C["bg"],
                background=C["bg"], foreground=C["txt"],
                arrowsize=12, relief="flat", borderwidth=1)
style.map("TCombobox",
          fieldbackground=[("readonly", C["bg"])],
          selectbackground=[("readonly", C["bg"])],
          selectforeground=[("readonly", C["txt"])])

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

# ── 검색 가능한 드롭다운 위젯 ────────────────────────────────────────────────
class SearchableCombo(tk.Frame):
    """
    제목 / 본문 / 제목+본문 검색 기능이 있는 드롭다운.
    items_fn  : 현재 항목 목록 반환 함수 → list of {"name":str, "content":str}
    on_select : 선택된 name을 받는 콜백
    """
    MODES = ["제목", "본문", "제목+본문"]

    def __init__(self, parent, items_fn, on_select, width=20, **kw):
        super().__init__(parent, bg=C["surface"], **kw)
        self._items_fn  = items_fn
        self._on_select = on_select
        self._popup     = None
        self._selected  = tk.StringVar()

        # ── 입력 + 검색모드 선택 + 드롭 버튼 ──────────────────────────────
        inner = tk.Frame(self, bg=C["bg"],
                         highlightthickness=1, highlightbackground=C["border"])
        inner.pack(fill="x")

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_type)

        self._entry = tk.Entry(inner, textvariable=self._search_var,
                               font=FG, fg=C["txt"], bg=C["bg"],
                               relief="flat", bd=0, width=width,
                               insertbackground=C["txt"])
        self._entry.pack(side="left", padx=(8, 0), pady=5, fill="x", expand=True)

        # 검색 범위 선택 (미니 세그먼트)
        self._mode_var = tk.StringVar(value="제목")
        seg = tk.Frame(inner, bg=C["bg"])
        seg.pack(side="left", padx=4)
        self._mode_btns = {}
        for m in self.MODES:
            b = tk.Label(seg, text=m, font=("맑은 고딕", 8),
                         bg=C["bg"], fg=C["txt_lt"],
                         cursor="hand2", padx=4, pady=2)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, mv=m: self._set_mode(mv))
            self._mode_btns[m] = b
        self._set_mode("제목")   # 초기 강조

        # 드롭 화살표 버튼
        drop_btn = tk.Label(inner, text="▾", font=("맑은 고딕", 10),
                            bg=C["bg"], fg=C["txt_lt"], cursor="hand2",
                            padx=6)
        drop_btn.pack(side="right")
        drop_btn.bind("<Button-1>", self._toggle_popup)
        self._entry.bind("<FocusIn>",  self._open_popup)
        self._entry.bind("<Escape>",   lambda e: self._close_popup())
        self._entry.bind("<Down>",     self._focus_list)
        self._entry.bind("<Return>",   self._confirm_first)

    def _set_mode(self, mode):
        self._mode_var.set(mode)
        for m, b in self._mode_btns.items():
            if m == mode:
                b.config(fg=C["blue"],
                         font=("맑은 고딕", 8, "bold"))
            else:
                b.config(fg=C["txt_lt"],
                         font=("맑은 고딕", 8))
        self._refresh_list()

    def get(self):
        return self._selected.get()

    def set(self, name):
        self._selected.set(name)
        self._search_var.set(name)

    def _items(self):
        return self._items_fn()

    def _matches(self, item):
        q    = self._search_var.get().strip().lower()
        mode = self._mode_var.get()
        if not q:
            return True
        name    = item["name"].lower()
        content = item.get("content", "").lower()
        if mode == "제목":
            return q in name
        elif mode == "본문":
            return q in content
        else:
            return q in name or q in content

    def _open_popup(self, e=None):
        if self._popup and self._popup.winfo_exists():
            return
        self._build_popup()

    def _toggle_popup(self, e=None):
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
        else:
            # 드롭 버튼 클릭 시 entry 내용 초기화해 전체 목록 보여주기
            cur = self._selected.get()
            self._search_var.set("")
            self._build_popup()
            # 현재 선택 항목 하이라이트
            self._highlight_current(cur)

    def _build_popup(self):
        # 팝업 위치: entry 아래
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = max(self.winfo_width(), 260)

        self._popup = tk.Toplevel(root)
        self._popup.wm_overrideredirect(True)
        self._popup.geometry(f"{w}x1+{x}+{y}")
        self._popup.configure(bg=C["border"])
        self._popup.attributes("-topmost", True)

        outer = tk.Frame(self._popup, bg=C["bg"],
                         highlightthickness=1, highlightbackground=C["border"])
        outer.pack(fill="both", expand=True)

        self._listbox = tk.Listbox(outer,
                                   font=FG, fg=C["txt"], bg=C["bg"],
                                   selectbackground=C["blue_lt"],
                                   selectforeground=C["blue"],
                                   relief="flat", bd=0,
                                   activestyle="none",
                                   highlightthickness=0)
        lb_sb = tk.Scrollbar(outer, command=self._listbox.yview,
                              width=8, troughcolor=C["surface"])
        lb_sb.pack(side="right", fill="y")
        self._listbox.pack(side="left", fill="both", expand=True)
        self._listbox.config(yscrollcommand=lb_sb.set)

        self._listbox.bind("<<ListboxSelect>>", self._on_lb_select)
        self._listbox.bind("<Return>",          self._on_lb_return)
        self._listbox.bind("<Escape>",          lambda e: self._close_popup())

        # 팝업 바깥 클릭 시 닫기
        self._popup.bind("<FocusOut>", self._on_focus_out)

        self._refresh_list()

    def _highlight_current(self, name):
        if not (self._popup and self._popup.winfo_exists()):
            return
        items = [i for i in self._items() if self._matches(i)]
        names = [i["name"] for i in items]
        if name in names:
            idx = names.index(name)
            self._listbox.selection_set(idx)
            self._listbox.see(idx)

    def _refresh_list(self):
        if not (self._popup and self._popup.winfo_exists()):
            return
        items   = [i for i in self._items() if self._matches(i)]
        lb      = self._listbox
        lb.delete(0, "end")
        for item in items:
            lb.insert("end", f"  {item['name']}")
        # 팝업 높이 조정 (최대 8행)
        rows = max(1, min(len(items), 8))
        line_h = 22
        self._popup.geometry(f"{self._popup.winfo_width()}x{rows * line_h}")

    def _on_type(self, *_):
        self._open_popup(None)
        self._refresh_list()

    def _on_lb_select(self, e=None):
        lb  = self._listbox
        sel = lb.curselection()
        if not sel:
            return
        name = lb.get(sel[0]).strip()
        self._select(name)

    def _on_lb_return(self, e=None):
        self._on_lb_select()

    def _confirm_first(self, e=None):
        if self._popup and self._popup.winfo_exists():
            items = [i for i in self._items() if self._matches(i)]
            if items:
                self._select(items[0]["name"])

    def _focus_list(self, e=None):
        if self._popup and self._popup.winfo_exists():
            self._listbox.focus_set()
            if not self._listbox.curselection():
                self._listbox.selection_set(0)

    def _select(self, name):
        self._selected.set(name)
        self._search_var.set(name)
        self._close_popup()
        self._on_select(name)

    def _on_focus_out(self, e=None):
        # 잠깐 뒤에 체크 (listbox 클릭 시 focus 잠시 빠짐 방지)
        self.after(150, self._check_focus)

    def _check_focus(self):
        try:
            focused = root.focus_get()
            if self._popup and self._popup.winfo_exists():
                if focused not in (self._entry, self._listbox):
                    self._close_popup()
        except Exception:
            self._close_popup()

    def _close_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None
        # 선택된 항목으로 entry 복원
        sel = self._selected.get()
        if sel:
            self._search_var.set(sel)

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────
def lbl(parent, text, font=None, fg=None, bg=None, **kw):
    return tk.Label(parent, text=text,
                    font=font or FG, fg=fg or C["txt_md"],
                    bg=bg or C["bg"], **kw)

def entry(parent, width=20, font=None, **kw):
    e = tk.Entry(parent, width=width, font=font or FGI,
                 fg=C["txt"], bg=C["bg"],
                 insertbackground=C["txt"],
                 relief="solid", bd=1,
                 highlightthickness=1,
                 highlightbackground=C["border"],
                 highlightcolor=C["blue"], **kw)
    return e

def btn(parent, text, cmd, bg=None, fg="white", font=None, pad=(14,7), **kw):
    b = tk.Button(parent, text=text, command=cmd,
                  bg=bg or C["blue"], fg=fg,
                  activebackground=C["blue_dk"], activeforeground="white",
                  font=font or FGB, relief="flat", cursor="hand2",
                  padx=pad[0], pady=pad[1], bd=0, **kw)
    return b

def ghost_btn(parent, text, cmd, fg=None, **kw):
    b = tk.Button(parent, text=text, command=cmd,
                  bg=C["bg"], fg=fg or C["txt_md"],
                  activebackground=C["surface"],
                  activeforeground=fg or C["txt"],
                  font=FGS, relief="flat", cursor="hand2",
                  padx=8, pady=4, bd=0, **kw)
    return b

def divider(parent, pad=(0, 0)):
    tk.Frame(parent, height=1, bg=C["border"]).pack(fill="x", pady=pad)

def status_lbl(parent):
    """인라인 저장 상태 표시용 라벨"""
    v = tk.StringVar()
    l = tk.Label(parent, textvariable=v, font=FGS, bg=C["bg"], fg=C["green"])
    return l, v

def flash_status(var, label, text="저장됨", color=None):
    label.config(fg=color or C["green"])
    var.set(text)
    root.after(2000, lambda: var.set(""))

def section_label(parent, text):
    lbl(parent, text, font=("맑은 고딕", 8), fg=C["txt_lt"]).pack(
        anchor="w", padx=20, pady=(10, 3))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — 수강료 계산
# ══════════════════════════════════════════════════════════════════════════════
tab_calc = tk.Frame(notebook, bg=C["bg"])
notebook.add(tab_calc, text="수강료 계산")

# ── 입력 영역 ─────────────────────────────────────────────────────────────
pad_x = 24

vcmd = root.register(lambda P: P.isdigit() or P == "")

inp_wrap = tk.Frame(tab_calc, bg=C["surface"],
                    highlightthickness=1, highlightbackground=C["border"])
inp_wrap.pack(fill="x", padx=pad_x, pady=(24, 0))

# 수강료
r1 = tk.Frame(inp_wrap, bg=C["surface"])
r1.pack(fill="x", padx=16, pady=(14, 10))
lbl(r1, "수강료", fg=C["txt_lt"], bg=C["surface"], font=FGS).pack(anchor="w")
r1b = tk.Frame(r1, bg=C["surface"])
r1b.pack(anchor="w", pady=(3, 0))
tuition_entry = tk.Entry(r1b, validate="key", validatecommand=(vcmd, "%P"),
                          font=("맑은 고딕", 18), width=10,
                          fg=C["txt"], bg=C["surface"],
                          insertbackground=C["txt"],
                          relief="flat", bd=0,
                          highlightthickness=0)
tuition_entry.pack(side="left")
lbl(r1b, "만 원", fg=C["txt_lt"], bg=C["surface"], font=FG).pack(side="left", padx=(4, 0))

tk.Frame(inp_wrap, height=1, bg=C["border"]).pack(fill="x", padx=16)

# 시작일
r2 = tk.Frame(inp_wrap, bg=C["surface"])
r2.pack(fill="x", padx=16, pady=(10, 14))
lbl(r2, "수업 시작일", fg=C["txt_lt"], bg=C["surface"], font=FGS).pack(anchor="w")
r2b = tk.Frame(r2, bg=C["surface"])
r2b.pack(anchor="w", pady=(6, 0))

now = datetime.now()
year_var  = tk.StringVar(value=str(now.year))
month_var = tk.StringVar(value=str(now.month))
day_var   = tk.StringVar(value=str(now.day))

sp_style = dict(font=("맑은 고딕", 12), relief="flat", bd=0,
                bg=C["bg"], fg=C["txt"],
                highlightthickness=1, highlightbackground=C["border"],
                buttonbackground=C["surface"])

tk.Spinbox(r2b, from_=2020, to=2035, textvariable=year_var,  width=5, **sp_style).pack(side="left")
lbl(r2b, "년", bg=C["surface"], fg=C["txt_md"]).pack(side="left", padx=(2, 8))
tk.Spinbox(r2b, from_=1, to=12, textvariable=month_var, width=3, **sp_style).pack(side="left")
lbl(r2b, "월", bg=C["surface"], fg=C["txt_md"]).pack(side="left", padx=(2, 8))
tk.Spinbox(r2b, from_=1, to=31, textvariable=day_var,   width=3, **sp_style).pack(side="left")
lbl(r2b, "일", bg=C["surface"], fg=C["txt_md"]).pack(side="left", padx=(2, 0))

# ── 계산 버튼 ─────────────────────────────────────────────────────────────
calc_btn = btn(tab_calc, "계산하기", lambda: do_calculate(),
               pad=(0, 13))
calc_btn.pack(fill="x", padx=pad_x, pady=(0, 0))

# ── 결과 ──────────────────────────────────────────────────────────────────
res_wrap = tk.Frame(tab_calc, bg=C["blue_lt"],
                    highlightthickness=1, highlightbackground=C["blue_bd"])
res_wrap.pack(fill="x", padx=pad_x, pady=(0, 20))

lbl(res_wrap, "이번 달 수강료", fg=C["blue"], bg=C["blue_lt"], font=FGS).pack(pady=(16, 2))
result_label = tk.Label(res_wrap, text="—", font=FGH,
                         bg=C["blue_lt"], fg=C["txt_lt"])
result_label.pack()
detail_label = tk.Label(res_wrap, text="", font=FGS,
                         bg=C["blue_lt"], fg=C["txt_lt"])
detail_label.pack(pady=(2, 16))

last_result = {"amount": 0, "month": 0, "year": 0, "tuition": 0}

def do_calculate():
    t = tuition_entry.get().strip()
    if not t:
        tuition_entry.focus()
        result_label.config(text="—", fg=C["txt_lt"])
        detail_label.config(text="수강료를 입력해주세요", fg=C["red"])
        return
    try:
        tuition   = int(t) * 10000
        start_day = int(day_var.get())
        month     = int(month_var.get())
        year      = int(year_var.get())
        last_day  = calendar.monthrange(year, month)[1]
        if start_day > last_day:
            detail_label.config(text=f"{month}월은 {last_day}일까지 있습니다", fg=C["red"])
            return
        days   = last_day - start_day + 1
        result = int((tuition / 30 * days) // 10 * 10)
        result_label.config(text=f"{result:,}원", fg=C["blue"])
        detail_label.config(
            text=f"{tuition:,}원 ÷ 30 × {days}일 (10원 단위 절삭)",
            fg=C["txt_lt"])
        last_result.update(amount=result, month=month, year=year, tuition=tuition)
    except ValueError:
        detail_label.config(text="올바른 숫자를 입력해주세요", fg=C["red"])

root.bind('<Return>', lambda e: do_calculate() if notebook.index(notebook.select()) == 0 else None)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — 문자 템플릿
# ══════════════════════════════════════════════════════════════════════════════
tab_tmpl = tk.Frame(notebook, bg=C["bg"])
notebook.add(tab_tmpl, text="문자 템플릿")
tab_tmpl.rowconfigure(3, weight=1)
tab_tmpl.columnconfigure(0, weight=1)

AUTO_VARS = {
    "__auto_month__":   lambda: str(last_result["month"] or datetime.now().month),
    "__auto_year__":    lambda: str(last_result["year"]  or datetime.now().year),
    "__auto_amount__":  lambda: (f"{last_result['amount']:,}" if last_result["amount"] else "(수강료 계산 먼저)"),
    "__auto_tuition__": lambda: (f"{last_result['tuition']:,}" if last_result["tuition"] else "(수강료 계산 먼저)"),
}
AUTO_LABELS = {
    "__auto_month__":   "월 (자동)",
    "__auto_year__":    "년도 (자동)",
    "__auto_amount__":  "계산된 수강료 (자동)",
    "__auto_tuition__": "정상 수강료 (자동)",
}

# ── 상단 툴바 ────────────────────────────────────────────────────────────
t2_bar = tk.Frame(tab_tmpl, bg=C["surface"],
                   highlightthickness=0)
t2_bar.grid(row=0, column=0, sticky="ew")
tk.Frame(t2_bar, height=1, bg=C["border"]).pack(side="bottom", fill="x")

def _tmpl_items():
    return [{"name": t["name"], "content": t["content"]}
            for t in app_data["templates"]]

tmpl_combo = SearchableCombo(t2_bar, _tmpl_items,
                              lambda name: load_template(name),
                              width=18)
tmpl_combo.pack(side="left", padx=(16, 6), pady=8)

ghost_btn(t2_bar, "+ 새로 만들기", lambda: new_template(),
          fg=C["blue"]).pack(side="left")
ghost_btn(t2_bar, "삭제", lambda: delete_template(),
          fg=C["red"]).pack(side="left")

t2_stat_var = tk.StringVar()
t2_stat_lbl = tk.Label(t2_bar, textvariable=t2_stat_var, font=FGS,
                        bg=C["surface"], fg=C["green"])
t2_stat_lbl.pack(side="right", padx=16)

btn(t2_bar, "미리보기 · 복사", lambda: preview_template(),
    pad=(12, 6)).pack(side="right", pady=8)
btn(t2_bar, "저장", lambda: save_template(),
    bg=C["green"], pad=(12, 6)).pack(side="right", padx=(0, 4), pady=8)

# ── 템플릿 이름 ──────────────────────────────────────────────────────────
t2_name_wrap = tk.Frame(tab_tmpl, bg=C["bg"])
t2_name_wrap.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 4))
lbl(t2_name_wrap, "템플릿 이름", font=FGS, fg=C["txt_lt"]).pack(anchor="w")
tmpl_name_entry = entry(t2_name_wrap, width=34, font=FGI)
tmpl_name_entry.pack(anchor="w", pady=(3, 0), ipady=4)

# ── 본문 ─────────────────────────────────────────────────────────────────
t2_content_wrap = tk.Frame(tab_tmpl, bg=C["bg"])
t2_content_wrap.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 4))
t2_content_wrap.columnconfigure(0, weight=1)
lbl(t2_content_wrap, "내용  ({변수명} 으로 빈칸 삽입)", font=FGS, fg=C["txt_lt"]).grid(
    row=0, column=0, sticky="w")

t2_body_wrap = tk.Frame(tab_tmpl, bg=C["bg"])
t2_body_wrap.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 4))
t2_body_wrap.rowconfigure(0, weight=1)
t2_body_wrap.columnconfigure(0, weight=1)
tmpl_text = tk.Text(t2_body_wrap, font=("맑은 고딕", 10), relief="solid", bd=1,
                     fg=C["txt"], bg=C["bg"],
                     insertbackground=C["txt"],
                     highlightthickness=1, highlightbackground=C["border"],
                     highlightcolor=C["blue"],
                     wrap="word", undo=True, padx=10, pady=10)
tmpl_text.grid(row=0, column=0, sticky="nsew")
t2_tsb = tk.Scrollbar(t2_body_wrap, command=tmpl_text.yview,
                        width=10, troughcolor=C["surface"], bg=C["border"])
t2_tsb.grid(row=0, column=1, sticky="ns")
tmpl_text.config(yscrollcommand=t2_tsb.set)

# ── 변수 패널 ────────────────────────────────────────────────────────────
var_panel = tk.Frame(tab_tmpl, bg=C["surface"],
                      highlightthickness=1, highlightbackground=C["border"])
var_panel.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 4))

vp_head = tk.Frame(var_panel, bg=C["surface"])
vp_head.pack(fill="x", padx=12, pady=(6, 4))
lbl(vp_head, "변수", font=("맑은 고딕", 8, "bold"),
    fg=C["txt_md"], bg=C["surface"]).pack(side="left")

auto_var_sel = tk.StringVar()
auto_combo = ttk.Combobox(vp_head, textvariable=auto_var_sel,
                           values=list(AUTO_LABELS.values()),
                           width=16, state="readonly", font=FGS)
auto_combo.pack(side="right")
lbl(vp_head, "자동변수:", font=FGS, fg=C["txt_lt"], bg=C["surface"]).pack(side="right", padx=(0, 4))

var_canvas = tk.Canvas(var_panel, bg=C["surface"], height=64,
                        highlightthickness=0, bd=0)
var_scroll = tk.Scrollbar(var_panel, orient="vertical", command=var_canvas.yview,
                           width=8, troughcolor=C["surface"])
var_canvas.configure(yscrollcommand=var_scroll.set)
var_canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 6))
var_scroll.pack(side="right", fill="y", pady=(0, 6))

var_inner = tk.Frame(var_canvas, bg=C["surface"])
var_cwin  = var_canvas.create_window((0, 0), window=var_inner, anchor="nw")

def _resize_var(e=None):
    var_canvas.configure(scrollregion=var_canvas.bbox("all"))
    var_canvas.itemconfig(var_cwin, width=var_canvas.winfo_width())
var_inner.bind("<Configure>", _resize_var)
var_canvas.bind("<Configure>", lambda e: var_canvas.itemconfig(var_cwin, width=e.width))

var_rows = []

def add_var_row(key="", label="", value="", auto_key=None):
    row = tk.Frame(var_inner, bg=C["surface"])
    row.pack(fill="x", padx=4, pady=2)

    # 키
    k_e = tk.Entry(row, font=FMO, width=11, relief="flat", bd=0,
                   fg=C["blue"], bg=C["bg"],
                   highlightthickness=1, highlightbackground=C["border"])
    k_e.insert(0, key)
    k_e.pack(side="left", padx=(0, 4), ipady=3)

    # 값 or 자동 뱃지
    if auto_key:
        val_w = tk.Label(row, text=AUTO_LABELS[auto_key],
                         font=FGS, bg=C["blue_lt"], fg=C["blue"],
                         relief="flat", padx=6, pady=2)
        val_w.pack(side="left", padx=(0, 4))
    else:
        val_w = tk.Entry(row, font=FMO, width=18, relief="flat", bd=0,
                         fg=C["txt"], bg=C["bg"],
                         highlightthickness=1, highlightbackground=C["border"],
                         insertbackground=C["txt"])
        val_w.insert(0, value if not value.startswith("__auto_") else "")
        val_w.pack(side="left", padx=(0, 4), ipady=3)

    # 설명을 placeholder처럼 저장용으로만 유지 (숨김 Entry)
    l_e = tk.Entry(row, width=0)
    l_e.insert(0, label)

    def remove():
        row.destroy()
        var_rows[:] = [r for r in var_rows if r["frame"].winfo_exists()]

    tk.Button(row, text="×", font=("맑은 고딕", 10), fg=C["txt_lt"],
              bg=C["surface"], relief="flat", cursor="hand2",
              activeforeground=C["red"], activebackground=C["surface"],
              bd=0, padx=4, command=remove).pack(side="left")

    var_rows.append({"key": k_e, "label": l_e, "val": val_w,
                     "frame": row, "auto_key": auto_key})

def add_auto_var(event=None):
    sel = auto_var_sel.get()
    if not sel:
        return
    ak = next((k for k, v in AUTO_LABELS.items() if v == sel), None)
    if not ak:
        return
    for r in var_rows:
        if r.get("auto_key") == ak and r["frame"].winfo_exists():
            auto_var_sel.set("")
            return
    short = ak.replace("__auto_", "").replace("__", "")
    add_var_row(key=short, label=sel, auto_key=ak)
    auto_var_sel.set("")

auto_combo.bind("<<ComboboxSelected>>", add_auto_var)

vp_foot = tk.Frame(var_panel, bg=C["surface"])
vp_foot.pack(fill="x", padx=8, pady=(0, 6))
ghost_btn(vp_foot, "+ 변수 추가", lambda: add_var_row(key="변수명", value=""),
          fg=C["blue"]).pack(side="left")

# ── 하단 여백 ────────────────────────────────────────────────────────────
tk.Frame(tab_tmpl, bg=C["bg"], height=8).grid(row=5, column=0)

# ── 로직 ─────────────────────────────────────────────────────────────────
def save_template():
    name = tmpl_name_entry.get().strip()
    if not name:
        flash_status(t2_stat_var, t2_stat_lbl, "이름을 입력해주세요", C["red"])
        return
    content = tmpl_text.get("1.0", "end-1c")
    sel = tmpl_combo.get()
    vars_list = []
    for r in var_rows:
        if not r["frame"].winfo_exists():
            continue
        k  = r["key"].get().strip()
        l  = r["label"].get().strip()
        ak = r.get("auto_key")
        v  = ak if ak else r["val"].get().strip()
        if k:
            vars_list.append({"key": k, "label": l, "value": v})
    for t in app_data["templates"]:
        if t["name"] == sel:
            t["name"] = name
            t["content"] = content
            t["vars"] = vars_list
            break
    if save_data(app_data):
        refresh_tmpl_combo(name)
        flash_status(t2_stat_var, t2_stat_lbl, "✓ 저장됨")

def preview_template():
    content = tmpl_text.get("1.0", "end-1c")
    kwargs = {}
    for r in var_rows:
        if not r["frame"].winfo_exists():
            continue
        k  = r["key"].get().strip()
        ak = r.get("auto_key")
        if not k:
            continue
        kwargs[k] = AUTO_VARS[ak]() if (ak and ak in AUTO_VARS) else r["val"].get().strip()
    used    = set(re.findall(r'\{(\w+)\}', content))
    missing = used - set(kwargs.keys())
    if missing:
        flash_status(t2_stat_var, t2_stat_lbl,
                     f"미정의 변수: {', '.join('{'+m+'}' for m in missing)}", C["amber"])
        return
    try:
        filled = content.format(**kwargs)
    except Exception as e:
        flash_status(t2_stat_var, t2_stat_lbl, str(e), C["red"])
        return

    win = tk.Toplevel(root)
    win.title("미리보기")
    win.geometry("340x300")
    win.configure(bg=C["bg"])
    win.resizable(False, True)
    lbl(win, "미리보기", font=FGB, fg=C["txt"]).pack(pady=(16, 6))
    box_wrap = tk.Frame(win, bg=C["bg"])
    box_wrap.pack(fill="both", expand=True, padx=16)
    box_wrap.rowconfigure(0, weight=1)
    box_wrap.columnconfigure(0, weight=1)
    box = tk.Text(box_wrap, font=("맑은 고딕", 10), relief="solid", bd=1,
                  fg=C["txt"], bg=C["surface"], wrap="word", padx=12, pady=12,
                  highlightthickness=0)
    box.pack(fill="both", expand=True)
    box.insert("1.0", filled)
    box.config(state="disabled")

    def copy_text():
        root.clipboard_clear()
        root.clipboard_append(filled)
        copy_b.config(text="✓ 복사됨")
        win.after(1500, lambda: copy_b.config(text="복사하기"))

    copy_b = btn(win, "복사하기", copy_text, pad=(20, 8))
    copy_b.pack(pady=10)

def refresh_tmpl_combo(select_name=None):
    names = [t["name"] for t in app_data["templates"]]
    if names:
        target = select_name if (select_name and select_name in names) else names[0]
        tmpl_combo.set(target)
        load_template(target)

def load_template(name=None):
    sel = name or tmpl_combo.get()
    for t in app_data["templates"]:
        if t["name"] == sel:
            tmpl_name_entry.delete(0, "end")
            tmpl_name_entry.insert(0, t["name"])
            tmpl_text.delete("1.0", "end")
            tmpl_text.insert("1.0", t["content"])
            for r in var_rows:
                if r["frame"].winfo_exists():
                    r["frame"].destroy()
            var_rows.clear()
            for v in t.get("vars", []):
                ak = v["value"] if v["value"].startswith("__auto_") else None
                add_var_row(key=v["key"], label=v["label"],
                            value=v["value"], auto_key=ak)
            break

def new_template():
    app_data["templates"].append({"name": "새 템플릿", "content": "", "vars": []})
    refresh_tmpl_combo("새 템플릿")
    tmpl_name_entry.focus()
    tmpl_name_entry.selection_range(0, "end")

def delete_template():
    sel = tmpl_combo.get()
    if len(app_data["templates"]) <= 1:
        flash_status(t2_stat_var, t2_stat_lbl, "템플릿은 최소 1개 필요", C["red"])
        return
    if messagebox.askyesno("삭제", f"'{sel}' 을 삭제할까요?", parent=root):
        app_data["templates"] = [t for t in app_data["templates"] if t["name"] != sel]
        save_data(app_data)
        refresh_tmpl_combo()

refresh_tmpl_combo()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — 메모
# ══════════════════════════════════════════════════════════════════════════════
tab_info = tk.Frame(notebook, bg=C["bg"])
notebook.add(tab_info, text="메모")
tab_info.rowconfigure(2, weight=1)
tab_info.columnconfigure(0, weight=1)

# ── 상단 툴바 ────────────────────────────────────────────────────────────
t3_bar = tk.Frame(tab_info, bg=C["surface"])
t3_bar.grid(row=0, column=0, sticky="ew")
tk.Frame(t3_bar, height=1, bg=C["border"]).pack(side="bottom", fill="x")

def _note_items():
    return [{"name": n["name"], "content": n.get("content", "")}
            for n in app_data["notes"]]

note_combo = SearchableCombo(t3_bar, _note_items,
                              lambda name: load_note(name),
                              width=18)
note_combo.pack(side="left", padx=(16, 6), pady=8)

ghost_btn(t3_bar, "+ 새로 만들기", lambda: new_note(), fg=C["blue"]).pack(side="left")
ghost_btn(t3_bar, "삭제", lambda: delete_note(), fg=C["red"]).pack(side="left")

t3_stat_var = tk.StringVar()
t3_stat_lbl = tk.Label(t3_bar, textvariable=t3_stat_var, font=FGS,
                        bg=C["surface"], fg=C["green"])
t3_stat_lbl.pack(side="right", padx=16)

btn(t3_bar, "저장", lambda: save_note(),
    bg=C["green"], pad=(14, 6)).pack(side="right", padx=(0, 12), pady=8)

# ── 제목 ─────────────────────────────────────────────────────────────────
t3_title_wrap = tk.Frame(tab_info, bg=C["bg"])
t3_title_wrap.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 4))
lbl(t3_title_wrap, "제목", font=FGS, fg=C["txt_lt"]).pack(anchor="w")
note_name_entry = entry(t3_title_wrap, width=34, font=FGI)
note_name_entry.pack(anchor="w", pady=(3, 0), ipady=4)

# ── 본문 ─────────────────────────────────────────────────────────────────
t3_body = tk.Frame(tab_info, bg=C["bg"])
t3_body.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 4))
t3_body.rowconfigure(0, weight=1)
t3_body.columnconfigure(0, weight=1)
note_text = tk.Text(t3_body, font=("맑은 고딕", 10), relief="solid", bd=1,
                     fg=C["txt"], bg=C["bg"],
                     insertbackground=C["txt"],
                     highlightthickness=1, highlightbackground=C["border"],
                     highlightcolor=C["blue"],
                     wrap="word", undo=True, padx=12, pady=12)
note_text.grid(row=0, column=0, sticky="nsew")
t3_sb = tk.Scrollbar(t3_body, command=note_text.yview,
                      width=10, troughcolor=C["surface"])
t3_sb.grid(row=0, column=1, sticky="ns")
note_text.config(yscrollcommand=t3_sb.set)

# ── 안내 ─────────────────────────────────────────────────────────────────
t3_hint = tk.Frame(tab_info, bg=C["bg"])
t3_hint.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 12))
lbl(t3_hint, "계좌번호, 인수인계, 공지 등 자유롭게 메모하세요  ·  data.json 복사로 이전 가능",
    font=FGS, fg=C["txt_lt"]).pack(side="left")

def open_data_folder():
    folder = os.path.dirname(get_data_path())
    if   sys.platform == "win32": os.startfile(folder)
    elif sys.platform == "darwin": os.system(f'open "{folder}"')
    else: os.system(f'xdg-open "{folder}"')

ghost_btn(t3_hint, "📂 폴더 열기", open_data_folder,
          fg=C["txt_lt"]).pack(side="right")

# ── 로직 ─────────────────────────────────────────────────────────────────
def refresh_note_combo(select_name=None):
    names = [n["name"] for n in app_data["notes"]]
    if names:
        target = select_name if (select_name and select_name in names) else names[0]
        note_combo.set(target)
        load_note(target)

def load_note(name=None):
    sel = name or note_combo.get()
    for n in app_data["notes"]:
        if n["name"] == sel:
            note_name_entry.delete(0, "end")
            note_name_entry.insert(0, n["name"])
            note_text.delete("1.0", "end")
            note_text.insert("1.0", n.get("content", ""))
            break

def new_note():
    app_data["notes"].append({"name": "새 메모", "content": ""})
    refresh_note_combo("새 메모")
    note_name_entry.focus()
    note_name_entry.selection_range(0, "end")

def delete_note():
    sel = note_combo.get()
    if len(app_data["notes"]) <= 1:
        flash_status(t3_stat_var, t3_stat_lbl, "메모는 최소 1개 필요", C["red"])
        return
    if messagebox.askyesno("삭제", f"'{sel}' 을 삭제할까요?", parent=root):
        app_data["notes"] = [n for n in app_data["notes"] if n["name"] != sel]
        save_data(app_data)
        refresh_note_combo()

def save_note():
    sel      = note_combo.get()
    new_name = note_name_entry.get().strip()
    if not new_name:
        flash_status(t3_stat_var, t3_stat_lbl, "제목을 입력해주세요", C["red"])
        return
    for item in app_data["notes"]:
        if item["name"] == new_name and item["name"] != sel:
            flash_status(t3_stat_var, t3_stat_lbl, "같은 제목이 있습니다", C["red"])
            return
    for n in app_data["notes"]:
        if n["name"] == sel:
            n["name"]    = new_name
            n["content"] = note_text.get("1.0", "end-1c")
            break
    if save_data(app_data):
        refresh_note_combo(new_name)
        flash_status(t3_stat_var, t3_stat_lbl, "✓ 저장됨")

refresh_note_combo()

# ── 실행 ─────────────────────────────────────────────────────────────────
root.mainloop()
