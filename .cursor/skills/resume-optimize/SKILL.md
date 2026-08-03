---
name: resume-optimize
description: AI 简历。用户说「简历优化」时，在 Cursor 中一句指令自动跑通抽段/改写/回写/报告/验收。主打前端提示词；其他岗位可扩展 prompts。只改文案、不动版式；有 JD 出定制版，无 JD 出通用优化版。
disable-model-invocation: true
---

# AI 简历

## 触发语

用户输入 **`简历优化`**（或同义：优化inbox / `/resume`）时执行本 Skill；**一句指令自动跑完整条流程**。

## 定位

- 项目名：**AI 简历**
- **Cursor 一句指令自动化**：抽段 → 改写 → 保版式回写 → 对比/诊断报告 → 验收
- **主打前端**（当前 `prompts/` 为前端专用）；其他岗位可自行扩展提示词后复用本流程
- 只改文案、不动版式；按工作年限对标**该档完美简历**；模型用 **Cursor Agent**
  - 提示词：
  - 通用润色：`prompts/copy_only_zh.txt`（不夸大不编造 + 该档完美标准 + 输出前自检）
  - JD 定制：`prompts/frontend_jd_tailor_zh.txt`（不夸大不编造 + JD 定向 + 技能回填）
  - 优化诊断：`prompts/resume_review_zh.txt`（按同档位尺子打分）
  - Diff 结构大纲：`prompts/diff_outline_zh.txt`（优先保留原稿分类，不合理再改优）

### 改写铁律（产出质量）

1. **不夸大、不编造（最高优先级）**：不得虚构或放大技术栈、项目、公司、职级、职责边界、团队规模、管理/带人、架构负责人身份、业务结果与数字。一次做透 ≠ 编造事实；只能在原文依据内改表述、结构、检索词回填。拿不准就不写、不抬档、不硬贴量化。
2. **具体问题具体分析**：先推断年限档位（junior/mid/senior/staff）与本简历相对「该档完美简历」的 3–5 个缺口，再改写。
3. **对标该档完美简历**：0–2 / 3–5 / 6–9 / 10+ 各有不同深度与口吻；目标是**可直接投递、少返工**的该档最佳水平，不是「略好一点」。禁止低年限装资深、高年限只换动词。
4. **一次做透**：职责 / 项目 / 自我评价 / 技能区凡未达标必须改到位；仅姓名、电话、邮箱、纯日期、纯链接可无故保持原文。做透的是表述与结构，不是补造经历。
5. **禁止浅改充数**：仅换「负责→主导」、加「技术栈：」、HTML→HTML5 且无信息增益 → 不合格，需重写该条。
6. **技能区必须认真处理**：从全文（含项目技术栈）**有选择地**回填已有依据的关键词；只回填对**当前热门主流前端岗位 JD**仍常见、可检索的技术；项目里偶发的冷门库/工具/私有封装**不必**进专业技能（留在项目技术栈即可）。同技术不同写法由模型语义判断；无故整段原样视为不合格；全文没有的词禁止写入。
7. **量化克制（宁缺毋滥）**：有机制才可保守估算且须 note 核对；同一项目不要条条贴百分比；已有数字不改大；无机制则写清手段与可感知结果，不硬编百分比。

## 输入文件

| inbox | 必须 | 说明 |
|-------|------|------|
| `<stem>.docx` / `<stem>.pdf` | 是 | 原简历 |
| `<stem>.md` | 否 | JD + 额外要求 + 可选六维开关（见 `inbox/_template.md`） |

解析配置：

```bash
python scripts/parse_inbox_config.py --stem "<stem>"
```

- `has_jd: true` → **只走 JD 分支**（不产出通用版终稿文件）
- `has_jd: false` → **只走通用分支**
- `requirements` 注入对应分支的提示词

六维优化开关：以 `parse_inbox_config.py` 输出的 `dimensions` 为准（默认全开；可在 `<stem>.md` 的「六维优化」段关闭单项，见 `inbox/_template.md`）。

## 选文件

1. 扫描 `inbox/` 下 `.docx` / `.pdf`（忽略 `_template.md` 等）
2. **未优化**判定：
   - 无 JD：`outbox/<stem>_优化版.*` 且 `outbox/<stem>_diff.png` 且 `outbox/<stem>_review_report.png` 缺一即未优化
   - 有 JD：`outbox/<stem>_定制版.*` 且 `_diff_jd.png` 且 `_jd_report.png` 且 `_review_report.png` 缺一即未优化
3. 未优化数量：0 → 提示放入文件；1 → 直接处理；≥2 → 列出选项等用户选择

## 步骤

工作目录：仓库根目录，先 `source .venv/bin/activate`。

1. `python scripts/parse_inbox_config.py --stem "<stem>"` 判断分支
2. `python scripts/extract_segments.py --input "inbox/<file>"`
3. **分支 A（无 JD）**：
   - `python scripts/merge_replacements.py scaffold -s "jsons/<stem>_segments.json" -o "jsons/<stem>_replacements.scaffold.json"`
   - 读 `prompts/copy_only_zh.txt` + 额外要求 + 六维 + **scaffold**（`editable` 条目；**禁止改 id/original**）
   - 模型产出 patch 后必须合并：  
     `python scripts/merge_replacements.py merge -s "jsons/<stem>_segments.json" -p "<patch.json>" -o "jsons/<stem>_replacements.json"`  
     （合并时 **original 一律以 segments 为准**，只采纳 rewritten/note，从根源杜绝串条）
   - 禁止手改整份 replacements 时「凭记忆填 id」；单条修改用：  
     `python scripts/merge_replacements.py set -r "jsons/<stem>_replacements.json" -s "jsons/<stem>_segments.json" --id p-xx --rewritten "..." --note "..."`
   - 读 `prompts/diff_outline_zh.txt` + segments → `jsons/<stem>_diff_outline.json`
   - 读 `prompts/resume_review_zh.txt` + 优化前/后 → `jsons/<stem>_review_report.json`
   - `python scripts/apply_replacements.py -i "inbox/<file>" -r "jsons/<stem>_replacements.json" -s "jsons/<stem>_segments.json"`
   - `python scripts/render_diff_report.py -r "jsons/<stem>_replacements.json" --outline "jsons/<stem>_diff_outline.json" --review "jsons/<stem>_review_report.json"`
   - `python scripts/render_review_report.py -i "jsons/<stem>_review_report.json"`
   - `python scripts/verify_outbox.py --stem "<stem>"`（正文 + note + diff 说明；不通过则不应结束流程）
4. **分支 B（有 JD）**：
   - scaffold → 按年限档位 + JD 缺口诊断后改写（锁定 id/original）→ `merge_replacements.py merge` 产出 `jsons/<stem>_replacements_jd.json`
   - 读 `prompts/diff_outline_zh.txt` + segments，写 `jsons/<stem>_diff_outline.json`
   - 读 `prompts/resume_review_zh.txt` + 优化前/后文本，写 `jsons/<stem>_review_report.json`
   - `python scripts/apply_replacements.py -i "inbox/<file>" -r "jsons/<stem>_replacements_jd.json" -s "jsons/<stem>_segments.json" --jd`
   - `python scripts/render_diff_report.py -r "jsons/<stem>_replacements_jd.json" --outline "jsons/<stem>_diff_outline.json" --review "jsons/<stem>_review_report.json"`
   - Auto 生成 `jsons/<stem>_jd_report.json`（紧凑 JSON，字段见下）
   - `python scripts/render_jd_report.py -i "jsons/<stem>_jd_report.json"`
   - `python scripts/render_review_report.py -i "jsons/<stem>_review_report.json"`
   - `python scripts/verify_outbox.py --stem "<stem>" --jd`
5. 汇报 outbox 路径与最终产出清单；**验收未通过则不应结束流程**

### 防串条铁律（根源）

| 错误做法 | 正确做法 |
|---------|---------|
| 凭记忆改 `p-54` 的 rewritten/note | `merge_replacements.py set --id …` 或 merge |
| 让模型从零输出整份数组并直接当终稿 | 先 scaffold，模型只改 rewritten/note，再 **merge** |
| 用另一条的说明/文案覆盖标题 | original 锁定自 segments，merge 不会改 original |

### `_replacements.json` / `_replacements_jd.json` 字段

```json
[
  {
    "id": "p-14",
    "original": "负责某某产品研发与迭代",
    "rewritten": "主导某某产品核心链路研发与迭代",
    "note": "将「负责」改为「主导」并点明核心链路，突出职责边界与影响力"
  },
  {
    "id": "p-1",
    "original": "张三",
    "rewritten": "张三",
    "note": ""
  }
]
```

- `note`：改动说明（一句），解释改了什么、目的或提升效果；对比 PNG 在每条 `-/+` 下以灰色文案展示
- 未改写条目：`note` 必须为 `""`
- **量化估算**：原文有动作缺数字时，按行业常见保守区间写入 `rewritten`；该类 `note` 须含「可按实际调整」

### `_diff_outline.json` 字段

模型根据 segments 识别层级；**优先保留原稿分类名**，仅当不合理时改优。

```json
{
  "items": [
    {
      "id": "p-5",
      "section": "专业技能",
      "subsection": "",
      "label": "语言基础",
      "section_original": "专业技能",
      "renamed": false,
      "reason": ""
    },
    {
      "id": "p-14",
      "section": "工作经历",
      "subsection": "顺丰科技",
      "label": "职责描述",
      "section_original": "职业履历",
      "renamed": true,
      "reason": "原稿分类不规范，改为行业通用名"
    }
  ]
}
```

### `_review_report.json` 字段

```json
{
  "title": "简历优化诊断",
  "score": 91,
  "score_before": 68,
  "tags": ["语言表达增强", "职责边界细化", "ATS关键词补强"],
  "strengths": ["大厂/核心业务背景", "Vue/React 双栈"],
  "weaknesses": ["部分技术指标仍待补充", "早期项目可再加厚"],
  "dimensions": [
    {"name": "ATS 关键词", "score": 93, "score_before": 72, "comment": "技术栈覆盖较全，可补充工程化关键词"},
    {"name": "结构优化", "score": 90, "score_before": 78, "comment": "模块齐全，项目描述可再突出难点"},
    {"name": "量化表述", "score": 82, "score_before": 70, "comment": "多数经历缺指标，建议补充性能/效率数据"},
    {"name": "技能匹配", "score": 92, "score_before": 80, "comment": "技能与项目技术栈基本一致"},
    {"name": "语言表达", "score": 93, "score_before": 66, "comment": "整体专业，个别条目可更精炼"},
    {"name": "亮点提炼", "score": 91, "score_before": 68, "comment": "有大厂与复杂项目，但价值点可更前置"}
  ],
  "suggestions": ["补充冷启动/性能优化具体指标"],
  "next_steps": ["核对联系方式与在职状态"]
}
```

- `score` / `score_before`：优化后 / 优化前（原稿）综合分
- **`_review_report.html/png` 只展示原稿分**（`score_before` 与各维 `score_before`）
- **`_diff.png` 顶部评分卡**展示优化后分、提升分与标签（`score_before` 只用于算 Δ，界面不展示优化前分）
- 评分口径：实质改写后优化后分通常 **88–94**，分差常见 **+14～+22**（见 `prompts/resume_review_zh.txt`）
- `tags`：提升类型短标签（增强/补强/提升/细化等），展示在 diff 顶部

### `_jd_report.json` 字段

**关键词匹配硬规则（必须遵守）：**
- `matched_keywords` / `missing_keywords` 必须对比**简历全文**判定，至少包括：专业技能、工作职责、项目简介、**项目技术栈行**、自我评价
- **禁止只扫「专业技能」区**：技术词常出现在项目技术栈（如 `Node.js`、`react-i18next`、`vue-i18n`），技能区未单列也算**已匹配**
- 仅当全文（含项目技术栈）均无依据时，才可列入 `missing_keywords`
- `weak_points` 不得写「未在简历中体现」，若该词其实出现在项目技术栈/职责中
- 若关键词在项目技术栈有、专业技能区没有：记为 **matched**；仅当该词属于主流前端 JD 常见检索词时，才可在 `weak_points` / `next_steps` 建议「回填专业技能区」；冷门库不必建议回填；**禁止**因技能区未列而标成缺失
- **同技术不同写法**：由模型基于语义自行判断是否等价（如 i18n / 国际化 / react-i18next），**不维护、不依赖固定别名表**；有合理依据即算已匹配

```json
{
  "title": "岗位匹配诊断",
  "score": 85,
  "matched_keywords": ["React", "TypeScript", "Node.js", "国际化 / i18n"],
  "missing_keywords": ["微前端", "React Native"],
  "weak_points": ["Node.js / i18n 已在项目技术栈出现，建议回填专业技能区便于检索"],
  "next_steps": ["面试前准备组件设计题"]
}
```

## 最终产出（互斥）

| 场景 | 文件 |
|------|------|
| 无 JD | `<stem>_优化版.docx/pdf` + `<stem>_diff.png` + `<stem>_review_report.png` |
| 有 JD | `<stem>_定制版.docx/pdf` + `<stem>_diff_jd.png` + `<stem>_jd_report.png` + `<stem>_review_report.png` |

**通常无需外传：** 任何 `.txt`、`.md`、`.json`、`.html`（HTML 仅供本地预览/调样式）。中间 JSON 一律放 `jsons/`，最终产出与 HTML/PNG 预览放 `outbox/`。

## 禁止

- 换模板、改版式建议
- 覆盖 inbox 原件
- 夸大或编造技术栈、公司/项目、职级、职责范围、结果与数字；量化仅允许在有机制依据时按保守区间估算并 note 请按实绩核对，禁止夸张吹嘘与无依据硬贴
- 同一次流程同时产出通用版与 JD 版终稿
- 把 HTML 当终稿（HTML 仅本地预览，终稿用 PNG）
