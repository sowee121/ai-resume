# AI 简历 — 一键安装：创建 .venv 并安装 requirements.txt
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "==> 仓库目录: $Root"

function Find-Python {
  $candidates = @()
  if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += "python" }
  if (Get-Command py -ErrorAction SilentlyContinue) { $candidates += "py" }
  foreach ($c in $candidates) {
    try {
      if ($c -eq "py") {
        $ver = & py -3 -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        $ok = & py -3 -c "import sys; print(1 if sys.version_info >= (3, 9) else 0)" 2>$null
        if ($ok -eq "1") { return @{ Cmd = "py"; Args = @("-3"); Ver = $ver } }
      } else {
        $ver = & python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        $ok = & python -c "import sys; print(1 if sys.version_info >= (3, 9) else 0)" 2>$null
        if ($ok -eq "1") { return @{ Cmd = "python"; Args = @(); Ver = $ver } }
      }
    } catch { }
  }
  return $null
}

$Py = Find-Python
if (-not $Py) {
  Write-Host "[错误] 未找到 Python 3.9+，请先安装并确保 python 或 py 在 PATH 中"
  exit 1
}
Write-Host "==> Python $($Py.Ver)"

$VenvDir = Join-Path $Root ".venv"
if (-not (Test-Path $VenvDir)) {
  Write-Host "==> 创建虚拟环境 .venv"
  & $Py.Cmd @($Py.Args + @("-m", "venv", ".venv"))
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
  Write-Host "==> 复用已有 .venv"
}

$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPip)) {
  Write-Host "[错误] .venv 不完整，请删除 .venv 后重试"
  exit 1
}

Write-Host "==> 安装依赖 (requirements.txt)"
& $VenvPip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$HasChrome = $false
$chromePaths = @(
  "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "${env:LocalAppData}\Google\Chrome\Application\chrome.exe"
)
foreach ($p in $chromePaths) {
  if ($p -and (Test-Path $p)) { $HasChrome = $true; break }
}
if (-not $HasChrome) {
  if (Get-Command chrome -ErrorAction SilentlyContinue) { $HasChrome = $true }
  elseif (Get-Command chromium -ErrorAction SilentlyContinue) { $HasChrome = $true }
}

Write-Host ""
Write-Host "[ok] 依赖已安装"
Write-Host "     python: $VenvPy"
Write-Host ""
Write-Host "接下来:"
Write-Host "1. 用 Cursor 打开本仓库根目录（才能加载 .cursor/skills）"
Write-Host "2. 新开终端时激活环境:"
Write-Host "     .venv\Scripts\activate"
Write-Host "   macOS / Linux:"
Write-Host "     source .venv/bin/activate"
Write-Host "3. 将简历放入 inbox/（例如 inbox/张三.docx）"
Write-Host "   可选: 复制 inbox/_template.md 为 inbox/张三.md，填写 JD / 额外要求"
Write-Host "4. 在 Cursor 对话中输入: 简历优化"
Write-Host "   或使用命令: /resume"
Write-Host "5. 等待 Agent 自动跑完: 抽段 -> 改写 -> 保版式回写 -> 报告 -> 验收"
Write-Host "6. 在 outbox/ 查看最终产出（优化版或定制版简历，以及 PNG/HTML 报告）"
Write-Host ""
if ($HasChrome) {
  Write-Host "说明: 已检测到 Chrome/Chromium，报告 PNG 可自动截图生成。"
} else {
  Write-Host "说明: 未检测到 Chrome/Chromium。流程仍可跑通，报告可能只有 HTML；"
  Write-Host "      请用浏览器打开 outbox 下对应 .html 后自行截长图。安装 Chrome 后重跑渲染即可出 PNG。"
}
Write-Host "更完整说明见 README.md"
Write-Host ""
