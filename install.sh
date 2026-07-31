#!/usr/bin/env bash
# AI 简历 — 一键安装：创建 .venv 并安装 requirements.txt
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> 仓库目录: $ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未找到 python3，请先安装 Python 3.9+"
  exit 1
fi

PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_OK="$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 9) else 0)')"
if [[ "$PY_OK" != "1" ]]; then
  echo "[错误] 需要 Python 3.9+，当前为 $PY_VER"
  exit 1
fi
echo "==> Python $PY_VER"

if [[ ! -d .venv ]]; then
  echo "==> 创建虚拟环境 .venv"
  python3 -m venv .venv
else
  echo "==> 复用已有 .venv"
fi

VENV_PIP="${ROOT}/.venv/bin/pip"
VENV_PY="${ROOT}/.venv/bin/python"
if [[ ! -x "${VENV_PIP}" ]]; then
  echo "[错误] .venv 不完整，请删除 .venv 后重试"
  exit 1
fi

echo "==> 安装依赖 (requirements.txt)"
"${VENV_PIP}" install -r requirements.txt

HAS_CHROME=0
if [[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]] \
  || [[ -x "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing" ]] \
  || [[ -x "/Applications/Chromium.app/Contents/MacOS/Chromium" ]] \
  || command -v google-chrome >/dev/null 2>&1 \
  || command -v chromium >/dev/null 2>&1 \
  || command -v chromium-browser >/dev/null 2>&1; then
  HAS_CHROME=1
fi

echo ""
echo "[ok] 依赖已安装"
echo "     python: ${VENV_PY}"
echo ""
echo "接下来:"
echo "1. 用 Cursor 打开本仓库根目录（才能加载 .cursor/skills）"
echo "2. 新开终端时激活环境:"
echo "     source .venv/bin/activate"
echo "   Windows:"
echo "     .venv\\Scripts\\activate"
echo "3. 将简历放入 inbox/（例如 inbox/张三.docx）"
echo "   可选: 复制 inbox/_template.md 为 inbox/张三.md，填写 JD / 额外要求 / 六维开关"
echo "4. 在 Cursor 对话中输入: 简历优化"
echo "   或使用命令: /resume"
echo "5. 等待 Agent 自动跑完: 抽段 -> 改写 -> 保版式回写 -> 报告 -> 验收"
echo "6. 在 outbox/ 查看最终产出（优化版或定制版简历，以及 PNG/HTML 报告）"
echo ""
if [[ "${HAS_CHROME}" -eq 1 ]]; then
  echo "说明: 已检测到 Chrome/Chromium，报告 PNG 可自动截图生成。"
else
  echo "说明: 未检测到 Chrome/Chromium。流程仍可跑通，报告可能只有 HTML；"
  echo "      请用浏览器打开 outbox 下对应 .html 后自行截长图。安装 Chrome 后重跑渲染即可出 PNG。"
fi
echo "更完整说明见 README.md"
echo ""

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
  echo "[ok] 已在当前 shell 激活 .venv（因使用了 source install.sh）"
fi
