# 钇·锆·拾遗 · 一键上传到 GitHub
# 由 上传到GitHub.bat 调用；也可单独运行：
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\upload.ps1

$ErrorActionPreference = 'Continue'

# 仓库根 = 本脚本所在 tools/ 的上一级
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

function Pause-Exit($code) {
    Write-Host ""
    Read-Host "按回车键关闭" | Out-Null
    exit $code
}

function Get-RepoParts($url) {
    if ($url -match 'github\.com[/:]([^/]+)/([^/]+?)(\.git)?/?$') {
        return @{ Owner = $Matches[1]; Name = $Matches[2] }
    }
    return $null
}

Write-Host "============================================================"
Write-Host "  钇·锆·拾遗 · 上传到 GitHub"
Write-Host "============================================================"
Write-Host ""

# ── 0. 检查 git ───────────────────────────────────────────────
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] 这台电脑没装 Git，没法上传。"
    Write-Host "       去 https://git-scm.com/download/win 安装后再试。"
    Pause-Exit 1
}

# ── 1. 远程仓库地址 ───────────────────────────────────────────
$remote = (git remote get-url origin 2>$null)
$needAsk = $true

if ($remote) {
    Write-Host "[当前远程仓库] $remote"
    Write-Host ""
    $ans = Read-Host "要更换仓库地址吗？直接回车 = 不用，输入 y 更换"
    if ($ans -notmatch '^[Yy]') { $needAsk = $false }
}

if ($needAsk) {
    Write-Host ""
    Write-Host "------------------------------------------------------------"
    Write-Host " 请先在 GitHub 网页上建一个【空的】仓库，然后复制它的地址"
    Write-Host " （形如 https://github.com/你的用户名/yunost-zerkalo.git）"
    Write-Host ""
    Write-Host " ★ 建仓库时不要勾 Add README / .gitignore / license，"
    Write-Host "   否则推送会被拒绝，得再来一次。"
    Write-Host "------------------------------------------------------------"
    Write-Host ""
    $url = Read-Host "把仓库地址粘贴到这里，然后按回车"
    if (-not $url -or -not $url.Trim()) {
        Write-Host ""
        Write-Host "[取消] 没填地址，什么也没做。"
        Pause-Exit 1
    }
    $url = $url.Trim()
    git remote remove origin 2>$null | Out-Null
    git remote add origin $url 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 这个地址 git 不认，检查一下有没有复制全。"
        Pause-Exit 1
    }
    Write-Host "[已设置] 远程仓库 = $url"
    Write-Host ""
}

# ── 2. 提交本地改动（没有改动也不算错）────────────────────────
Write-Host "[1/2] 整理本地改动……"
git add -A | Out-Null
$commitOut = (git commit -m "更新站点内容" 2>&1 | Out-String)
if ($commitOut -match 'nothing to commit|无文件要提交|未跟踪') {
    Write-Host "      没有需要提交的新改动。"
} elseif ($LASTEXITCODE -ne 0) {
    Write-Host "      提交时出问题了，原样输出如下："
    Write-Host $commitOut
} else {
    Write-Host "      已提交。"
}
Write-Host ""

# ── 3. 推送 ───────────────────────────────────────────────────
Write-Host "[2/2] 推送到 GitHub……"
Write-Host ""
Write-Host "  第一次推送会弹出浏览器窗口让你登录 GitHub，"
Write-Host "  ★ 一定要在弹出的网页里点绿色的 Authorize 按钮才算完成。"
Write-Host ""

$pushOut = (git push -u origin main 2>&1 | Out-String)
Write-Host $pushOut
$pushOk = ($LASTEXITCODE -eq 0)

# ── 4. 登录失败则改用访问令牌 ─────────────────────────────────
if (-not $pushOk -and $pushOut -match 'Authentication failed|Invalid username or token|could not read Username|terminal prompts disabled|denied|已取消|cancel') {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host " 登录没成功。"
    Write-Host ""
    Write-Host " 注意：GitHub 从 2021 年起就不再接受账号密码了，"
    Write-Host "       必须用「访问令牌」(Token) 或者浏览器授权。"
    Write-Host "============================================================"
    Write-Host ""
    Write-Host " 办法一：再跑一次本脚本，这回记得在浏览器里点 Authorize"
    Write-Host " 办法二：改用访问令牌，现在就能继续 ↓"
    Write-Host ""
    $ans = Read-Host "现在用访问令牌登录？(输入 y 继续，直接回车 = 先不用)"
    if ($ans -notmatch '^[Yy]') {
        Pause-Exit 1
    }

    Write-Host ""
    Write-Host "------------------------------------------------------------"
    Write-Host " 怎么拿令牌（一次性，约 1 分钟）："
    Write-Host ""
    Write-Host "  1. 浏览器打开  https://github.com/settings/tokens/new"
    Write-Host "  2. Note 随便填，比如：博客上传"
    Write-Host "  3. Expiration 选 90 days，或者 No expiration（不过期）"
    Write-Host "  4. 勾选第一项 repo（整个大框，包括下面的子项）"
    Write-Host "  5. 拉到最下面点 Generate token"
    Write-Host "  6. 复制那串 ghp_ 开头的字符"
    Write-Host "     ★ 离开这个页面就再也看不到了"
    Write-Host "------------------------------------------------------------"
    Write-Host ""
    $token = ''
    try {
        $sec = Read-Host "把令牌粘贴到这里（输入时不显示，粘完按回车）" -AsSecureString
        $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    } catch {
        $token = Read-Host "把令牌粘贴到这里，然后按回车"
    }
    $token = ($token -replace '\s', '')
    if (-not $token) {
        Write-Host ""
        Write-Host "[取消] 没填令牌。"
        Pause-Exit 1
    }

    $cleanUrl = (git remote get-url origin).Trim()
    $parts = Get-RepoParts $cleanUrl
    if (-not $parts) {
        Write-Host "[错误] 远程地址不是标准 GitHub 地址：$cleanUrl"
        Pause-Exit 1
    }
    $owner = $parts.Owner
    $name = $parts.Name

    Write-Host ""
    Write-Host "      正在用令牌推送……"
    $authUrl = "https://${owner}:$([uri]::EscapeDataString($token))@github.com/${owner}/${name}.git"
    git remote set-url origin $authUrl
    $pushOut2 = (git push -u origin main 2>&1 | Out-String)
    $pushOk2 = ($LASTEXITCODE -eq 0)
    # 不论成败都立刻把令牌从仓库配置里抹掉
    git remote set-url origin $cleanUrl

    if ($pushOk2) {
        $pushOk = $true
        Write-Host "      令牌有效，推送成功。"
        Write-Host ""
        Write-Host "      （令牌已从仓库配置里移除，改由系统的凭据管理器保存，"
        Write-Host "        以后不用再输。）"
    } else {
        Write-Host $pushOut2
        Write-Host ""
        Write-Host "============================================================"
        Write-Host " 用令牌推送也失败了。常见原因："
        Write-Host ""
        Write-Host " · 提示 Invalid username or token"
        Write-Host "     -> 令牌复制不全，或者生成时没勾 repo"
        Write-Host ""
        Write-Host " · 提示 repository not found"
        Write-Host "     -> 令牌所属账号没有这个仓库的权限"
        Write-Host ""
        Write-Host " · 提示 rejected / non-fast-forward"
        Write-Host "     -> 远程仓库不是空的，里面已经有提交了"
        Write-Host "============================================================"
        Pause-Exit 1
    }
}

if (-not $pushOk) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host " 推送失败，原样输出见上。"
    Write-Host " 如果看不懂，把上面的内容截图发出来。"
    Write-Host "============================================================"
    Pause-Exit 1
}

# ── 5. 成功 ───────────────────────────────────────────────────
$parts = Get-RepoParts (git remote get-url origin)
$pagesUrl = ''
if ($parts) {
    $pagesUrl = "https://$($parts.Owner.ToLower()).github.io/$($parts.Name)/"
}

Write-Host ""
Write-Host "============================================================"
Write-Host " 上传成功！"
Write-Host "============================================================"
Write-Host ""
Write-Host " 接下来还有一步（只做一次）："
Write-Host ""
Write-Host "  1. 打开你的仓库网页 Settings（设置）"
Write-Host "  2. 左侧菜单找 Pages"
Write-Host "  3. 把 Source（来源）选成 GitHub Actions"
Write-Host "  4. 回到仓库的 Actions 标签，等它跑完（约 1 分钟）"
Write-Host ""
if ($pagesUrl) {
    Write-Host " 然后访问： $pagesUrl"
    Write-Host ""
}
Write-Host " 以后写完文章，点助手里那个「发布到 GitHub」按钮就行，"
Write-Host " 或者再来双击一次本脚本。"
Pause-Exit 0
