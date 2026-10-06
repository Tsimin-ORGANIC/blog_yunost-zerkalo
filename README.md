# 钇·锆·拾遗

> **Yunost Zerkalo** · Юность Зеркало · **Y-Zr**
> 捡一些碎片，为将来的过去拾遗补缺。

基于 [Hugo](https://gohugo.io/) 与 [Stack 主题](https://github.com/CaiJimmy/hugo-theme-stack) 的个人博客，视觉基调为「列宁格勒档案室」：暗夜库房底色、褪色纸卡、血锈红戳记、直角卡片与微缩胶片噪点。

## 本地预览

双击 `预览.bat`，浏览器会自动打开 http://localhost:1314 （需已安装 Hugo extended）。

## 博客助手（给不熟悉 git 的作者）

`blog-app/` 里是一个**通用的 Hugo 博客助手**（不绑定站点、不绑定主题）：源码 `blog_app.py` +
`theme_editor.py`，打包好的 `dist/博客助手.exe` 双击即可运行，无需安装 Python。两个博客（见山斋 /
本站）**共用同一个 exe**，它按博客文件夹分别记住站点名、预览端口、关于页路径与主题文件，
切站点只需重新「选择博客文件夹」。

**写文章**页：

1. 首次使用：菜单「设置 → 选择博客文件夹」，选到博客根目录（有 `hugo.toml` 的那层）
2. 站点名、预览端口、关于页会自动从 `hugo.toml` 和 `content/page/` 探测；不对就在
   「设置 → 站点设置」里改（端口被占用时会自动顺延到下一个空闲端口）
3. 新建文章 → 填标题/分类/标签 → 写正文 → 「插入图片」选照片（自动转格式、压缩、生成图注代码）
4. 「保存草稿」暂存不发布；「🌐 发布到 GitHub」一键提交推送，推上去后 Actions 自动构建上线
5. 第一次发布会弹出 GitHub 登录窗口，登录一次即可

**配色**页（可视化改主题，不用碰代码）：

- 直接列出 `assets/scss/custom.scss` 里的 CSS 变量，按暗色 / 亮色两栏并列：
  底色纸卡、文字、血锈红强调、代码块表格引文、滚动条、案卷标签（锆蓝墨 + 丹砂红变体）
- 点色块选色：内置档案室色板（铁灰 / 纸黄 / 血锈红 / 锆蓝 / 丹砂…）+ 系统取色器 + 手填 hex；
  `rgba()` 项附带透明度滑块；装订线那种 `1px solid rgba(...)` 只换颜色、保留 `1px solid`
- 版式：卡片/标签圆角、正文字号、行距、胶片颗粒强度，都是滑块
- 字体：正文与标题的字体栈可下拉选预设或直接编辑
- 保存前自动备份到 `assets/scss/.theme-backups/`（留 8 份），「还原备份…」一键回退
- **改完立刻能看到**：如果本地预览正开着，保存后会自动刷新浏览器（Hugo 重建 CSS）

> 只做行级替换，不动注释与缩进，改完的 SCSS 仍然人手可读。

源码改动后重新打包：

```bat
cd blog-app
python blog_app.py --selftest          :: 改完先跑自测
python -m PyInstaller --noconfirm 博客助手.spec   :: 必须走 spec，theme_editor 是 hiddenimport
```

> 注意：发布前务必确认当前打开的是哪个博客文件夹（窗口标题会显示站点名），避免发错库。

## 写作

- 卷宗放在 `content/posts/`，每篇一个 Markdown 文件（或同名文件夹 + `index.md` + 图片）
- 库房 / 检索 / 登记簿三个页面在 `content/page/` 下，地址已在各自 front matter 里指定
- 字体与配色等视觉定制集中在 `assets/scss/custom.scss`，盖戳动效与传阅计数在 `assets/ts/custom.ts`
- 传阅次数：本机 localStorage 计数（无需后端），换设备不累计；想要真实全站计数可后续接入 umami / busuanzi

## 部署

- 线上地址：<https://tsimin-organic.github.io/blog_yunost-zerkalo/>
- `.github/workflows/deploy.yml` 在每次 push 时自动构建发布
- Pages 由 `configure-pages` 的 `enablement: true` **自动开启**，不用手动去 Settings 选 Source
- 主题已直接打包在本仓库 `themes/stack/` 内（非子模块），clone 即用，无需 `git submodule update --init`
- 上传方式：双击 `上传到GitHub.bat`，或在助手里点「🌐 发布到 GitHub」

## 踩坑记录（换电脑重来时先看这里）

全是一次次撞出来的，按坑的类型分组。

### 一、上传到 GitHub

- **建仓库必须建空的。** 别勾 `Add README` / `.gitignore` / `license` —— 勾了远程就先有一个自己的提交，和本地没有共同祖先，push 会直接
  `! [rejected] main -> main (fetch first)`。许可证从本地加进去一起推才对。
- **GitHub 从 2021 年起不接受账号密码。** 输密码必然报
  `Password authentication is not supported for Git operations`。
  只能用浏览器授权，或用访问令牌（Settings → Developer settings → Personal access tokens → 勾 `repo`）。
- **浏览器授权必须点完。** GCM 打出 `please complete authentication in your browser...` 之后，
  如果没在网页里点绿色的 `Authorize`，就会 `fatal: 已取消一个任务`，
  然后 git 退回命令行问账号密码 —— 而那条路是死的（见上一条）。
- **提交邮箱别用裸用户名格式。** `yzr@users.noreply.github.com` 会被 GitHub 模糊匹配到
  用户名恰好叫 `yzr` 的**陌生人**，提交不算你的。正确格式要带数字 ID：

  ```powershell
  # ID 从 https://api.github.com/users/你的用户名 拿
  git config user.email "312572725+Tsimin-ORGANIC@users.noreply.github.com"
  ```

- **改历史里已经写错的作者**：

  ```powershell
  $env:GIT_SEQUENCE_EDITOR = 'true'    # 不加这句 rebase 会开编辑器卡住
  git rebase --root --exec "git commit --amend --no-edit --reset-author"
  git diff origin/main HEAD            # 必须是空的：只改了作者，没改内容
  git push --force-with-lease origin main   # 比 --force 安全：远程被别人动过会拒绝
  ```

### 二、Windows 脚本

- **`.bat` 里不要写中文。** cmd.exe 解析多字节 UTF-8 的批处理会错位断行，报出
  `'hub.com' is not recognized` 这种莫名其妙的错。
  做法：`.bat` 只当纯 ASCII 启动器，中文逻辑放进 `.ps1`。
- **`.ps1` 必须存成 UTF-8 带 BOM。** 否则 PowerShell 5.1 会按 GBK 解码，
  中文全乱并连带引发语法错误（`The string is missing the terminator`）。
- **PowerShell 里 `$home` 是只读变量**，不能赋值，换个名字（比如 `$html`）。
- **`if (git diff --quiet ...)` 判断的是输出而不是退出码。** 命令没输出会被当成假，
  要判断成败得用 `$LASTEXITCODE`。

### 三、Hugo 与内容

- **`draft: true` 的页面在生产构建里会消失。** 本地 `hugo server -D` 带 `-D` 参数，
  草稿也显示；GitHub Actions 构建不带 `-D`，于是线上直接没有这个页面。
  发文章前搜一遍 `draft: true`。
- **`public/` 会残留多份哈希 CSS。** Hugo 增量构建不清旧的，`--gc` 也不清。
  验证视觉改动时**要看 `index.html` 实际引用的那一份**，否则会被旧文件骗。
  彻底干净的做法：删掉整个 `public/` 重新构建。
- **主题的 meta description 取的是 `params.description`**，顶层 `description` 它不读——
  写在顶层等于没写。
- **Hugo 的 minifier 会改大小写**：hex 颜色转大写、字体名转小写。
  写 `.Contains()` 之类的检查时要按这个预期来。
- **改了 `hugo.toml` 要重启 `hugo server`**，配置项的热重载不可靠。

### 四、打包助手

- **必须走 spec**：`python -m PyInstaller --noconfirm 博客助手.spec`。
  直接 `PyInstaller blog_app.py` 会漏掉 `theme_editor`（运行时才 import 的模块），
  打出来的 exe 配色页会整块消失。spec 里已声明 `hiddenimports=['theme_editor']`。
- **打包前先关掉正在运行的助手**，exe 被占用会 `PermissionError: [WinError 5]`。
- **打包前跑一遍自测**：`python blog_app.py --selftest`
  （里面有 GUI 构造检查，能抓到"属性在赋值前被引用"这类只在运行时才炸的错）。

### 五、预览端口

- 助手内置端口探测：配置的端口被占用时会自动顺延到下一个空闲端口，并在消息栏告诉你实际地址。
- `预览.bat` 的端口是写死的，双击两次必然撞车（`bind: Only one usage of each socket address`）。
  先看浏览器能不能打开 1314，能打开就说明已经在跑了，不用再启动。

## 视觉规范速查

| 项 | 值 |
| --- | --- |
| 主背景（暗） | `#2A2C30`（铁灰蓝库房） |
| 卡片（暗） | `#36383D`（亮一档灰蓝纸卡，直角 + 装订线压痕） |
| 主背景（亮） | `#F7F6DC`（泛黄档案纸） |
| 卡片（亮） | `#FCFAEA` |
| 正文主色（暗） | `#D3C4B0`（褪色纸字） |
| 描述 / 次要文字（暗） | `#9D9589`（暖灰） |
| 正文（亮） | `#1F1D18`（墨黑） |
| 强调 | `#8B0000` / `#C24141`（血锈红，仅链接、戳记、警告） |
| 备用强调 | `#4E729E`（氧化锆蓝）、`#9E3C2D`（丹砂红，标签章随机色之一） |
| 标题字体 | 方正姚体（苏式海报方正骨架，子集化 woff2） |
| 噪点 | 内联 SVG feTurbulence 胶片颗粒，opacity 0.05 |

> 改这些值不用手改代码：打开助手的「配色」标签页，选色保存即可（会自动备份到
> `assets/scss/.theme-backups/`，可一键还原）。上表只是速查。

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

本站对「内容」和「代码」分别授权，这是静态站点博客的通行做法。
仓库根目录放了两个文件，对应这两部分：

| 部分 | 许可 | 说明 |
| --- | --- | --- |
| 正文内容（`content/` 下的文章与图片） | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh) | 详见 [`LICENSE-CONTENT.md`](LICENSE-CONTENT.md)；转载需署名、非商业、相同方式共享 |
| 站点定制代码（`assets/`、`layouts/`、`i18n/`、`tools/`、`blog-app/` 等） | [GPL-3.0](LICENSE) | 基于主题修改/扩展，随主题同协议发布 |
| [Stack 主题](https://github.com/CaiJimmy/hugo-theme-stack) | [GPL-3.0-only](https://github.com/CaiJimmy/hugo-theme-stack/blob/master/LICENSE) | 已直接打包在 `themes/stack/`（非 submodule），保留上游 LICENSE 与页脚署名 |
| 字体文件（`static/fonts/`） | 归各字体厂商 | 子集化自 Windows 系统字体，仅供本站显示，不得单独提取再分发 |

> GPL 只约束**代码**的传播，不会"传染"到你写的文章和图片上——内容是你的原创作品，版权完全属于你，采用 CC 协议即可，无需与 GPL 兼容。

© 2026 ZrYttrium
