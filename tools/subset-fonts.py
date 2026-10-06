# -*- coding: utf-8 -*-
"""
钇·锆·拾遗 · 字体子集化工具
把 Windows 系统字体裁成网站用的 woff2 子集（GB2312 汉字 + 站内实际用字）。

用法：
    python tools/subset-fonts.py            # 正常子集化
    python tools/subset-fonts.py --check    # 只检查正文字符是否有缺字，不动文件

依赖：pip install fonttools brotli

产物：static/fonts/*.woff2（约 1-2MB 级，由构建打进网站）

字号来源：
    - GB2312 全部 6763 汉字（覆盖绝大多数中文写作）
    - 站内 content/ + layouts/ + i18n/ 实际出现的所有字符
    - 西里尔字母（Юность Зеркало）与拉丁扩展
写文章遇到缺字时，把新字加进 content 后重跑本脚本即可。
"""

import sys
from pathlib import Path
from fontTools.subset import Subsetter, Options
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIRS = [ROOT / "content", ROOT / "layouts", ROOT / "i18n", ROOT / "README.md"]
OUT_DIR = ROOT / "static" / "fonts"

FONTS = {
    # 变量名: (源字体路径, 输出文件名, 用途说明)
    "yao":     (r"C:\Windows\Fonts\FZYTK.TTF",    "FZYaoTi-subset.woff2",    "标题：方正姚体"),
    "fang":    (r"C:\Windows\Fonts\STFANGSO.TTF", "STFangsong-subset.woff2", "正文：华文仿宋"),
    "times":   (r"C:\Windows\Fonts\TIMES.TTF",    "Times-subset.woff2",      "拉丁正文：Times"),
    "timesbd": (r"C:\Windows\Fonts\TIMESBD.TTF",  "TimesBD-subset.woff2",    "拉丁粗体：Times Bold"),
    "timesi":  (r"C:\Windows\Fonts\TIMESI.TTF",   "TimesItalic-subset.woff2","拉丁斜体：Times Italic"),
    "timesbi": (r"C:\Windows\Fonts\TIMESBI.TTF",  "TimesBoldItalic-subset.woff2", "拉丁粗斜体：Times Bold Italic"),
}


def gb2312_chars():
    """GB2312 双字节区全部字符（6763 汉字 + 符号区）"""
    chars = set()
    for hi in range(0xB0, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                chars.add(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    # 符号区（另一段双字节）
    for hi in range(0xA1, 0xA8):
        for lo in range(0xA1, 0xFF):
            try:
                chars.add(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    return chars


def site_chars():
    """站内实际用到的所有字符（去空白，保留可见字符）"""
    chars = set()
    for d in CONTENT_DIRS:
        if d.is_file():
            try:
                chars |= set(d.read_text(encoding="utf-8"))
            except Exception:
                pass
        elif d.is_dir():
            for p in d.rglob("*"):
                if p.suffix.lower() in (".md", ".html", ".toml", ".yml", ".scss", ".ts"):
                    try:
                        chars |= set(p.read_text(encoding="utf-8"))
                    except Exception:
                        pass
    # ASCII 全集（打字机正文需要完整拉丁与标点）
    chars |= {chr(c) for c in range(0x20, 0x7F)}
    # 西里尔字母全表（Юность Зеркало 及未来可能的俄语引用）
    chars |= {chr(c) for c in range(0x0400, 0x0500)}
    # 常用符号补充
    chars |= set("·—…「」『』《》〈〉·№§¶†‡•°×÷±∞≈≠≤≥→←↑↓↔⇒⇐★☆⚙☸✦✧♪♫")
    return chars


def charset():
    return gb2312_chars() | site_chars()


def subset_one(src: str, out: Path, chars: set, hinting: bool = True) -> float:
    opts = Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]          # 保留全部 OpenType 特性
    opts.name_IDs = [0, 1, 2, 3, 4, 6]    # 保留基本命名记录
    opts.notdef_outline = True
    opts.recalc_bounds = True
    opts.drop_tables += ["FFTM"]
    # 中文字体字形极多，hinting 指令表占 30-40% 体积且现代系统基本不读；
    # 西文小字号清晰度靠 hinting，保留。
    opts.hinting = hinting
    font = TTFont(src)
    ss = Subsetter(options=opts)
    ss.populate(text="".join(sorted(chars)))
    ss.subset(font)
    out.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(out))
    return out.stat().st_size / 1024


def main():
    check_only = "--check" in sys.argv
    chars = charset()

    # 检查站内字符是否都能被子集覆盖（源字体是否真的有这个字形）
    for key, (src, out_name, _usage) in FONTS.items():
        if not key in ("yao", "fang"):
            continue  # 只检查 CJK 字体；Times 本来就不含汉字
        f = TTFont(src)
        cmap = f.getBestCmap()
        missing = sorted(ch for ch in (chars & CJK_ONLY) if ord(ch) not in cmap)
        if missing:
            print(f"[缺字] {key}: {len(missing)} 个 GB2312 字在源字体中不存在，"
                  f"例如: {''.join(missing[:30])}")
        else:
            print(f"[OK] {key}: GB2312 全覆盖")

    if check_only:
        return

    total = 0.0
    for key, (src, out_name, usage) in FONTS.items():
        if not Path(src).exists():
            print(f"[跳过] {src} 不存在（{usage}）")
            continue
        hinting = key not in ("yao", "fang")  # 中文字体去 hinting 减重
        kb = subset_one(src, OUT_DIR / out_name, chars, hinting=hinting)
        total += kb
        print(f"[生成] {out_name:<32} {kb:8.1f} KB  ({usage})")
    print(f"合计 {total:.1f} KB")


# 汉字判定（用于缺字检查）：GB2312 汉字区
def _is_cjk(ch):
    return '\u4e00' <= ch <= '\u9fff'

CJK_ONLY = None  # 占位，main 里构建


if __name__ == "__main__":
    # 构建汉字集合（gb2312 双字节中的汉字部分）
    _han = set()
    for hi in range(0xB0, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                ch = bytes([hi, lo]).decode("gb2312")
                if '\u4e00' <= ch <= '\u9fff':
                    _han.add(ch)
            except UnicodeDecodeError:
                pass
    CJK_ONLY = _han
    main()
