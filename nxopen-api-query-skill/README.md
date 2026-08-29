# NXOpen Python API 查询工具

一个将 **Siemens NXOpen Python API**（1778 个 `.pyi` 类型存根）整理成 SQLite + FTS5 全文索引，提供毫秒级类/方法/属性查询的 **Agent Skill**（同时也是一个可独立运行的命令行工具）。

> 本项目是一个 **Agent Skill**：`SKILL.md` 为根入口（带 frontmatter 触发描述与 Agent 使用指令），AI 辅助工具可加载此 skill，让 Agent 在辅助 Siemens NX（UG）二次开发时快速、准确地查阅 NXOpen Python API 信息，而非凭记忆猜测。查询引擎 `scripts/nxopen_query.py` 也可脱离 skill 作为普通命令行工具独立使用。

> **API 来源**：本项目基于 **Siemens NX 2212** 版本的 NXOpen Python API。
> `.pyi` 类型存根由 NX 2212 的 `NXOpen_*.pyd` 二进制模块经反射工具解析生成，
> 由上游项目 `nxopen-api-map` 解析为 `nxopen_structure.json.gz`，共约 1778 个 `.pyi` 文件，覆盖 99 个顶层模块。

覆盖全部 99 个模块、23,377 个类、41,501 个方法、48,017 个属性。支持类详情查询、方法搜索、名称验证、全文搜索、继承浏览与批量查询。

## 快速开始

```bash
# 1. 查询（首次运行自动构建数据库，约 10s）
python scripts/nxopen_query.py class "NXOpen.Body"
python scripts/nxopen_query.py search "face normal"
python scripts/nxopen_query.py count

# 2. 手动重建数据库（如需刷新）
python scripts/build_index.py

# 3. 压缩 JSON 为 gzip（分发前用）
python scripts/compress.py compress data/nxopen_structure.json
```

## 目录结构

```
nxopen-api-query-skill/
├── README.md               ← 本文件
├── SKILL.md                ← Skill 入口（frontmatter + Agent 使用指令）
├── AGENTS.md               ← 开发维护说明（数据库结构、程序架构、规范）
├── doc/
│   ├── json-structure.md       ← 中间 JSON 结构说明
│   └── database-structure.md   ← SQLite 数据库结构说明
├── data/
│   ├── nxopen_api.db            ← SQLite 数据库（~160MB，首次运行自动生成，不随分发）
│   └── nxopen_structure.json.gz ← 源数据（gzip，~3.2MB，随分发，构建数据库的输入）
└── scripts/
    ├── build_index.py      ← 索引构建脚本（JSON/gz → SQLite + FTS5）
    ├── compress.py         ← JSON 压缩/解压工具（通用）
    ├── domains.py          ← 功能域映射表（12 域 → 99 模块，独立维护）
    └── nxopen_query.py     ← Skill 查询引擎 / 命令行工具（10 个子命令）
```

## 查询命令

所有查询通过 `scripts/nxopen_query.py` 执行：

```bash
python scripts/nxopen_query.py <command> [args] [options]
```

| 命令 | 作用 | 示例 |
|------|------|------|
| `search` | 全文搜索类+方法（trigram 名 + BM25 描述/参数/返回值） | `search "face normal"` |
| `class` | 类详情（doc/继承/方法/属性/嵌套类） | `class "NXOpen.Body"` |
| `method` | 按名搜方法，可按类过滤 | `method "Create" --cls "Body"` |
| `verify` | 验证类名/方法名/属性名 | `verify "NXOpen.Body"` |
| `module` | 列出模块统计 + 顶层类 | `module "CAM"` |
| `inherit` | 继承树（父类+子类） | `inherit "NXOpen.Body"` |
| `suggest` | 模糊推荐相似名称 | `suggest "Body"` |
| `modules` | 列出全部 99 模块 | `modules` |
| `count` | 总体统计 | `count` |
| `batch` | 一次进程跑多个子查询 | `batch -f queries.json` |

通用选项：`--db PATH`（指定数据库）、`--limit N`（默认 30）、`--json`（JSON 输出）。

## 环境要求

⚠️ **硬性要求 SQLite ≥ 3.34.0**（Python 自带的 `sqlite3` 模块）。

原因：使用 FTS5 `trigram` 分词器做类名/方法名子串检索。低于此版本脚本会报错退出。

```bash
# 检查版本
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

若不满足：升级 Python（推荐 conda: `conda install -c conda-forge python=3.10`），或 `pip install pysqlite3-binary`。

## 数据统计

| 指标 | 数量 |
|------|------|
| 模块 | 99 |
| 类（顶层+嵌套） | 23,377 |
| 方法 | 41,501 |
| 属性 | 48,017 |
| 嵌套类 | 21,601 |

## 技术栈

- **查询引擎**：Python 3 + SQLite + FTS5（trigram + unicode61 分词器 + BM25 排序）
- **无第三方依赖**：仅标准库 `sqlite3`/`json`/`os`/`sys`/`re`
- **数据源**：Siemens NX 2212 NXOpen Python API 类型存根（1778 个 `.pyi` 文件）

## 文档

- [SKILL.md](SKILL.md) — Skill 入口（Agent 使用指令、查询命令说明、中文意图分析方法论、交叉验证工作流）
- [AGENTS.md](AGENTS.md) — 开发维护说明（数据库结构、程序架构、FTS5 检索设计、编码规范、已知优化点）
- [doc/json-structure.md](doc/json-structure.md) — 中间 JSON 结构说明
- [doc/database-structure.md](doc/database-structure.md) — SQLite 数据库结构说明
