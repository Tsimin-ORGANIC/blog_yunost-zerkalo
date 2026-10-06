# 钇·锆·拾遗

> **Yunost Zerkalo** · Юность Зеркало · **Y-Zr**
> 一间私人档案室：卷宗、摘录与被钉住的黄昏。

基于 [Hugo](https://gohugo.io/) 与 [Stack 主题](https://github.com/CaiJimmy/hugo-theme-stack) 的个人博客，视觉基调为「列宁格勒档案室」：暗夜库房底色、褪色纸卡、血锈红戳记、直角卡片与微缩胶片噪点。

## 本地预览

双击 `预览.bat`，浏览器会自动打开 http://localhost:1314 （需已安装 Hugo extended）。

## 博客助手（给不熟悉 git 的作者）

`blog-app/` 里是一个**通用的 Hugo 博客助手**（不绑定站点、不绑定主题）：源码 `blog_app.py`，打包好的
`dist/博客助手.exe` 双击即可运行，无需安装 Python。两个博客（见山斋 / 本站）**共用同一个 exe**，
它按博客文件夹分别记住站点名、预览端口与关于页路径，切站点只需重新「选择博客文件夹」。

1. 首次使用：菜单「设置 → 选择博客文件夹」，选到博客根目录（有 `hugo.toml` 的那层）
2. 站点名、预览端口、关于页会自动从 `hugo.toml` 和 `content/page/` 探测；不对就在
   「设置 → 站点设置」里改（端口被占用时会自动顺延到下一个空闲端口）
3. 新建文章 → 填标题/分类/标签 → 写正文 → 「插入图片」选照片（自动转格式、压缩、生成图注代码）
4. 「保存草稿」暂存不发布；「🌐 发布到 GitHub」一键提交推送，推上去后 Actions 自动构建上线
5. 第一次发布会弹出 GitHub 登录窗口，登录一次即可

源码改动后重新打包：

```bat
cd blog-app
python -m PyInstaller --onefile --windowed --name 博客助手 blog_app.py
python blog_app.py --selftest    :: 改完先跑自测
```

> 注意：发布前务必确认当前打开的是哪个博客文件夹（窗口标题会显示站点名），避免发错库。

## 写作

- 卷宗放在 `content/posts/`，每篇一个 Markdown 文件（或同名文件夹 + `index.md` + 图片）
- 库房 / 检索 / 登记簿三个页面在 `content/page/` 下，地址已在各自 front matter 里指定
- 字体与配色等视觉定制集中在 `assets/scss/custom.scss`，盖戳动效与传阅计数在 `assets/ts/custom.ts`
- 传阅次数：本机 localStorage 计数（无需后端），换设备不累计；想要真实全站计数可后续接入 umami / busuanzi

## 部署

1. 推送到 GitHub 后，在仓库 **Settings → Pages → Source** 选择 **GitHub Actions**
2. `.github/workflows/deploy.yml` 会在每次 push 时自动构建发布
3. 主题已直接打包在本仓库 `themes/stack/` 内（非子模块），clone 即用，无需 `git submodule update --init`

## 视觉规范速查

| 项 | 值 |
| --- | --- |
| 主背景（暗） | `#2A2C30`（铁灰蓝库房） |
| 卡片（暗） | `#36383D`（亮一档灰蓝纸卡，直角 + 装订线压痕） |
| 主背景（亮） | `#F7F6DC`（泛黄档案纸） |
| 正文 | `#D4C5B0`（暗）/ 墨黑 `#1F1D18`（亮），Times + 华文仿宋打字机体 |
| 强调 | `#8B0000` / `#C24141`（血锈红，仅链接、戳记、警告） |
| 备用强调 | `#4E729E`（氧化锆蓝）、`#9E3C2D`（丹砂红，标签章随机色之一） |
| 标题字体 | 方正姚体（苏式海报方正骨架，子集化 woff2） |
| 噪点 | 内联 SVG feTurbulence 胶片颗粒，opacity 0.05 |

## 字体

站内字体全部为 Windows 系统字体的**子集化 woff2**（GB2312 全部汉字 + 站内实际用字 + 西里尔字母）：

| 文件 | 来源 | 用途 |
| --- | --- | --- |
| `FZYaoTi-subset.woff2` | 方正姚体 `FZYTK.TTF` | 标题（苏式海报骨架） |
| `STFangsong-subset.woff2` | 华文仿宋 `STFANGSO.TTF` | 正文汉字（公文打字机） |
| `Times*-subset.woff2` ×4 | Times New Roman 四体 | 拉丁与西里尔（Юность Зеркало） |

- 重新生成：`python tools/subset-fonts.py`（依赖 `pip install fonttools brotli`，需本机装有上述系统字体）
- 写了生僻字？先 `python tools/subset-fonts.py --check` 查缺字，再重跑生成
- 字体渲染层级见 `assets/scss/custom.scss` 的「〇、字体」一节

## 版权与许可

本站对「内容」和「代码」分别授权，这是静态站点博客的通行做法：

| 部分 | 许可 | 说明 |
| --- | --- | --- |
| 正文内容（`content/` 下的文章与图片） | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh) | 版权归作者本人；转载需署名、非商业、相同方式共享 |
| 站点定制代码（`assets/`、`layouts/` 等） | GPL-3.0 | 基于主题修改/扩展，随主题同协议发布 |
| [Stack 主题](https://github.com/CaiJimmy/hugo-theme-stack) | [GPL-3.0-only](https://github.com/CaiJimmy/hugo-theme-stack/blob/master/LICENSE) | 以 git submodule 引用，保留上游 LICENSE 与页脚署名 |

> GPL 只约束**代码**的传播，不会"传染"到你写的文章和图片上——内容是你的原创作品，版权完全属于你，采用 CC 协议即可，无需与 GPL 兼容。
