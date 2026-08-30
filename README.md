# NXOpen Python API 查询工程（nxopen-api-query）

> **Siemens NX（UG）二次开发的 NXOpen Python API 查询与可视化工程**

一个面向 **Siemens NX 2212** 的 NXOpen Python API 工程，包含 **类型存根生成** → **思维导图可视化** → **全文检索引擎** 三条衔接的子项目，覆盖全部 **99 个模块、23,377 个类、41,501 个方法、48,017 个属性**（共 1,778 个 `.pyi` 类型存根）。

**NXOpen API 全景思维导图**： [nxopen-api-map](https://yybrook.github.io/nxopen-api-query/nxopen-api-map/viewer.html)

---

## 📚 工程概览

NXOpen 是 Siemens NX 提供的 Python 二次开发 API。由于其 `.pyd` 二进制模块无法直接获取类型信息，开发者在编写脚本时缺乏代码补全、类型检查和 API 查阅能力。本工程通过 **反射 → 解析 → 索引/可视化** 的三段管线，完整解决这一问题：

| 子项目 | 作用 | 输出 | 面向 |
|--------|------|------|------|
| [make-nxopen-pyi](./make-nxopen-pyi) | 在 NX 内置 Python 环境中反射 `.pyd`，生成 `.pyi` 类型存根 | `NXOpen/*.pyi`（约 1,778 个文件） | 开发者 / 数据管线 |
| [nxopen-api-map](./nxopen-api-map) | 解析 `.pyi` → 中间 JSON → 精简 JS，渲染交互式思维导图 | `viewer.html` + `data/nxopen_data.js` | 开发者 / 学习者 |
| [nxopen-api-query-skill](./nxopen-api-query-skill) | 从中间 JSON 构建 SQLite+FTS5 索引，提供毫秒级查询 | `nxopen_api.db` + `nxopen_query.py` | Agent / 开发者 |

---

## 🔄 数据管线

```
NXOpen_*.pyd                make-nxopen-pyi             nxopen-api-map             nxopen-api-query-skill
(Siemens NX 2212)           (反射生成 .pyi)             (解析/精简/分组)            (索引/查询)
    │                            │                          │                            │
    │                            ▼                          ▼                            ▼
    │                    NXOpen/*.pyi (~62MB)      nxopen_structure.json.gz   data/nxopen_data.js
    │                    (1,778 个类型存根)        (~3.5MB，中间 JSON)         (~24.9MB，前端数据)
    │                                          parse_pyi.py →                gen_js.py →
    │                                          gen_js.py →                   viewer.html
    │                                          ↓
    │                                          ↘ build_index.py  → nxopen_api.db (~160MB)
    │                                                                ↗ nxopen_query.py
    └──────────────────────────────────────────▶  data/nxopen_structure.json.gz  ◀──────────────────┘
                                                (由 nxopen-api-map/parse_pyi.py 产出，随仓库分发)
```

**管线说明：**

1. **生成 `.pyi`**（`make-nxopen-pyi`）：在 NX 内置 Python 环境中运行 `make_pyi.py`，反射扫描所有 `NXOpen_*.pyd` 模块，生成类型存根文件夹。需要 **安装 Siemens NX 软件**。
2. **解析为中间 JSON**（`nxopen-api-map`）：运行 `scripts/parse_pyi.py --source <NXOpen文件夹>`，使用 Python `ast` + 状态机 docstring 解析，输出 `nxopen_structure.json.gz`（随仓库分发）。
3. **生成前端数据**（`nxopen-api-map`）：运行 `scripts/gen_js.py`，将中间 JSON 精简为 `data/nxopen_data.js`，在 `viewer.html` 中渲染为 D3.js 思维导图。
4. **构建查询索引**（`nxopen-api-query-skill`）：运行 `scripts/build_index.py`，从 `data/nxopen_structure.json.gz` 构建 SQLite + FTS5 数据库 `data/nxopen_api.db`。
5. **执行查询**（`nxopen-api-query-skill`）：运行 `scripts/nxopen_query.py <command>`，提供类/方法/属性查询、名称验证、全文搜索、继承浏览等功能。

> `nxopen_structure.json.gz` 是管线的枢纽数据：由上游 `nxopen-api-map` 产出并随仓库分发，`nxopen-api-query-skill` 直接消费它构建数据库。

---

## 🗺 数据统计

| 指标 | 数量 |
|------|------|
| 类型存根文件 | 1,778 |
| 顶层模块 | 99 |
| 功能域 | 12 |
| 类（含嵌套类） | 23,377 |
| 方法 | 41,501 |
| 属性 | 48,017 |
| 嵌套类 | 21,601 |
| 有许可证的方法/属性 | 27,371（30.6%） |
| SQLite 数据库体积 | ~160MB |

---

## 🔧 快速入门

### 查看 API（无需安装 NX）

```bash
# 1. 交互式思维导图 —— 浏览器直接打开（无需构建工具/后端）
start nxopen-api-map/viewer.html

# 2. 命令行查询 —— 毫秒级类/方法/属性搜索
cd nxopen-api-query-skill
python scripts/nxopen_query.py class "NXOpen.Body"
python scripts/nxopen_query.py search "face normal"
python scripts/nxopen_query.py count
```

> **首次运行** 查询脚本会自动从 `data/nxopen_structure.json.gz` 构建数据库（约 10 秒，一次性），后续查询直接使用已构建的 `data/nxopen_api.db`。

### 重新生成全部数据（需要安装 Siemens NX）

```bash
# 步骤 1：在 NX 内置 Python 环境中生成 .pyi 类型存根
# 将 make_pyi.py 放入 NX Journal/Script 入口执行，或：
# "<NX安装路径>\nxbin\python\python.exe" make-nxopen-pyi/make_pyi.py
# → 生成 ./NXOpen/ 文件夹

# 步骤 2：解析 .pyi → 中间 JSON
cd nxopen-api-map
python scripts/parse_pyi.py --source <path_to_NXOpen_folder>

# 步骤 3：生成前端数据
python scripts/gen_js.py
# → data/nxopen_data.js（供 viewer.html 使用）

# 步骤 4：构建查询数据库
cd ../nxopen-api-query-skill
python scripts/build_index.py
# → data/nxopen_api.db（供 nxopen_query.py 查询）
```

---

## 📁 工程结构

```
nxopen-api-query/
├── README.md                    ← 本文件（工程总览）
├── pyproject.toml               ← 工程元信息
├── .gitignore                   ← 根级忽略规则（Python/IDE/系统/虚拟环境）
├── LICENSE                      ← MIT 许可证
├── make-nxopen-pyi/             ← 子项目 1：类型存根生成
│   ├── README.md
│   ├── make_pyi.py              ← 反射生成 .pyi 的主脚本（在 NX 内置 Python 中运行）
│   ├── .gitignore               ← 忽略 *NXOpen（生成的存根目录）
│   └── NXOpen/                  ← 生成的类型存根输出目录（.gitignore 忽略）
│       ├── __init__.py
│       ├── _nxopen.pyi
│       ├── <模块>.pyi           （约 99 个顶层模块）
│       └── clss/                （约 1,679 个类存根）
├── nxopen-api-map/              ← 子项目 2：思维导图可视化
│   ├── README.md
│   ├── AGENTS.md                ← 开发/维护说明
│   ├── viewer.html              ← 主页面（HTML 结构）
│   ├── viewer.css               ← 样式表
│   ├── app.js                   ← 交互逻辑（D3.js v7）
│   ├── .gitignore               ← 忽略 *nxopen_structure.json（仅分发 .gz）
│   ├── doc/
│   │   ├── pyi-structure.md     ← .pyi 类型存根结构详解
│   │   ├── json-structure.md    ← 中间 JSON 结构说明
│   │   └── js-structure.md      ← 精简 JS 数据结构说明
│   ├── scripts/
│   │   ├── parse_pyi.py         ← .pyi → 中间 JSON（AST + 状态机 docstring 解析）
│   │   ├── gen_js.py            ← 中间 JSON → 精简 JS（分组 + 继承解析）
│   │   ├── domains.py           ← 功能域映射表（12 域 → 99 模块）
│   │   └── compress.py          ← JSON 压缩/解压工具
│   └── data/
│       ├── nxopen_data.js       ← 精简前端数据（~24.9MB，由 gen_js.py 生成）
│       └── nxopen_structure.json.gz ← 压缩中间 JSON（~3.5MB，随仓库分发）
└── nxopen-api-query-skill/      ← 子项目 3：Agent Skill + 查询工具
    ├── README.md
    ├── SKILL.md                 ← Skill 入口（frontmatter + Agent 使用指令）
    ├── AGENTS.md                ← 开发/维护说明
    ├── .gitignore               ← 忽略 *nxopen_api.db / *nxopen_structure.json
    ├── doc/
    │   ├── json-structure.md    ← 中间 JSON 结构说明
    │   └── database-structure.md ← SQLite 数据库结构说明
    ├── data/
    │   ├── nxopen_api.db        ← SQLite 数据库（~160MB，首次运行自动生成）
    │   └── nxopen_structure.json.gz ← 源数据（~3.2MB，随 skill 分发）
    └── scripts/
        ├── build_index.py       ← 索引构建脚本（JSON/gz → SQLite + FTS5）
        ├── compress.py          ← JSON 压缩/解压工具（通用）
        ├── domains.py           ← 功能域映射表（12 域 → 99 模块）
        └── nxopen_query.py      ← 查询引擎 / 命令行工具（10 个子命令）
```

---

## 📖 子项目详情

### 1. make-nxopen-pyi — 类型存根生成

> ⚠️ **需要安装 Siemens NX 软件**，脚本必须在 NX 内置的 Python 环境中运行。

通过反射（introspection）技术扫描 NX 安装目录下的所有 `NXOpen_*.pyd` 二进制模块，提取类、方法、属性、成员等信息，自动生成 Python 类型存根（`.pyi`）文件。使 VS Code / PyCharm 等 IDE 获得完整的 NXOpen 智能提示能力。

- **输入**：`NXOpen_*.pyd`（Siemens NX 2212 内置）
- **输出**：`NXOpen/` 文件夹（1,778 个 `.pyi` 文件）
- **技术**：Python 反射 + `types` 模块类型检测 + 正则 rtype 解析
- **运行方式**：NX Journal/Script 入口，或 `nxbin/python/python.exe make_pyi.py`

👉 [更多说明](./make-nxopen-pyi/README.md)

### 2. nxopen-api-map — 交互式思维导图

一个**纯静态网页**项目（HTML/CSS/JS + D3.js v7，无需构建工具和后端服务），将 NXOpen Python API 可视化为三层交互式思维导图（功能域 → 模块 → 类）。

- **功能**：三层思维导图、全局搜索（类/方法/属性）、类型链接跳转、继承关系浏览、许可证信息显示
- **数据来源**：`make-nxopen-pyi` 生成的 `.pyi` → `parse_pyi.py` 解析为 JSON → `gen_js.py` 精简为 JS
- **12 个功能域**：核心基础、建模与特征、制图与标注、装配与产品数据、仿真分析、制造加工、运动与机构、电气与管路布线、模具与复合材料、编程与定制、报告与可视化、行业专用

👉 [更多说明](./nxopen-api-map/README.md) · [开发说明](./nxopen-api-map/AGENTS.md)

### 3. nxopen-api-query-skill — Agent Skill + 查询工具

一个 **Agent Skill**，将 1,778 个 `.pyi` 类型存根构建为 SQLite + FTS5 全文索引，提供毫秒级的类/方法/属性查询。同时可作为**独立命令行工具**使用。

- **10 个子命令**：`search` / `class` / `method` / `verify` / `module` / `inherit` / `suggest` / `modules` / `count` / `batch`
- **搜索技术**：FTS5 trigram（类名/方法名子串匹配） + unicode61（描述参数/返回值词级搜索） + BM25 排序
- **环境要求**：SQLite ≥ 3.34.0（trigram 分词器引入版本）

```bash
python scripts/nxopen_query.py class "NXOpen.Body"    # 类详情
python scripts/nxopen_query.py method "Create" --cls "Body"  # 方法搜索
python scripts/nxopen_query.py search "face normal"   # 全文搜索
python scripts/nxopen_query.py verify "NXOpen.Body"   # 名称验证
python scripts/nxopen_query.py inherit "NXOpen.Body"  # 继承关系
```

👉 [更多说明](./nxopen-api-query-skill/README.md) · [Skill 入口](./nxopen-api-query-skill/SKILL.md) · [开发说明](./nxopen-api-query-skill/AGENTS.md)

---

## 📝 使用场景

| 场景 | 推荐工具 |
|------|----------|
| 编写 NX Python 脚本，需 IDE 补全/类型检查 | `make-nxopen-pyi` → 将生成的 `NXOpen/` 放入 `site-packages` |
| 浏览/学习 NXOpen API 的类继承与模块分布 | `nxopen-api-map`（浏览器打开 `viewer.html`） |
| 查询某个类的方法签名、参数、返回值 | `nxopen-api-query-skill` → `nxopen_query.py class "ClassName"` |
| 验证 API 名称是否正确（防拼写错误） | `nxopen-api-query-skill` → `nxopen_query.py verify "Name"` |
| 搜索相关 API（按功能描述） | `nxopen-api-query-skill` → `nxopen_query.py search "关键词"` |
| 查看类之间的继承关系 | `nxopen-api-query-skill` → `nxopen_query.py inherit "ClassName"` |
| Agent 在 NX 二次开发时查阅 API | 加载 `nxopen-api-query-skill` 作为 Skill |

---

## 🏗️ 技术栈

| 子项目 | 语言/框架 | 依赖 |
|--------|-----------|------|
| make-nxopen-pyi | Python 3 | `NXOpen`（NX 内置）、标准库（`types`/`os`/`re`/`importlib`） |
| nxopen-api-map | Python 3 + HTML/CSS/JS | `ast`（标准库）、D3.js v7（CDN） |
| nxopen-api-query-skill | Python 3 | `sqlite3`（标准库，含 FTS5/trigram）、`json`/`os`/`sys`/`re` |

---

## ⚡ 环境要求

- **Siemens NX 2212**（用于生成 `.pyi`，仅 `make-nxopen-pyi` 需要）
- **Python 3.10+**（`requires-python >= 3.10.6`）
- **SQLite ≥ 3.34.0**（`nxopen-api-query-skill` 硬性要求，trigram 分词器）

```bash
# 检查 SQLite 版本
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

---

## 📄 许可证

本项目使用 [MIT License](./LICENSE)。

> **声明**：本工程仅包含从 Siemens NX 的二进制模块反射生成的类型存根和查询工具，不包含 Siemens NX 的任何专有内容。NXOpen API 的版权归 Siemens 公司所有。

---

## 🙏 致谢

- [D3.js](https://d3js.org/) —— 思维导图渲染引擎
- [unm001 的博客](https://www.cnblogs.com/unm001/p/16259771.html) —— NXOpen Python API 二次开发参考

---

## 🎯 项目远景

该工程旨在为 Siemens NX 的 Python 二次开发者提供一个**完整的 API 查询生态**：从类型存根生成、到可视化浏览、再到全文检索引擎。无论是 AI Agent 辅助开发，还是人工查阅 API，都能快速定位到所需的类、方法、参数和返回值，提升开发效率和准确性。
