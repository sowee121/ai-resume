# AI Resume — 前端简历保样式优化

用 **Cursor** 做前端简历文案优化：**只改文字、不动版式**。按候选人工作年限对标该档完美简历；支持通用润色与 JD 定制（互斥）。脚本负责抽段、保样式回写、报告截图与验收。

铁律：**不夸大、不编造**——只在原文依据内改表述与结构；量化宁缺毋滥。

## 环境要求

- [Cursor](https://cursor.com/)
- Python 3.9+
- Google Chrome（用于报告 PNG 截图；没有则只出 HTML）

## 安装

```bash
git clone <your-repo-url>
cd "AI Resume"   # 或你的克隆目录名
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

用 Cursor 打开本仓库即可加载 Skill（`.cursor/skills/`）。

## 快速使用

1. 将简历放入 `inbox/`（`.docx` 或 `.pdf`）
2. 可选：复制 `inbox/_template.md` → `inbox/<stem>.md`，填写 JD 与额外要求
3. 在 Cursor 对话中输入：

```text
简历优化
```

或使用 `/resume`。多份未优化简历时会列出选项供选择。

## 输入（inbox）

| 文件 | 必须 | 说明 |
|------|------|------|
| `<stem>.docx` 或 `<stem>.pdf` | 是 | 原简历 |
| `<stem>.md` | 否 | JD + 额外要求（见 `inbox/_template.md`） |
| `optimization_defaults.yaml` | 仓库默认 | 六维开关（一般无需改） |

`<stem>` = 文件名去掉扩展名（如 `张三.docx` → `张三`）。

### 分支（互斥）

- **JD 非空** → 只产出定制版交付包  
- **无 JD** → 只产出通用优化版交付包  

## 客户交付（outbox）

| 场景 | 文件 |
|------|------|
| 无 JD | `<stem>_优化版.docx/pdf` + `<stem>_diff.png` + `<stem>_review_report.png` |
| 有 JD | `<stem>_定制版.docx/pdf` + `<stem>_diff_jd.png` + `<stem>_jd_report.png` + `<stem>_review_report.png` |

中间 JSON 在 `jsons/`；HTML 仅本地预览。均不发给客户。

## 提示词与脚本

| 路径 | 用途 |
|------|------|
| `prompts/copy_only_zh.txt` | 通用改写 |
| `prompts/frontend_jd_tailor_zh.txt` | JD 定制改写 |
| `prompts/resume_review_zh.txt` | 优化诊断评分 |
| `prompts/diff_outline_zh.txt` | 对照报告层级大纲 |
| `scripts/*.py` | 抽段 / 合并 / 回写 / 渲染 / 验收 |

手动流水线示例见下方；日常推荐直接对话触发 Skill。

### 手动流水线（通用）

```bash
source .venv/bin/activate
python scripts/parse_inbox_config.py --stem "张三"
python scripts/extract_segments.py --input "inbox/张三.docx"
# 由 Cursor Agent 按 prompts 生成 jsons/ 下 replacements / outline / review_report
python scripts/apply_replacements.py -i "inbox/张三.docx" -r "jsons/张三_replacements.json"
python scripts/render_diff_report.py -r "jsons/张三_replacements.json" --outline "jsons/张三_diff_outline.json" --review "jsons/张三_review_report.json"
python scripts/render_review_report.py -i "jsons/张三_review_report.json"
python scripts/verify_outbox.py --stem "张三"
```

### 手动流水线（JD）

```bash
python scripts/apply_replacements.py -i "inbox/张三.docx" -r "jsons/张三_replacements_jd.json" --jd
python scripts/render_diff_report.py -r "jsons/张三_replacements_jd.json" --outline "jsons/张三_diff_outline.json" --review "jsons/张三_review_report.json" --title "JD定制改动对照"
python scripts/render_jd_report.py -i "jsons/张三_jd_report.json"
python scripts/render_review_report.py -i "jsons/张三_review_report.json"
python scripts/verify_outbox.py --stem "张三" --jd
```

## 工作区结构

```text
AI Resume/
  inbox/                            # 原件 + 配置（客户稿默认不入库）
  jsons/                            # 中间 JSON（不入库）
  outbox/                           # 交付与预览（不入库）
  scripts/                          # 管道脚本
  prompts/                          # 提示词
  templates/                        # 报告 HTML 模板
  .cursor/skills/resume-optimize/   # 主 Skill SOP
  .cursor/skills/resume/            # /resume 入口
  plan.md                           # 演进记录（可选阅读）
  requirements.txt
  LICENSE
```

## 许可

MIT License，见 [LICENSE](LICENSE)。
