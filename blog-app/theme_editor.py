# -*- coding: utf-8 -*-
"""
主题可视化编辑：把站点 SCSS 里的 CSS 变量读出来，改值后原样写回。

设计原则：
  - 只做「行级替换」：不动缩进、不动注释、不动没被编辑的声明，改完的文件仍是人手可读的 SCSS
  - 值只有三种形态：#RRGGBB / rgba() / 数字+单位，解析与回写都是无损的
  - 每次保存前自动备份，随时可还原
  - 不绑定具体主题：变量清单按名字匹配，找不到的项自动隐藏
"""

import re
from pathlib import Path
from tkinter import (BOTH, HORIZONTAL, LEFT, RIGHT, TOP, W, X, Y, Button, Canvas,
                     DoubleVar, Entry, Frame, Label, StringVar, Toplevel,
                     colorchooser, messagebox, ttk)

# ────────────────────────── SCSS 解析 ──────────────────────────

DECL_RE = re.compile(r"^(--[\w-]+|[a-zA-Z-]+)\s*:\s*(.*)$")
RGBA_RE = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)")
HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
NUM_RE = re.compile(r"([-+]?[\d.]+)\s*([a-z%]*)\s*$")


def scope_of(path):
    """把选择器路径归类：暗色 / 亮色 / 丹砂标签"""
    cinnabar = "zr-tag--cinnabar" in path
    light = 'data-scheme="light"' in path
    if cinnabar:
        return "cinnabar-light" if light else "cinnabar"
    return "light" if light else "dark"


class Decl:
    """一条声明：--变量名: 值;  或  属性: 值;"""

    def __init__(self, path, prop, value, start, end, indent, comment):
        self.path = path          # 所在选择器路径
        self.prop = prop          # --card-background / opacity / font-family
        self.value = value        # 原始值（去掉分号与尾注释）
        self.start = start        # 起始行号（含）
        self.end = end            # 结束行号（含）
        self.indent = indent
        self.comment = comment    # 紧邻上方的注释，用作说明

    @property
    def scope(self):
        return scope_of(self.path)

    def __repr__(self):
        return f"<Decl {self.prop}={self.value!r} @{self.scope}>"


def parse_decls(lines):
    """扫一遍 SCSS，取出所有声明及其所在选择器路径（含嵌套 &[data-scheme]）"""
    decls = []
    stack = []
    pending = []
    last_comment = ""
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        s = raw.strip()

        # 注释块：累积成说明文字
        if s.startswith("/*") or s.startswith("*"):
            txt = s.lstrip("/*").rstrip("*/").strip()
            if txt and not txt.startswith("═"):
                last_comment = txt if not last_comment else last_comment
            i += 1
            continue
        if not s:
            i += 1
            continue

        # 进入块
        if s.endswith("{") and not s.startswith("@"):
            sel = s[:-1].strip()
            if not sel and pending:
                sel = " ".join(x.strip() for x in pending)
            stack.append(sel or "?")
            pending = []
            last_comment = ""
            i += 1
            continue

        # 离开块
        if s.startswith("}"):
            if stack:
                stack.pop()
            pending = []
            last_comment = ""
            i += 1
            continue

        # 单行块：body::before { opacity: 0.05; }
        if "{" in s and "}" in s and stack is not None:
            sel, inner = s.split("{", 1)
            inner = inner.rsplit("}", 1)[0]
            sel = sel.strip() or " ".join(pending).strip()
            stack.append(sel or "?")
            indent = re.match(r"\s*", raw).group(0)
            for piece in inner.split(";"):
                piece = piece.strip()
                if not piece:
                    continue
                m2 = DECL_RE.match(piece)
                if m2:
                    decls.append(Decl(
                        path=" > ".join(stack), prop=m2.group(1),
                        value=m2.group(2).strip(), start=i, end=i,
                        indent=indent, comment=last_comment))
            stack.pop()
            pending = []
            last_comment = ""
            i += 1
            continue

        m = DECL_RE.match(s)
        if m and stack:
            prop, rest = m.group(1), m.group(2)
            j = i
            parts = [rest]
            # 值可能跨行（比如字体栈），一直吃到分号为止
            while j < n and not parts[-1].rstrip().endswith(";"):
                j += 1
                if j >= n:
                    break
                parts.append(lines[j].strip())
            value = " ".join(parts).rstrip(";").strip()
            comment = ""
            if "/*" in value:
                value, comment = value.split("/*", 1)
                value = value.strip()
                comment = comment.rstrip("*/").strip()
            decls.append(Decl(
                path=" > ".join(stack), prop=prop, value=value,
                start=i, end=min(j, n - 1),
                indent=re.match(r"\s*", raw).group(0),
                comment=comment or last_comment))
            last_comment = ""
            i = j + 1
            continue

        # 其他（选择器续行等）
        pending.append(s)
        i += 1
    return decls


class ThemeFile:
    def __init__(self, path):
        self.path = Path(path)
        self.original_text = self.path.read_text(encoding="utf-8")
        self.lines = self.original_text.split("\n")
        self.decls = parse_decls(self.lines)

    def find(self, prop=None, scope=None, path_contains=None, root_only=None):
        """找一条声明。--变量默认只在 :root 里找，避免误命中局部规则里的同名变量"""
        if root_only is None:
            root_only = str(prop or "").startswith("--") and scope in ("dark", "light")
        cands = []
        for d in self.decls:
            if prop is not None and d.prop != prop:
                continue
            if scope is not None and d.scope != scope:
                continue
            if path_contains is not None and path_contains not in d.path:
                continue
            if root_only and ":root" not in d.path:
                continue
            cands.append(d)
        if not cands:
            return None
        # 路径最短的更靠外（更"全局"），其次取最先出现的
        cands.sort(key=lambda d: (len(d.path), d.start))
        return cands[0]

    def set_value(self, decl, new_value):
        """替换一条声明的值（保持缩进；跨行的字体栈会被收成一行）"""
        line = f"{decl.indent}{decl.prop}: {new_value};"
        if decl.comment and "/*" not in line:
            line += f" /* {decl.comment} */"
        self.lines[decl.start:decl.end + 1] = [line]

    def save(self, backup_dir=None, keep=8):
        if backup_dir:
            try:
                bd = Path(backup_dir)
                bd.mkdir(parents=True, exist_ok=True)
                from datetime import datetime
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                (bd / f"custom.scss.{stamp}.bak").write_text(
                    self.original_text, encoding="utf-8")
                baks = sorted(bd.glob("custom.scss.*.bak"))
                for old in baks[:-keep]:
                    old.unlink(missing_ok=True)
            except Exception:
                pass
        self.path.write_text("\n".join(self.lines), encoding="utf-8")
        self.original_text = "\n".join(self.lines)
        self.decls = parse_decls(self.lines)


# ────────────────────────── 颜色工具 ──────────────────────────

def parse_color(text):
    """-> (r, g, b, a)  解析 #RGB / #RRGGBB / rgb() / rgba()"""
    t = (text or "").strip()
    m = HEX_RE.match(t)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
    m = RGBA_RE.search(t)
    if m:
        r, g, b = (int(float(m.group(i))) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) else 1.0
        return r, g, b, a
    return 255, 255, 255, 1.0


def to_hex(r, g, b):
    return "#%02X%02X%02X" % (r, g, b)


def format_color(r, g, b, a):
    if a >= 0.999:
        return to_hex(r, g, b)
    return "rgba({}, {}, {}, {})".format(r, g, b, round(a, 2))


def inline_rgba_replace(text, r, g, b, a):
    """只替换 '1px solid rgba(...)' 里的颜色部分，其余原样保留"""
    return RGBA_RE.sub(lambda _: format_color(r, g, b, a), text, count=1)


PALETTE = [
    ("铁灰库房", "#2A2C30"), ("库房纸卡", "#36383D"), ("暗夜黑", "#111111"),
    ("褪色纸字", "#D3C4B0"), ("描述灰", "#9D9589"), ("冷白", "#E0E0E0"),
    ("血锈红", "#C24141"), ("深血红", "#8B0000"), ("更深的红", "#5E0000"),
    ("氧化锆蓝", "#4E729E"), ("深锆蓝", "#2E5482"), ("浅锆蓝", "#A8C0DC"),
    ("丹砂红", "#9E3C2D"), ("暗丹砂", "#8B2A1E"), ("丹砂浅", "#D98B7A"),
    ("档案纸", "#F7F6DC"), ("纸卡亮", "#FCFAEA"), ("墨黑", "#1F1D18"),
]

FONT_PRESETS = [
    '"Times Arch", "Times New Roman", "FangSong Arch", "STFangsong", "华文仿宋", '
    '"FangSong", "仿宋", "FangSong_GB2312", var(--sys-font-family), serif',
    '"FangSong Arch", "STFangsong", "华文仿宋", "仿宋", var(--sys-font-family), serif',
    '"Times Arch", "Times New Roman", Georgia, var(--sys-font-family), serif',
    'var(--sys-font-family), "Microsoft YaHei UI", sans-serif',
    'ui-monospace, "Cascadia Mono", Consolas, monospace',
]

TITLE_FONT_PRESETS = [
    '"FangYao Arch", "FZYaoTi", "方正姚体", "FangYao", "Microsoft YaHei UI", '
    '"Microsoft YaHei", "PingFang SC", sans-serif',
    '"FangYao Arch", "FZYaoTi", "方正姚体", serif',
    '"Times Arch", "Times New Roman", Georgia, serif',
    'var(--sys-font-family), "Microsoft YaHei UI", sans-serif',
]


# ────────────────────────── 可调项清单 ──────────────────────────

COLOR_GROUPS = [
    ("底色与纸卡", [
        ("库房地面（整页底色）", "--body-background"),
        ("档案纸卡", "--card-background"),
        ("纸卡选中/悬停", "--card-background-selected"),
    ]),
    ("文字", [
        ("正文主色", "--body-text-color"),
        ("卡片主文字（标题）", "--card-text-color-main"),
        ("次要文字（描述）", "--card-text-color-secondary"),
        ("三级文字（时间戳）", "--card-text-color-tertiary"),
        ("分隔线", "--card-separator-color"),
        ("强调色上的文字", "--accent-color-text"),
    ]),
    ("强调色", [
        ("血锈红·链接与戳记", "--accent-color"),
        ("血锈红·深压（装订线）", "--accent-color-darker"),
        ("氧化锆蓝·备用状态色", "--zircon-blue"),
    ]),
    ("代码块·表格·引文", [
        ("代码块底色", "--code-background-color"),
        ("代码块文字", "--code-text-color"),
        ("表格线", "--table-border-color"),
        ("表格偶数行", "--tr-even-background-color"),
        ("引文底色", "--blockquote-background-color"),
    ]),
    ("滚动条与徽标", [
        ("滚动条轨道", "--scrollbar-track"),
        ("滚动条滑块", "--scrollbar-thumb"),
        ("传阅徽标底色", "--circ-badge-bg"),
    ]),
]

CHIP_VARS = [
    ("墨色（文字）", "--chip-ink"),
    ("底色", "--chip-bg"),
    ("边框", "--chip-border"),
    ("悬停填充", "--chip-fill"),
    ("填充上的字", "--chip-fill-text"),
]

# 单项：kind ∈ px / rem / unitless / inline-rgba / font
SINGLE_ITEMS = [
    ("版式", [
        ("卡片圆角（0 = 直角档案）", "--card-border-radius", "px", 0, 24, 1),
        ("标签圆角", "--tag-border-radius", "px", 0, 24, 1),
        ("正文字号", "--article-font-size", "rem", 1.0, 2.5, 0.05),
        ("正文行距", "--article-line-height", "unitless", 1.2, 2.6, 0.05),
        ("胶片颗粒强度", "opacity", "unitless", 0.0, 0.3, 0.01),
    ]),
]


# ────────────────────────── 控件 ──────────────────────────

class ScrollFrame(ttk.Frame):
    """带滚轮的可滚动容器"""

    def __init__(self, master):
        super().__init__(master)
        self.canvas = Canvas(self, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        sb.pack(side=RIGHT, fill=Y)
        for w in (self.canvas, self.inner):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Enter>", lambda e: self.canvas.focus_set())

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


def ask_color(parent, initial_hex, title="选颜色"):
    """色板 + 系统取色器 + 手输 hex"""
    result = {"value": None}
    win = Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.geometry("420x300")
    var = StringVar(value=initial_hex)

    top = ttk.Frame(win, padding=10)
    top.pack(fill=X)
    ttk.Label(top, text="档案室色板：").pack(anchor=W)
    grid = ttk.Frame(top)
    grid.pack(fill=X, pady=(6, 10))
    for idx, (name, hexv) in enumerate(PALETTE):
        b = Button(grid, text=name, bg=hexv, fg="#ffffff" if sum(
            parse_color(hexv)[:3]) < 380 else "#101010",
            relief="flat", width=12, command=lambda h=hexv: var.set(h))
        b.grid(row=idx // 3, column=idx % 3, padx=3, pady=3)

    mid = ttk.Frame(win, padding=(10, 0))
    mid.pack(fill=X)
    ttk.Label(mid, text="或直接填 / 系统取色器：").pack(anchor=W)
    row = ttk.Frame(mid)
    row.pack(fill=X, pady=6)
    e = Entry(row, textvariable=var, width=14)
    e.pack(side=LEFT)
    preview = Label(row, text="    ", relief="solid")
    preview.pack(side=LEFT, padx=8)

    def refresh_preview(*_):
        try:
            r, g, b, _ = parse_color(var.get())
            preview.config(bg=to_hex(r, g, b))
        except Exception:
            pass
    var.trace_add("write", refresh_preview)
    refresh_preview()

    def sys_pick():
        picked = colorchooser.askcolor(initialcolor=var.get(), parent=win, title=title)
        if picked and picked[1]:
            var.set(picked[1].upper())

    ttk.Button(row, text="系统取色器…", command=sys_pick).pack(side=LEFT, padx=6)

    bar = ttk.Frame(win, padding=10)
    bar.pack(fill=X)

    def ok():
        v = var.get().strip()
        if not HEX_RE.match(v):
            messagebox.showerror("颜色", "请填 #RRGGBB 或 #RGB 形式的颜色。", parent=win)
            return
        result["value"] = v.upper()
        win.destroy()

    ttk.Button(bar, text="确定", command=ok).pack(side=LEFT)
    ttk.Button(bar, text="取消", command=win.destroy).pack(side=LEFT, padx=8)
    win.grab_set()
    parent.wait_window(win)
    return result["value"]


class ColorCell:
    """一个色格：色块按钮 + hex 文字 + 可选的透明度滑块"""

    def __init__(self, master, decl, tag):
        self.decl = decl
        self.tag = tag
        r, g, b, a = parse_color(decl.value)
        self.rgb = (r, g, b)
        self.alpha = DoubleVar(value=a)
        self._alpha_stored = a

        self.btn = Button(master, text=to_hex(r, g, b), bg=to_hex(r, g, b),
                          fg="#ffffff" if (r + g + b) < 380 else "#101010",
                          relief="solid", width=10, command=self.pick)
        self.btn.pack(side=LEFT, padx=(0, 4))

        if a < 0.999:
            ttk.Scale(master, from_=0.0, to=1.0, orient=HORIZONTAL, length=70,
                      variable=self.alpha).pack(side=LEFT, padx=(0, 4))
            Label(master, text="α").pack(side=LEFT)

    def pick(self):
        got = ask_color(self.btn, to_hex(*self.rgb), self.tag)
        if not got:
            return
        self.rgb = parse_color(got)[:3]
        self.btn.config(text=got, bg=got,
                        fg="#ffffff" if sum(self.rgb) < 380 else "#101010")

    @property
    def orig_value(self):
        return self.decl.value

    def value_str(self):
        return format_color(*self.rgb, self.alpha.get())

    def is_changed(self):
        return self.value_str() != self.orig_value


class InlineRgbaCell:
    """值形如 '1px solid rgba(...)'：只改颜色部分"""

    def __init__(self, master, decl, tag):
        self.decl = decl
        r, g, b, a = parse_color(decl.value)
        self.rgb = (r, g, b)
        self.alpha = DoubleVar(value=a)
        self.btn = Button(master, text=to_hex(r, g, b), bg=to_hex(r, g, b),
                          fg="#ffffff" if (r + g + b) < 380 else "#101010",
                          relief="solid", width=10, command=self.pick)
        self.btn.pack(side=LEFT, padx=(0, 4))
        ttk.Scale(master, from_=0.0, to=1.0, orient=HORIZONTAL, length=70,
                  variable=self.alpha).pack(side=LEFT, padx=(0, 4))

    def pick(self):
        got = ask_color(self.btn, to_hex(*self.rgb), self.decl.prop)
        if got:
            self.rgb = parse_color(got)[:3]
            self.btn.config(text=got, bg=got,
                            fg="#ffffff" if sum(self.rgb) < 380 else "#101010")

    @property
    def orig_value(self):
        return self.decl.value

    def value_str(self):
        return inline_rgba_replace(self.decl.value, *self.rgb, self.alpha.get())

    def is_changed(self):
        return self.value_str() != self.orig_value


class NumberCell:
    def __init__(self, master, decl, unit, lo, hi, step):
        self.decl = decl
        self.unit = unit
        m = NUM_RE.search(decl.value or "0")
        self.num = float(m.group(1)) if m else 0.0
        self.bare = not (m and m.group(2))   # 原值没写单位（比如 0），就别补单位
        self.var = DoubleVar(value=self.num)
        self.lbl = Label(master, text=self._fmt(self.num), width=7)
        self.lbl.pack(side=LEFT)
        ttk.Scale(master, from_=lo, to=hi, orient=HORIZONTAL, length=150,
                  variable=self.var,
                  command=lambda v: self.lbl.config(text=self._fmt(float(v)))
                  ).pack(side=LEFT, padx=(4, 0))

    def _fmt(self, v):
        if self.unit == "px":
            if self.bare and abs(v - round(v)) < 1e-9:
                return str(int(round(v)))
            return f"{int(round(v))}px"
        if self.unit == "rem":
            return f"{v:.2f}rem"
        return f"{v:.2f}"

    def _num_of(self, text):
        m = NUM_RE.search(text or "0")
        return float(m.group(1)) if m else 0.0

    @property
    def orig_value(self):
        return self.decl.value

    def value_str(self):
        return self._fmt(self.var.get())

    def is_changed(self):
        # 比数值，不比字符串：避免 "0" 与 "0px" 被当成改动
        return abs(self.var.get() - self._num_of(self.orig_value)) > 1e-9


class FontCell:
    def __init__(self, master, decl, presets):
        self.decl = decl
        flat = re.sub(r"\s+", " ", decl.value).strip()
        self.var = StringVar(value=flat)
        cb = ttk.Combobox(master, textvariable=self.var, width=86,
                          values=[re.sub(r"\s+", " ", p).strip() for p in presets])
        cb.pack(side=LEFT, fill=X, expand=True)

    @property
    def orig_value(self):
        return self.decl.value

    def value_str(self):
        return re.sub(r"\s+", " ", self.var.get()).strip()

    def is_changed(self):
        return self.value_str() != re.sub(r"\s+", " ", self.orig_value).strip()


# ────────────────────────── 面板 ──────────────────────────

class ThemePanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.tf = None
        self.cells = []          # [(decl, cell)]
        self._build_bar()
        self.container = ttk.Frame(self)
        self.container.pack(fill=BOTH, expand=True)
        self.reload()

    # ── 顶栏 ──
    def _build_bar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill=X, side=TOP)
        self.path_var = StringVar(value="")
        ttk.Label(bar, textvariable=self.path_var, foreground="#666").pack(side=LEFT)
        ttk.Button(bar, text="保存（预览自动刷新）", command=self.save).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(bar, text="放弃改动", command=self.reload).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(bar, text="还原备份…", command=self.restore).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(bar, text="重新载入", command=self.reload).pack(side=RIGHT, padx=(6, 0))
        self.tip = ttk.Label(self, foreground="#8B0000", padding=(6, 0))
        self.tip.pack(fill=X, side=TOP)

    def _scss_path(self):
        p = getattr(self.app, "scss_path", None)
        if p:
            return Path(p)
        repo = getattr(self.app, "repo", None)
        if not repo:
            return None
        for rel in ("assets/scss/custom.scss", "assets/scss/style.scss"):
            cand = Path(repo) / rel
            if cand.exists():
                return cand
        return None

    def reload(self):
        for w in self.container.winfo_children():
            w.destroy()
        self.cells = []
        self.tf = None
        path = self._scss_path()
        if not path or not Path(path).exists():
            ttk.Label(self.container, padding=20,
                      text="没找到可调的 SCSS。\n"
                           "先在左边选好博客文件夹，或到「设置 → 主题文件」指定路径。",
                      justify="left").pack(anchor=W)
            self.path_var.set("主题文件：未指定")
            self.tip.config(text="")
            return
        try:
            self.tf = ThemeFile(path)
        except Exception as e:
            ttk.Label(self.container, padding=20, text=f"读取失败：{e}").pack(anchor=W)
            return

        try:
            rel = Path(path).relative_to(self.app.repo)
        except Exception:
            rel = path
        self.path_var.set(f"主题文件：{rel}")
        self.tip.config(text="")

        sf = ScrollFrame(self.container)
        sf.pack(fill=BOTH, expand=True)
        box = ttk.Frame(sf.inner, padding=8)
        box.pack(fill=BOTH, expand=True)

        total = len(self.cells)
        self._color_section(box, "案卷标签·锆蓝墨（分类/标签）", CHIP_VARS, ("dark", "light"))
        self._color_section(box, "案卷标签·丹砂红（随机变体）", CHIP_VARS,
                            ("cinnabar", "cinnabar-light"))
        for title, items in COLOR_GROUPS:
            self._color_section(box, title, items, ("dark", "light"))
        self._single_section(box)
        self._font_section(box)
        self._summary(box)

    def _summary(self, box):
        """列出这个主题里没找到的项，别让人以为是坏了"""
        all_vars = [v for _, items in COLOR_GROUPS for _, v in items] + \
                   [v for _, v in CHIP_VARS] + \
                   [p for _, items in SINGLE_ITEMS for _, p, *_ in items]
        missing = []
        for v in dict.fromkeys(all_vars):
            if v.startswith("--"):
                if not (self.tf.find(v, "dark") or self.tf.find(v, "light")):
                    missing.append(v)
            elif v == "opacity":
                if not self.tf.find("opacity", path_contains="body::before"):
                    missing.append("body::before 的 opacity")
        box_ = ttk.Frame(box)
        box_.pack(fill=X, pady=(12, 20))
        n = len(self.cells)
        ttk.Label(box_, foreground="#666", wraplength=760, justify="left",
                  text=f"本站共认出 {n} 项可调。\n"
                       f"没找到的（这个主题没用到，已自动隐藏）：{'、'.join(missing) if missing else '无'}"
                  ).pack(anchor=W)

    def _row(self, box, label, hint=""):
        row = ttk.Frame(box)
        row.pack(fill=X, pady=2)
        ttk.Label(row, text=label, width=24, anchor=W).pack(side=LEFT)
        if hint:
            ttk.Label(row, text=hint, foreground="#888", width=14,
                      anchor=W).pack(side=LEFT)
        return row

    def _color_section(self, box, title, items, scopes):
        found = [(lbl, var) for lbl, var in items
                 if self.tf.find(var, scopes[0]) or self.tf.find(var, scopes[1])]
        if not found:
            return
        # 单色主题（没有亮色块）就只画一栏，别留一排「—」
        has_second = any(self.tf.find(var, scopes[1]) for _, var in found)
        use_scopes = scopes if has_second else scopes[:1]

        grp = ttk.LabelFrame(box, text=f" {title} ", padding=6)
        grp.pack(fill=X, pady=(8, 2))
        head = ttk.Frame(grp)
        head.pack(fill=X)
        ttk.Label(head, text="", width=24).pack(side=LEFT)
        ttk.Label(head, text=("暗色" if has_second else "颜色"),
                  width=16, anchor=W).pack(side=LEFT)
        if has_second:
            ttk.Label(head, text="亮色（浅色模式）", width=24, anchor=W).pack(side=LEFT)

        for label, var in found:
            row = self._row(grp, label)
            for sc in use_scopes:
                d = self.tf.find(var, sc)
                holder = ttk.Frame(row, width=170)
                holder.pack(side=LEFT, padx=(0, 10))
                if d is None:
                    ttk.Label(holder, text="—", foreground="#aaa").pack(side=LEFT)
                    continue
                cell = ColorCell(holder, d, f"{label}·{sc}")
                self.cells.append((d, cell))

    def _single_section(self, box):
        for title, items in SINGLE_ITEMS:
            grp = ttk.LabelFrame(box, text=f" {title} ", padding=6)
            grp.pack(fill=X, pady=(8, 2))
            any_found = False
            for label, prop, unit, lo, hi, step in items:
                if prop.startswith("--"):
                    d = self.tf.find(prop, "dark")
                    if d is None:
                        d = self.tf.find(prop)
                else:
                    d = self.tf.find(prop, path_contains="body::before")
                if d is None:
                    continue
                any_found = True
                row = self._row(grp, label)
                if unit == "px" or unit == "rem" or unit == "unitless":
                    cell = NumberCell(row, d, unit, lo, hi, step)
                else:
                    cell = InlineRgbaCell(row, d, label)
                self.cells.append((d, cell))
            if not any_found:
                grp.destroy()

        # 装订线颜色（值里内嵌 rgba）
        borders = [d for d in self.tf.decls if d.prop == "--archive-border"]
        if borders:
            grp = ttk.LabelFrame(box, text=" 装订线 ", padding=6)
            grp.pack(fill=X, pady=(8, 2))
            for d in borders:
                tag = "亮色" if d.scope == "light" else "暗色"
                row = self._row(grp, f"装订线颜色（{tag}）")
                cell = InlineRgbaCell(row, d, f"装订线·{tag}")
                self.cells.append((d, cell))

    def _font_section(self, box):
        grp = ttk.LabelFrame(box, text=" 字体 ", padding=6)
        grp.pack(fill=X, pady=(8, 2))
        found = False
        for label, prop, presets in (
                ("正文 / 全站字体栈", "--base-font-family", FONT_PRESETS),
                ("标题字体栈", "font-family", TITLE_FONT_PRESETS)):
            if prop.startswith("--"):
                d = self.tf.find(prop, "dark")
            else:
                d = (self.tf.find(prop, path_contains="site-name")
                     or self.tf.find(prop, path_contains="article-title")
                     or self.tf.find(prop))
            if d is None:
                continue
            found = True
            row = ttk.Frame(grp)
            row.pack(fill=X, pady=4)
            ttk.Label(row, text=label, width=24, anchor=W).pack(side=LEFT)
            cell = FontCell(row, d, presets)
            self.cells.append((d, cell))
        if not found:
            grp.destroy()

    # ── 保存 / 还原 ──
    def save(self):
        if not self.tf:
            return
        changed = [(d, c) for d, c in self.cells if c.is_changed()]
        if not changed:
            self.tip.config(text="没有改动。")
            return
        backup_dir = Path(self.tf.path).parent / ".theme-backups"
        # 从后往前改，避免行号偏移
        for d, c in sorted(changed, key=lambda x: -x[0].start):
            self.tf.set_value(d, c.value_str())
        try:
            self.tf.save(backup_dir=backup_dir)
        except Exception as e:
            self.app.log(f"主题保存失败：{e}")
            return
        names = ", ".join(sorted({d.prop for d, _ in changed}))
        self.app.log(f"主题已保存（{len(changed)} 项）：{names}")
        self.app.log(f"备份：{backup_dir}")
        self.reload()
        self.app.after_theme_saved()

    def restore(self):
        if not self.tf:
            return
        bd = Path(self.tf.path).parent / ".theme-backups"
        baks = sorted(bd.glob("custom.scss.*.bak")) if bd.exists() else []
        if not baks:
            messagebox.showinfo("还原", "还没有备份。保存一次之后就会产生备份。")
            return
        win = Toplevel(self)
        win.title("还原备份")
        win.geometry("520x320")
        ttk.Label(win, text="选一个备份还原（当前内容会先备份一份）：",
                  padding=8).pack(anchor=W)
        lb = Frame(win)
        lb.pack(fill=BOTH, expand=True, padx=8)
        from tkinter import Listbox, Scrollbar as Sb, END as TK_END
        s = Sb(lb)
        box = Listbox(lb, yscrollcommand=s.set)
        s.config(command=box.yview)
        s.pack(side="right", fill=Y)
        box.pack(side=LEFT, fill=BOTH, expand=True)
        for b in reversed(baks):
            box.insert(TK_END, b.name)
        sel = {}

        def do_restore():
            idx = box.curselection()
            if not idx:
                return
            name = box.get(idx[0])
            src = bd / name
            try:
                self.tf.save(backup_dir=bd)          # 先备份当前
                self.tf.path.write_text(src.read_text(encoding="utf-8"),
                                        encoding="utf-8")
            except Exception as e:
                self.app.log(f"还原失败：{e}")
                return
            self.app.log(f"已还原备份：{name}")
            win.destroy()
            self.reload()
            self.app.after_theme_saved()

        bar = ttk.Frame(win, padding=8)
        bar.pack(fill=X)
        ttk.Button(bar, text="还原选中", command=do_restore).pack(side=LEFT)
        ttk.Button(bar, text="关闭", command=win.destroy).pack(side=LEFT, padx=8)
