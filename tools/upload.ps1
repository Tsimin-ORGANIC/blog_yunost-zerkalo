# 钇·锆·拾遗 · 一键上传到 GitHub
# 由 上传到GitHub.bat 调用；也可单独运行：
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\upload.ps1

$ErrorActionPreference = 'Continue'
$OutputEncoding = [System.Text.Encoding]::UTF8

# 仓库根 = 本脚本所在 tools/ 的上一级
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

function Pause-Exit($code) {
    Write-Host ""
    Read-Host "按回车键关闭" | Out-Null
    exit $code
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
    Write-Host " ★ 建仓库时不要勾选 Add README / .gitignore / license，"
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
$out = (git commit -m "更新站点内容" 2>&1 | Out-String)
if ($out -match 'nothing to commit|无文件要提交|未跟踪') {
    Write-Host "      没有需要提交的新改动。"
} elseif ($LASTEXITCODE -ne 0) {
    Write-Host "      提交时出问题了，原样输出如下："
    Write-Host $out
} else {
    Write-Host "      已提交。"
}
Write-Host ""

# ── 3. 推送 ───────────────────────────────────────────────────
Write-Host "[2/2] 推送到 GitHub……"
Write-Host ""
Write-Host "  第一次推送会弹出浏览器窗口让你登录 GitHub，"
Write-Host "  登录一次以后就不用再登了。"
Write-Host ""

git push -u origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host " 推送失败。对照下面的情况看看："
    Write-Host ""
    Write-Host " · 提示 Authentication failed / 登录失败"
    Write-Host "     -> 再运行一次本脚本，重新登录 GitHub"
    Write-Host ""
    Write-Host " · 提示 rejected / non-fast-forward"
    Write-Host "     -> 建仓库时勾了 README。删掉那个仓库，重建一个空仓库"
    Write-Host ""
    Write-Host " · 提示 repository not found"
    Write-Host "     -> 地址拼错了，或者那个仓库不属于你"
    Write-Host "============================================================"
    Pause-Exit 1
}

Write-Host ""
Write-Host "============================================================"
Write-Host " 上传成功！"
Write-Host "============================================================"
Write-Host ""
Write-Host " 接下来还有一步（只做一次）："
Write-Host ""
Write-Host "  1. 打开你的仓库网页"
Write-Host "  2. 点 Settings（设置）→ 左侧找 Pages"
Write-Host "  3. 把 Source（来源）选成 GitHub Actions"
Write-Host "  4. 回到仓库的 Actions 标签，等它跑完（约 1 分钟）"
Write-Host ""
Write-Host " 然后访问： https://你的用户名.github.io/仓库名/"
Write-Host ""
Write-Host " 以后写完文章，点助手里那个「发布到 GitHub」按钮就行，"
Write-Host " 或者再来双击一次本脚本。"
Pause-Exit 0
