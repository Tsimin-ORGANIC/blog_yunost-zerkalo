# -*- coding: utf-8 -*-
"""
钇·锆·拾遗（Yunost Zerkalo · Y-Zr）· 博客助手
为不会用 git / 命令行的作者定制的桌面端发布工具：
  - 新建 / 编辑文章（标题、分类、标签、正文）
  - 插图：自动转格式、压缩、放入文章目录并生成 figure 代码
  - 保存草稿 / 一键发布（git 提交推送，GitHub Actions 自动构建上线）
  - 本地预览（需本机装有 Hugo）

依赖：仅 Python 标准库 + Pillow（打包后的 exe 无需安装 Python）

注意：本副本属于「钇·锆·拾遗」站，配置文件与 senychistory 的副本相互独立，
预览端口也错开（本站 1314），避免两个博客互相干扰。
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import (BOTH, END, INSERT, LEFT, RIGHT, StringVar, Text, Tk, Toplevel,
                     filedialog, messagebox, ttk, Menu)
from tkinter.scrolledtext import ScrolledText

APP_NAME = "钇·锆·拾遗 · 博客助手"
CONFIG_PATH = Path(os.environ.get("APPDATA", Path.home())) / "BlogPublish" / "config-yunost.json"
POSTS_DIR = Path("content") / "posts"
PREVIEW_PORT = 1314

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


# ─────────────────────────── 配置 ───────────────────────────

def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ──────────────────────── 文章读写 ─────────────────────────

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


def parse_front_matter(text):
    """解析我们自己的 YAML 头部信息（只取已知字段，容错）"""
    meta = {"title": "", "date": "", "description": "", "draft": True,
            "tags": [], "categories": []}
    m = FM_RE.match(text)
    body = text[m.end():] if m else text
    if not m:
        return meta, body
    block = m.group(1)
    for key in ("title", "date", "description", "url"):
        km = re.search(rf"^{key}:\s*[\"']?(.*?)[\"']?\s*$", block, re.M)
        if km:
            meta[key] = km.group(1)
    if re.search(r"^draft:\s*false\s*$", block, re.M):
        meta["draft"] = False
    for key in ("tags", "categories"):
        km = re.search(rf"^{key}:\s*\[(.*?)\]", block, re.M | re.S)
        if km:
            meta[key] = [x.strip().strip("'\"") for x in km.group(1).split(",") if x.strip()]
    return meta, body


def build_front_matter(meta):
    def q(s):
        return '"' + str(s).replace('"', '\\"') + '"'
    lines = ["---",
             f"title: {q(meta['title'])}",
             f"date: {q(meta['date'])}"]
    if meta.get("description"):
        lines.append(f"description: {q(meta['description'])}")
    if meta.get("url"):
        lines.append(f"url: {q(meta['url'])}")
    lines.append(f"draft: {'true' if meta.get('draft', True) else 'false'}")
    tags = meta.get("tags") or []
    cats = meta.get("categories") or []
    lines.append("tags: [" + ", ".join(q(t) for t in tags) + "]")
    lines.append("categories: [" + ", ".join(q(c) for c in cats) + "]")
    lines.append("---")
    return "\n".join(lines) + "\n"


class Post:
    """一篇文章：普通 md 或 文件夹 bundle（index.md）"""

    def __init__(self, md_path, repo_root):
        self.repo_root = Path(repo_root)
        self.md_path = Path(md_path)          # index.md 或 xxx.md
        self.is_bundle = self.md_path.name == "index.md"
        self.dir = self.md_path.parent if self.is_bundle else self.md_path.parent
        self.meta, self.body = parse_front_matter(
            self.md_path.read_text(encoding="utf-8"))

    @property
    def title(self):
        return self.meta.get("title") or self.md_path.stem

    @property
    def draft(self):
        return self.meta.get("draft", True)

    def img_dir(self):
        return self.dir / "img" if self.is_bundle else self.dir

    def save(self, meta, body):
        meta = dict(meta)
        meta.setdefault("date", datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"))
        self.meta, self.body = meta, body
        self.md_path.write_text(build_front_matter(meta) + "\n" + body.rstrip() + "\n",
                                encoding="utf-8")

    def add_image(self, src_path, max_width=1600, quality=88):
        """把图片转成 JPEG（压缩 + 限宽），放入文章目录，返回相对引用路径与 figure 代码"""
        if not HAS_PIL:
            raise RuntimeError("缺少 Pillow，无法处理图片")
        src = Path(src_path)
        img = Image.open(src)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if img.width > max_width:
            h = round(img.height * max_width / img.width)
            img = img.resize((max_width, h), Image.LANCZOS)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_name = f"img-{stamp}.jpg"
        self.img_dir().mkdir(parents=True, exist_ok=True)
        img.save(self.img_dir() / out_name, "JPEG", quality=quality, optimize=True)

        if self.is_bundle:
            ref = f"img/{out_name}"
        else:
            ref = out_name
        caption = src.stem  # 用原文件名当默认图注，作者可自行修改
        snippet = (f'\n{{{{< figure src="{ref}" '
                   f'caption="{caption}" >}}}}\n')
        return ref, snippet


def scan_posts(repo_root):
    posts_dir = Path(repo_root) / "content" / "posts"
    if not posts_dir.exists():
        return []
    result = []
    for p in sorted(posts_dir.rglob("*.md"), key=lambda x: str(x).lower()):
        if p.name.startswith("_"):
            continue
        try:
            result.append(Post(p, repo_root))
        except Exception:
            continue
    # 新文章在前
    result.sort(key=lambda x: x.meta.get("date", ""), reverse=True)
    return result


# ────────────────────────── git 操作 ──────────────────────────

ABOUT_DEFAULT = """这里是钇·锆·拾遗（Yunost Zerkalo · Юность Зеркало），编号 Y-Zr。

一间私人档案室，主要归档：

- **摘录与批注** —— 读到的史料、画册、旧物，随手登记
- **看展记录** —— 博物馆和美术馆的传阅件
- **杂项库房** —— 平时钉住的黄昏、铁轨、生活碎片

可以用左侧栏的「检索」调卷宗，也可以在「库房」按时间浏览。盖章欢迎。
"""


def load_about(repo_root):
    """读取关于页，返回 (meta, body, path)；不存在则用默认模板"""
    path = Path(repo_root) / "content" / "page" / "about" / "index.md"
    if path.exists():
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        return meta, body, path
    meta = {"title": "登记簿", "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "description": "关于本档案室与值班员", "draft": False,
            "url": "/about/", "tags": [], "categories": []}
    return meta, ABOUT_DEFAULT, path


def save_about(repo_root, meta, body):
    path = Path(repo_root) / "content" / "page" / "about" / "index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_front_matter(meta) + "\n" + body.rstrip() + "\n",
                    encoding="utf-8")
    return path


def run_cmd(args, cwd, timeout=120):
    p = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout,
                       shell=False)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()


def git_publish(repo_root, message, log):
    rc, out = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    if rc != 0:
        raise RuntimeError("这里不是有效的 git 仓库，请先检查博客文件夹。\n" + out)
    branch = out.splitlines()[0].strip()

    rc, out = run_cmd(["git", "add", "-A"], repo_root)
    if rc != 0:
        raise RuntimeError("git add 失败：\n" + out)

    rc, out = run_cmd(["git", "commit", "-m", message], repo_root)
    if rc != 0 and "nothing to commit" not in out:
        raise RuntimeError("git commit 失败：\n" + out)
    if "nothing to commit" in out:
        log("没有需要发布的改动。")
    else:
        log(f"已提交：{message}")

    rc, out = run_cmd(["git", "push", "origin", branch], repo_root, timeout=180)
    if rc != 0:
        raise RuntimeError("git push 失败（如果弹出登录窗口请登录 GitHub）：\n" + out)
    log(f"已推送到 GitHub（{branch} 分支），Actions 正在自动发布，"
        f"一两分钟后刷新网页即可看到。")


# ────────────────────────── 主界面 ──────────────────────────

class App:
    def __init__(self, root: Tk):
        self.root = root
        root.title(APP_NAME)
        root.geometry("1080x720")
        root.minsize(900, 620)

        self.repo = None
        self.post = None          # 当前打开的文章
        self.current_ref = None   # 当前列表里对应的 md 路径
        self.preview_proc = None

        self._build_menu()
        self._build_layout()

        cfg = load_config()
        if cfg.get("repo"):
            self._open_repo(cfg["repo"])

    # ── 界面搭建 ──
    def _build_menu(self):
        m = Menu(self.root)
        fm = Menu(m, tearoff=0)
        fm.add_command(label="选择博客文件夹…", command=self.choose_repo)
        fm.add_separator()
        fm.add_command(label="退出", command=self.root.destroy)
        m.add_cascade(label="设置", menu=fm)
        hm = Menu(m, tearoff=0)
        hm.add_command(label="使用帮助", command=self.show_help)
        m.add_cascade(label="帮助", menu=hm)
        self.root.config(menu=m)

    def _build_layout(self):
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            pass
        style.configure(".", font=("Microsoft YaHei UI", 10))

        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=BOTH, expand=True)

        # 左侧：文章列表
        left = ttk.LabelFrame(main, text=" 文章列表 ", padding=6)
        left.pack(side=LEFT, fill="y", padx=(0, 8))
        self.post_list = ttk.Treeview(left, columns=("state",), show="tree headings",
                                      height=24)
        self.post_list.column("#0", width=210)
        self.post_list.column("state", width=52, anchor="center")
        self.post_list.heading("#0", text="标题")
        self.post_list.heading("state", text="状态")
        self.post_list.pack(fill=BOTH, expand=True)
        self.post_list.bind("<<TreeviewSelect>>", self.on_pick_post)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="新建文章", command=self.new_post).pack(side=LEFT, expand=True, fill="x", padx=(0, 2))
        ttk.Button(btns, text="刷新", command=self.refresh_list).pack(side=LEFT, expand=True, fill="x", padx=(2, 0))

        # 右侧：编辑区
        right = ttk.Frame(main)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        meta = ttk.Frame(right)
        meta.pack(fill="x")
        ttk.Label(meta, text="标题：").grid(row=0, column=0, sticky="w")
        self.var_title = StringVar()
        ttk.Entry(meta, textvariable=self.var_title, width=36).grid(row=0, column=1, sticky="we", padx=4)
        ttk.Label(meta, text="分类：").grid(row=0, column=2, sticky="w")
        self.var_cats = StringVar()
        ttk.Entry(meta, textvariable=self.var_cats, width=14).grid(row=0, column=3, sticky="we", padx=4)
        ttk.Label(meta, text="标签(逗号隔开)：").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_tags = StringVar()
        ttk.Entry(meta, textvariable=self.var_tags, width=36).grid(row=1, column=1, sticky="we", padx=4, pady=(6, 0))
        ttk.Label(meta, text="摘要：").grid(row=1, column=2, sticky="w", pady=(6, 0))
        self.var_desc = StringVar()
        ttk.Entry(meta, textvariable=self.var_desc, width=14).grid(row=1, column=3, sticky="we", padx=4, pady=(6, 0))
        meta.columnconfigure(1, weight=1)
        meta.columnconfigure(3, weight=1)

        tools = ttk.Frame(right)
        tools.pack(fill="x", pady=6)
        for text, cmd in (("插入图片", self.insert_images),
                          ("加粗", lambda: self.wrap_selection("**", "**")),
                          ("斜体", lambda: self.wrap_selection("*", "*")),
                          ("引用", lambda: self.wrap_selection("> ", "")),
                          ("图注式插图", self.insert_figure_placeholder)):
            ttk.Button(tools, text=text, command=cmd).pack(side=LEFT, padx=(0, 6))

        ttk.Label(right, text="正文（Markdown）：").pack(anchor="w")
        self.body = ScrolledText(right, font=("Microsoft YaHei UI", 11), undo=True,
                                 wrap="word", height=18)
        self.body.pack(fill=BOTH, expand=True)

        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="保存草稿", command=self.save_draft).pack(side=LEFT, padx=(0, 6))
        ttk.Button(actions, text="🌐 发布到 GitHub", command=self.publish).pack(side=LEFT, padx=6)
        ttk.Button(actions, text="本地预览", command=self.preview).pack(side=RIGHT, padx=6)
        ttk.Button(actions, text="修改简介", command=self.edit_about).pack(side=RIGHT, padx=6)

        # 底部日志
        logf = ttk.LabelFrame(self.root, text=" 消息 ", padding=4)
        logf.pack(fill="x", side="bottom", padx=8, pady=(0, 8))
        self.log_text = Text(logf, height=6, font=("Microsoft YaHei UI", 9),
                             state="disabled", wrap="word")
        self.log_text.pack(fill=BOTH)

    # ── 工具 ──
    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert(END, str(msg) + "\n")
        self.log_text.see(END)
        self.log_text.config(state="disabled")

    def _require_repo(self):
        if not self.repo:
            self.choose_repo()
        return bool(self.repo)

    def choose_repo(self):
        path = filedialog.askdirectory(title="选择博客文件夹（里面有 hugo.toml）")
        if not path:
            return
        p = Path(path)
        if not (p / "hugo.toml").exists():
            messagebox.showerror(APP_NAME, "所选文件夹里没有 hugo.toml，请选择博客根目录。")
            return
        self._open_repo(p)

    def _open_repo(self, p: Path):
        self.repo = p
        cfg = load_config()
        cfg["repo"] = str(p)
        save_config(cfg)
        self.log(f"已打开博客文件夹：{p}")
        self.refresh_list()

    # ── 文章列表 ──
    def refresh_list(self):
        self.post_list.delete(*self.post_list.get_children())
        if not self.repo:
            return
        for post in scan_posts(self.repo):
            state = "草稿" if post.draft else "已发布"
            self.post_list.insert("", END, iid=str(post.md_path),
                                  text=post.title, values=(state,))

    def on_pick_post(self, _event=None):
        sel = self.post_list.selection()
        if not sel:
            return
        try:
            self.post = Post(Path(sel[0]), self.repo)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"读取文章失败：{e}")
            return
        self.current_ref = str(self.post.md_path)
        self.var_title.set(self.post.meta.get("title", ""))
        self.var_cats.set(", ".join(self.post.meta.get("categories", [])))
        self.var_tags.set(", ".join(self.post.meta.get("tags", [])))
        self.var_desc.set(self.post.meta.get("description", ""))
        self.body.delete("1.0", END)
        self.body.insert("1.0", self.post.body)
        self.log(f"已打开：{self.post.title}")

    def _collect_meta(self, draft):
        title = self.var_title.get().strip()
        if not title:
            messagebox.showwarning(APP_NAME, "请先填写文章标题。")
            return None
        split_list = lambda s: [x.strip() for x in s.replace("，", ",").split(",") if x.strip()]
        date = self.post.meta.get("date") if self.post else \
            datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
        return {"title": title, "date": date, "draft": draft,
                "description": self.var_desc.get().strip(),
                "categories": split_list(self.var_cats.get()),
                "tags": split_list(self.var_tags.get())}

    def _new_post_path(self, title):
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        safe = re.sub(r'[\\/:*?"<>|]', "", title)[:20]
        folder = self.repo / "content" / "posts" / f"{stamp}-{safe}" / "index.md"
        folder.parent.mkdir(parents=True, exist_ok=True)
        return folder

    def new_post(self):
        if not self._require_repo():
            return
        self.post = None
        self.current_ref = None
        self.var_title.set("")
        self.var_cats.set("")
        self.var_tags.set("")
        self.var_desc.set("")
        self.body.delete("1.0", END)
        self.body.insert("1.0", "从这里开始写正文……\n\n")
        self.log("新文章已就绪：填写标题和正文后，点「保存草稿」或直接「发布」。")

    def _ensure_post(self, meta):
        """当前没有打开旧文章时，按标题新建一个 bundle"""
        if self.post is None:
            path = self._new_post_path(meta["title"])
            path.write_text("", encoding="utf-8")
            self.post = Post(path, self.repo)
        return self.post

    def _save(self, draft):
        if not self._require_repo():
            return False
        meta = self._collect_meta(draft)
        if meta is None:
            return False
        post = self._ensure_post(meta)
        body = self.body.get("1.0", END)
        post.save(meta, body)
        self.current_ref = str(post.md_path)
        self.refresh_list()
        self.log(("草稿已保存：" if draft else "已保存（将发布）：") + meta["title"])
        return True

    def save_draft(self):
        self._save(draft=True)

    # ── 图片 ──
    def insert_images(self):
        if not self._require_repo():
            return
        files = filedialog.askopenfilenames(
            title="选择图片（可多选，会自动转成压缩 JPG）",
            filetypes=[("图片", "*.jpg *.jpeg *.png *.webp *.bmp *.gif")])
        if not files:
            return
        meta = self._collect_meta(draft=True)
        if meta is None:
            return
        post = self._ensure_post(meta)

        def work():
            try:
                for f in files:
                    ref, snippet = post.add_image(f)
                    self.body.insert(INSERT, snippet)
                    self.log(f"图片已处理并插入：{ref}")
            except Exception as e:
                self.log(f"图片处理失败：{e}")
                return
            body = self.body.get("1.0", END)
            post.save(meta, body)
            self.log("已自动保存草稿。")
        threading.Thread(target=work, daemon=True).start()

    def insert_figure_placeholder(self):
        self.body.insert(INSERT, '\n{{< figure src="img/图片文件名.jpg" caption="图注" >}}\n')
        messagebox.showinfo(APP_NAME,
                            "这是手动插图模板。\n推荐用「插入图片」按钮，会自动转格式并填好路径。")

    def wrap_selection(self, before, after):
        try:
            sel = self.body.get("sel.first", "sel.last")
            self.body.delete("sel.first", "sel.last")
            self.body.insert(INSERT, before + sel + after)
        except Exception:
            self.body.insert(INSERT, before + after)

    # ── 简介（关于页）──
    def edit_about(self):
        if not self._require_repo():
            return
        (meta, body, path) = load_about(self.repo)

        win = Toplevel(self.root)
        win.title("修改登记簿（「登记簿」页）")
        win.geometry("640x560")
        ttk.Label(win, text="访客点开菜单里的「登记簿」看到的内容：", padding=(8, 6)
                  ).pack(anchor="w")
        text = ScrolledText(win, font=("Microsoft YaHei UI", 11), undo=True, wrap="word")
        text.pack(fill=BOTH, expand=True, padx=8)
        text.insert("1.0", body)

        def save_and_close():
            save_about(self.repo, meta, text.get("1.0", END))
            self.log("简介已保存。要点「🌐 发布到 GitHub」才会更新到网上。")
            win.destroy()

        bar = ttk.Frame(win, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="保存", command=save_and_close).pack(side=LEFT)
        ttk.Label(bar, text="保存后回到主窗口点「发布到 GitHub」上线",
                  foreground="#777").pack(side=LEFT, padx=10)

    # ── 发布 / 预览 ──
    def publish(self):
        if not self._require_repo():
            return
        has_article = bool(self.var_title.get().strip())
        if has_article:
            if not messagebox.askyesno(
                    APP_NAME, "确定发布？\n\n会把草稿标记为已发布并推送到 GitHub，"
                              "推送成功后一两分钟内自动上线。"):
                return
            if not self._save(draft=False):
                return
            message = "发布文章：" + self.var_title.get().strip()
        else:
            if not messagebox.askyesno(
                    APP_NAME, "确定发布？\n\n会把已保存的全部改动（简介、文章等）推送到 GitHub，"
                              "推送成功后一两分钟内自动上线。"):
                return
            message = "更新站点内容"

        def work():
            try:
                git_publish(self.repo, message, self.log)
            except Exception as e:
                self.log("发布失败：" + str(e))
                self.log("提示：第一次推送时如果弹出 GitHub 登录窗口，请按提示登录。")
        threading.Thread(target=work, daemon=True).start()

    def preview(self):
        if not self._require_repo():
            return
        hugo = shutil.which("hugo")
        if not hugo:
            messagebox.showwarning(APP_NAME,
                                   "这台电脑没装 Hugo，无法本地预览。\n"
                                   "不影响发布：直接点「发布到 GitHub」即可。")
            return
        if self.preview_proc and self.preview_proc.poll() is None:
            webbrowser.open(f"http://localhost:{PREVIEW_PORT}/")
            return
        self.preview_proc = subprocess.Popen(
            [hugo, "server", "--port", str(PREVIEW_PORT),
             "--baseURL", f"http://localhost:{PREVIEW_PORT}/", "-D"],
            cwd=str(self.repo), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.root.after(2500, lambda: webbrowser.open(f"http://localhost:{PREVIEW_PORT}/"))
        self.log(f"本地预览已启动（http://localhost:{PREVIEW_PORT}/），关闭本程序即停止。")

    def show_help(self):
        Toplevel()
        msg = (
            "第一次使用：\n"
            "1. 菜单「设置 → 选择博客文件夹」，选到博客根目录（里面有 hugo.toml）\n"
            "2. 写文章：新建文章 → 填标题 → 写正文 → 「插入图片」选照片\n"
            "   （图片会自动转成压缩 JPG，无需手动改格式）\n"
            "3. 「保存草稿」= 暂存不发布；「发布到 GitHub」= 一键上线\n"
            "\n"
            "第一次发布会弹出 GitHub 登录窗口，登录一次即可。\n"
            "发布后等一两分钟，刷新博客网页就能看到新文章。\n"
            "\n"
            "常见问题：\n"
            "· 发布失败提示登录 → 登录 GitHub 后再点一次发布\n"
            "· 本地预览不可用 → 说明这台电脑没装 Hugo，直接发布即可"
        )
        messagebox.showinfo(APP_NAME + " · 帮助", msg)


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    root = Tk()
    App(root)
    root.mainloop()


# ────────────────────────── 自测 ──────────────────────────

def selftest():
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="blogapp-test-"))
    (tmp / "hugo.toml").write_text("x=1", encoding="utf-8")
    (tmp / POSTS_DIR).mkdir(parents=True)

    # 1. front matter 往返
    meta = {"title": "测试文章", "date": "2026-01-01T00:00:00+08:00",
            "draft": True, "description": "摘要",
            "tags": ["a", "b"], "categories": ["c"]}
    body = "正文内容"
    md = tmp / POSTS_DIR / "t" / "index.md"
    md.parent.mkdir(parents=True)
    md.write_text("", encoding="utf-8")
    p = Post(md, tmp)
    p.save(meta, body)
    p2 = Post(md, tmp)
    assert p2.meta["title"] == "测试文章" and p2.meta["draft"] is True
    assert p2.meta["tags"] == ["a", "b"] and p2.body.strip() == "正文内容"
    print("front matter 往返 OK")

    # 2. 图片转换
    img = Image.new("RGB", (3000, 1500), (200, 60, 50))
    src = tmp / "src.png"
    img.save(src)
    ref, snippet = p.add_image(src)
    out = p.img_dir() / Path(ref).name
    assert out.exists() and out.stat().st_size > 0
    assert "figure" in snippet and ref.startswith("img/")
    im = Image.open(out)
    assert im.width <= 1600
    print("图片转换 OK:", ref, im.size, f"{out.stat().st_size // 1024}KB")

    # 3. 登记簿读写（含 url 字段保留）
    meta3, body3, path3 = load_about(tmp)
    assert "摘录与批注" in body3 and meta3["url"] == "/about/"
    save_about(tmp, meta3, "新的简介内容")
    meta4, body4, _ = load_about(tmp)
    assert body4.strip() == "新的简介内容" and meta4["url"] == "/about/"
    print("登记簿读写 OK")

    # 4. 列表扫描
    posts = scan_posts(tmp)
    assert len(posts) == 1 and posts[0].title == "测试文章"
    print("文章扫描 OK")

    # 5. git 检测（非仓库应报错）
    try:
        git_publish(tmp, "x", print)
        print("git 检测失败：未报错")
    except RuntimeError:
        print("git 仓库检测 OK")

    shutil.rmtree(tmp, ignore_errors=True)
    print("全部自测通过")


if __name__ == "__main__":
    main()
