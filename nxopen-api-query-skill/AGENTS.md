# NXOpen Python API 查询工具

## 本目录定位

本目录 `nxopen-api-query-skill/` 是 **NXOpen Python API 查询工具** 的 skill 工作区，包含：

- `SKILL.md` — skill 入口（YAML frontmatter + Agent 使用指令）
- `AGENTS.md` — 本文件（面向开发/维护的数据库结构、程序结构、规范说明）
- `doc/` — 结构说明文档（json-structure.md / database-structure.md）
- `data/nxopen_api.db` — SQLite 数据库（约 160MB，首次运行自动生成，不随 skill 分发）
- `data/nxopen_structure.json.gz` — 源数据（gzip 压缩，~3.2MB，随 skill 分发，构建数据库的输入）
- `scripts/` — 数据管线脚本（build_index.py / compress.py / domains.py / nxopen_query.py）

源数据 `data/nxopen_structure.json.gz` 随 skill 分发（gzip 压缩，~3.2MB；由上游项目 `nxopen-api-map` 产出）。

> **API 来源**：基于 **Siemens NX 2212** 版本的 NXOpen Python API。`.pyi` 类型存根由 NX 2212 的 `NXOpen_*.pyd` 二进制模块经反射工具解析生成，由上游 `nxopen-api-map` 项目的 `parse_pyi.py` 解析为 `nxopen_structure.json.gz`。

## 目录结构

```
nxopen-api-query-skill/
├── .gitignore              ← 忽略 __pycache__/.idea/data/nxopen_api.db 等
├── SKILL.md                ← skill 入口（frontmatter + 使用说明，面向 Agent）
├── AGENTS.md               ← 本文件（开发/维护说明）
├── README.md               ← 项目说明（面向使用者）
├── doc/
│   ├── json-structure.md       ← 中间 JSON 结构说明（输入端）
│   └── database-structure.md   ← SQLite 数据库结构说明（产物）
├── data/
│   ├── nxopen_api.db            ← SQLite 数据库（~160MB，首次运行自动生成，不随 skill 分发 / .gitignore）
│   └── nxopen_structure.json.gz  ← 源数据（gzip 压缩，~3.2MB，随 skill 分发，构建数据库的输入）
└── scripts/
    ├── build_index.py      ← 索引构建脚本（JSON/gz → SQLite + FTS5）
    ├── compress.py         ← JSON 压缩/解压工具（通用，无硬编码路径）
    ├── domains.py          ← 功能域映射表（12 域 → 99 模块，独立维护）
    └── nxopen_query.py     ← 查询命令行工具（10 个子命令）
```

> 标准 agent skill 结构：`SKILL.md` 为根入口，`scripts/` 放可执行代码与运行时配置。脚本路径解析基于 skill 根目录（`scripts/` 的父目录）。

### 文档说明（`doc/` 目录）

| 文档 | 说明 | 对应阶段 |
|------|------|---------|
| [json-structure.md](doc/json-structure.md) | 中间 JSON 结构、字段说明、截断规则、数据统计 | 输入端（`nxopen_structure.json`） |
| [database-structure.md](doc/database-structure.md) | SQLite 数据库结构、主表、FTS5 索引表、B-tree 索引、构建流程 | 产物（`nxopen_api.db`） |

## 数据管线

```
NXOpen_*.pyd  ──make-nxopen-pyi──▶  NXOpen/*.pyi  ──parse_pyi.py（nxopen-api-map）──▶  nxopen_structure.json.gz  ──build_index.py──▶  nxopen_api.db
 (NX 2212)    (反射生成.pyi)       (1778个)                                    (压缩中间JSON,~3.2MB)       (本 skill)         (~160MB SQLite+FTS5)
                                                                                                                          │
                                                                                                                          ▼
                                                                                                                 scripts/nxopen_query.py <command>
                                                                                                                 （Agent 查询）
```

- **上游**（不在本 skill）：`nxopen-api-map/scripts/parse_pyi.py` 解析 1778 个 `.pyi` 类型存根 → `data/nxopen_structure.json.gz`。
- **构建**（本 skill `scripts/build_index.py`）：读 JSON（通过 `compress.load_json_from_gz`）→ 合并 `clss/` 到顶层模块 → 写 SQLite → 建 B-tree 索引 + FTS5 虚拟表。
- **查询**（本 skill `scripts/nxopen_query.py`）：基于 SQLite + FTS5 提供 10 个子命令。

## 数据库结构

> 本节为概要，完整结构说明详见 [doc/database-structure.md](doc/database-structure.md)。中间 JSON 结构详见 [doc/json-structure.md](doc/json-structure.md)。

### 主表

**`modules`（模块表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| name | TEXT | 模块名，如 NXOpen、CAM、Features |
| doc | TEXT | 模块文档 |
| domain | TEXT | 功能域（12 大分类之一） |

**`classes`（类表，含嵌套类）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| module_id | INTEGER FK→modules | 所属模块 |
| full_name | TEXT | 全名，如 `NXOpen.Body`、`UF.UF.Curve.CreateCurveOptions` |
| short_name | TEXT | 短名，如 `Body` |
| doc | TEXT | 类文档 |
| bases | TEXT | JSON 数组，父类列表（用于继承查询） |
| parent_class_id | INTEGER | 嵌套类的父类 id（顶层类为 NULL） |
| is_nested | INTEGER | 是否嵌套类（0/1） |

**`methods`（方法 + 属性共用表，用 `is_property` 区分）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| class_id | INTEGER FK→classes | 所属类 |
| name | TEXT | 方法/属性名 |
| desc | TEXT | 描述 |
| sig | TEXT | 签名，如 `GetEdges()` |
| params | TEXT | JSON，参数表（name/type/desc） |
| returns | TEXT | 返回值描述 |
| rtype | TEXT | 返回值类型 |
| rc | TEXT | return_components，返回值元组组成（JSON） |
| version | TEXT | 引入版本，如 NX3.0.0 |
| is_property | INTEGER | 0=方法，1=属性 |

### FTS5 全文索引表（5 张虚拟表）

| 表名 | 索引列 | 分词器 | 用途 |
|------|--------|--------|------|
| `classes_name_fts` | full_name, short_name | **trigram** | 类名子串/camelCase 命中（搜 `Body` 命中 `BodyDes`） |
| `methods_name_fts` | name | **trigram** | 方法名子串/camelCase 命中 |
| `classes_fts` | full_name, doc | unicode61 | 类文档词级全文 + BM25 排序 |
| `methods_fts` | name, desc, params, returns, rtype, rc | unicode61 | 方法描述/参数/返回值/返回类型/rc 全文 + BM25 |
| `methods_body_fts` | name, returns, rtype, params, rc_text | **trigram** | 方法标识符类字段子串检索（让 unitNorm/srf_unormal 等 camelCase 被 normal 命中） |

> trigram 分词器需 SQLite ≥ 3.34.0；unicode61 自 SQLite 3.9.0 可用。两脚本启动时硬性检测版本。

### B-tree 索引

`idx_classes_full` / `idx_classes_short` / `idx_classes_mod` / `idx_classes_parent`、`idx_methods_class` / `idx_methods_name` / `idx_methods_prop`、`idx_mod_domain`。

### 数据规模

| 指标 | 数量 |
|------|------|
| 模块 | 99 |
| 类（顶层+嵌套） | 23,377 |
| 方法 | 41,501 |
| 属性 | 48,017 |
| 嵌套类 | 21,601 |

## 程序结构

### `scripts/build_index.py`（索引构建）

**用法**：
```bash
python scripts/build_index.py --source <path_to_nxopen_structure.json> [--output PATH]
```

- `--source`（可选）：`nxopen_structure.json` 或 `.json.gz` 路径，默认 skill 根目录 `data/` 下。
- `--output`（可选）：输出数据库路径，默认 skill 根目录 `data/nxopen_api.db`。
- `--compress`：压缩 `data/nxopen_structure.json` 为 `.gz`（调用 `compress.compress_file`）。
- **路径解析**：`SCRIPT_DIR` = scripts/，`_ROOT_DIR` = 其父目录，数据库默认输出到 `_ROOT_DIR/data/nxopen_api.db`。
- **依赖**：从 `scripts/domains.py` 导入 `DOMAINS`（功能域映射表），从 `scripts/compress.py` 导入 `compress_file` / `load_json_from_gz`（压缩/解压工具）。

**关键逻辑**：
- `flatten_classes(classes, prefix, mod_id, conn, parent_id)` — 递归插入类及其方法/属性/嵌套类。
- `clss/` 模块合并：看类 `bases` 形如 `NXOpen.X.Y`（≥3 段且首段 NXOpen）则归入模块 X，否则归入 NXOpen。与 `nxopen-api-map/scripts/gen_js.py` 保持一致。
- 12 大功能域分组（`DOMAINS` 字典），定义在 `scripts/domains.py`（独立维护），与上游 `nxopen-api-map/scripts/domains.py` 完全一致。
- 构建顺序：建主表 → 插数据 → 建 B-tree 索引 → 建 FTS5 虚拟表（trigram name + unicode61 desc）。

### `scripts/nxopen_query.py`（查询工具）

**用法**：
```bash
python scripts/nxopen_query.py <command> [args] [--db PATH] [--limit N] [--json]
```

- **路径解析**：`DEFAULT_DB` = `data/nxopen_api.db`；`DEFAULT_SOURCE` = `data/nxopen_structure.json`。

**子命令（10 个）**：

| 命令                          | 作用 | name 检索方式 |
|-------------------------------|------|---------------|
| `search <text>`               | 全文搜索类+方法 | trigram 子串 + BM25 desc/params/returns |
| `class <full_name>`           | 类详情（doc/继承/方法/属性/嵌套） | 精确 → 短名 → LIKE 三级回退 |
| `method <name> [--cls C]`     | 按名搜方法，可按类过滤 | trigram 子串 + bm25 |
| `verify <name>`               | 验证类/方法/属性名，未找到推荐相似名 | 精确匹配，未找到调 suggest |
| `module <name>`               | 列出模块统计 + 顶层类 | — |
| `inherit <class>`             | 继承树（父类+子类） | — |
| `suggest <name>`              | 模糊推荐相似类名/方法名 | trigram 子串 |
| `modules`                     | 列出全部 99 模块 | — |
| `count`                       | 总体统计 | — |
| `batch '<json>' or -f f.json` | 一次进程跑多个子查询，返回聚合 JSON | — |

**关键函数**：
- `_fts_escape(term)` — FTS5 查询词转义（双引号包裹防注入）。
- `_build_fts_match(query, mode)` — 构建 unicode61 FTS5 MATCH 串（多词 AND/OR）。
- `_build_trigram_match(query)` — 构建 trigram FTS5 MATCH 串（≥3 字符 token，子串匹配）。
- `_run_sub(conn, spec)` — batch 内执行单个子查询，通过 stdout 重定向 + JSON 解析捕获结果返回 dict。
- `cmd_search` — name 走 trigram AND，body 走 trigram AND（含 rc/结构体属性回灌），desc 走 unicode61 BM25，三路合并去重 + 综合排序。

## 12 个功能域

| 功能域 | 模块数（部分） |
|--------|------|
| 核心基础 | NXOpen, Layer, Display, Select, Fields, Gateway, Options, Preferences, Appearance |
| 建模与特征 | Features, GeometricUtilities, Facet, Implicit, ModlDirect, ModlUtils, SheetMetal, BodyDes, StructureDesign, RegionRecognition, ShapeSearch, Join, Weld |
| 制图与标注 | Drawings, Drafting, Annotations, MBD, TDP, OpenXml, Layout2d |
| 装配与产品数据 | Assemblies, PDM, Positioning, Placement, DMU, CollaborationApplication, Issue, Validate |
| 仿真分析 | CAE, SIM, DesignSimulation, CADCAEPrep, GeometricAnalysis, PressLineSimulation, PhysMat |
| 制造加工 | CAM, Mfg, MfgModel, Tooling, Die |
| 运动与机构 | Motion, Mechatronics, AME |
| 电气与管路布线 | Routing, ElectricalRouting, MechanicalRouting, CableRouter, RoutingCommon, Formboard, Schematic |
| 模具与复合材料 | MoldCooling, Falcon, Composites, Fabric, Coatings |
| 编程与定制 | UF, BlockStyler, UIStyler, AutomatedTesting, AutomatedTestingCase, UserDefinedObjects, UserDefinedTemplate, MenuBar, PartFamily |
| 报告与可视化 | Report, VisualReporting, MendixReporting, Markup |
| 行业专用 | ShipDesign, StageModel, StageModelTemplate, AnimationDesigner, LineDesigner, ToolDesigner, PID, PcbExchange, Diagramming, Safety, ContactlessInspection, DSE, DSEDesignWorkflow, DSEPlatform, Optimization, PLAS, MPA, CLDCommon, CLDKin, Newapp, Rule, AECDesign |

## 注意事项

### 环境兼容性
- **硬性要求 SQLite ≥ 3.34.0**（trigram 分词器引入版本）。两脚本 import 期检测，不满足直接退出并报错。
- 检查：`python -c "import sqlite3; print(sqlite3.sqlite_version)"`
- 解决：升级 Python（conda: `conda install -c conda-forge python=3.10`），或 `pip install pysqlite3-binary` 替换标准库。

### 数据源
- `data/nxopen_structure.json.gz` 随 skill 分发（gzip 压缩，~3.2MB；由上游 `nxopen-api-map` 项目产出，基于 **Siemens NX 2212** 版本）。
- 重新构建数据库：`python scripts/build_index.py`（默认从 `data/nxopen_structure.json` 或 `.json.gz` 构建），约 10s，库约 160MB。
- 压缩源数据：`python scripts/compress.py compress data/nxopen_structure.json`（将 .json 压缩为 .gz，40MB→3.2MB）或 `python scripts/build_index.py --compress`。

### 路径约定
- 脚本路径解析基于 **skill 根目录**（`scripts/` 的父目录），而非脚本自身目录：
  - 数据库 `data/nxopen_api.db` 首次运行时自动从 `data/nxopen_structure.json` 或 `.json.gz` 构建（skill 包初始不含 db）。
- 这样无论从哪个工作目录调用脚本，路径都正确。

### FTS5 检索设计
- **name 字段用 trigram**：支持 camelCase 子串命中（搜 `Body` 命中 `BodyDes`），避免 unicode61 不拆 camelCase 的回归。
- **doc/desc/params/returns 用 unicode61**：英文散文词级分词 + BM25 相关度排序。
- **多词查询**：FTS5 MATCH 为任意位置 AND（非连续子串），召回率高于 LIKE。
- trigram 对 <3 字符 token 无 n-gram，`_build_trigram_match` 自动跳过过短 token。
- FTS5 查询词经 `_fts_escape` 双引号转义，防特殊字符（`* ( ) : -` 等）被当作语法。
- `methods_body_fts` 是 contentless FTS5 表（未指定 `content=`），不能增量更新，只能全量重建。`rc_text` 列由 Python 函数 `_rc_text`（注册为 SQLite function）从 rc JSON 解析为纯文本。
- BM25 列权重固定为 `(1.0, 1.0, 1.5, 2.0, 1.5, 1.5)`（name/desc/params/returns/rtype/rc），returns/rc 加权较高以突出返回值/结构体属性命中。

### 性能
- SQL 层：FTS5 较 LIKE 提速约 10x（类）/47x（方法）。
- 端到端瓶颈是进程启动开销（~209ms/次），`batch` 命令一次进程跑多个子查询可消除重复启动税（4 查询 815ms vs 3 单调用 1566ms）。

### 已知优化点（暂未实施）
- **O1**：`cmd_class` 子类查询用 `LIKE '%full_name%'` 搜 bases JSON 字符串，全表扫描 classes。可建 `class_bases` 关联表用 JOIN 替代。低频命令，收益有限。
- **O2**：`cmd_module` 对每个顶层类做 N+1 查询（sub_count/mc/pc）。可用 GROUP BY 批量查。低频命令，收益有限。
- **O3**：`_backfill_struct_props` 对 26978 方法遍历解析 rtype 正则 + 查 name_map。已批量优化到 10s。如数据增长可预建 `rtype → struct_full_name` 映射表。
- **R2**：各 cmd 函数（cmd_search/cmd_class/cmd_method 等）混合了"计算逻辑"和"打印格式化"，batch 命令通过 stdout 重定向 + JSON 解析间接调用。可拆分为"计算层（返回 dict）+ 打印层（格式化输出）"，batch 直接调计算层，消除 stdout 解析 hack。纯代码质量重构，无功能收益，回归风险较高，暂未实施。

## 检索策略与使用方式

### 中文意图处理
- `search` 仅支持英文关键词（API 名称/描述/返回值均为英文）。Agent 遇到中文意图时应分析意图核心，基于 NXOpen 命名习惯（`Get`/`Ask`/`Create`/`Measure` + 对象 + 属性）推导多个英文检索词，而非机械逐词翻译。
- SKILL.md 的"中文意图分析与检索词选择方法论"段落提供命名模式和启发示例，引导 Agent 灵活选词。

### 交叉验证
- 推荐工作流：Agent 先基于自身 NX 知识预判 API → 用 search 检索候选 → 对比预判与检索结果（补充/确认/纠错）→ class/method 深入确认。
- 这能弥补 search 排序不理想时的人工筛选，也发现 Agent 可能遗漏的 UF 底层函数。

### 网络资源补充
- skill 数据库含全部 API 签名/参数/返回值，但不含用法示例；UF 函数描述常为占位符。
- 信息不足时，Agent 可用 `fetch_web_content` 查 NXOpen 官方文档/UF C 函数文档，补充用法和语义。
- 网络信息需与 skill 数据交叉验证后再采用。skill 离线检索始终为首要权威来源。

## 编码规范

- Python 3，无第三方依赖（仅标准库 `sqlite3`/`json`/`os`/`sys`/`re`）。
- Windows 下强制 UTF-8 输出（`sys.stdout.reconfigure`），避免中文乱码。
- 输出双模式：人类可读文本（默认）+ JSON（`--json`，程序化处理）。
- 方法/属性共用 `methods` 表，用 `is_property` 区分。
- 类全名遵循 NXOpen 约定（`模块名.类名`），嵌套类为 `模块名.外层类.嵌套类`。

## 数据来源与上游格式

> 中间 JSON 结构详见 [doc/json-structure.md](doc/json-structure.md)，`.pyi` 格式详见上游 `nxopen-api-map/doc/pyi-structure.md`。

- 源数据：**Siemens NX 2212** 版本的 NXOpen Python API 类型存根（1778 个 `.pyi` 文件，约 62MB）。
- 上游 `parse_pyi.py`（`nxopen-api-map` 项目）用 `ast` 模块解析，状态机逐行解析 docstring（`### nxoMethodDescriptorType`、`Signature:`、`:param:`、`:type:`、`:returns:`、`:rtype:`、`.. versionadded::`），含 RST 标记清理。
- 中间 JSON 每个模块含 name/doc/classes/enums/functions，类含 name/doc/bases/methods/properties/nested_classes/nested_enums，方法/属性含 name/desc/sig/params/returns/rtype/return_components/version/**license**。
- `license` 字段存在于中间 JSON 中（约 30% 非空），但当前数据库未存储该字段（不影响搜索结果）。如需后续增加，在 `methods` 表添加 `license TEXT` 列并在 `build_index.py` 的 INSERT 语句中补充即可。
