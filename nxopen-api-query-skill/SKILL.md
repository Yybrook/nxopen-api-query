---
name: nxopen-api-query-skill
description: Siemens NX（UG）二次开发中的 NXOpen Python API 查询工具。在进行 NX（UG）二次开发时，开发者需要频繁查阅 NXOpen Python API 的类、方法、属性、继承关系、参数和返回值。本 skill 将全部 1778 个 .pyi 类型存根构建为 SQLite + FTS5 全文索引，提供毫秒级查询。当用户需要：查询某个类/方法/属性的作用和用法、验证 API 名称是否正确、搜索相关 API、查看继承关系、列出模块内容、或在编写 NX 自动化代码时不确定某个 API 的签名和参数时，都应使用此 skill。Agent 遇到中文意图时先翻译为英文关键词再检索。支持 99 个模块、23,377 个类、41,501 个方法、48,017 个属性的毫秒级查询。即使用户没有明确提到"skill"或"查询"，只要涉及 NXOpen Python API 的类/方法/属性问题、或在进行 NX（UG）二次开发时需要查阅 API，都应触发。
---

# NXOpen Python API 查询工具

在进行 Siemens NX（UG）二次开发时，开发者需要频繁查阅 NXOpen Python API 来编写自动化代码——查找类的方法签名、参数类型、返回值、继承关系，或验证 API 名称是否正确。本 skill 将全部 1778 个 `.pyi` 类型存根构建为 SQLite + FTS5 全文索引，提供毫秒级查询，让 Agent 在辅助 NX 二次开发时能快速、准确地获取 API 信息，而非凭记忆猜测。
覆盖全部 99 个模块、23,377 个类、41,501 个方法、48,017 个属性。所有查询通过 `scripts/nxopen_query.py` 执行，支持类/方法/属性查询、名称验证、全文搜索、继承浏览与批量查询。

## 数据库

```
data/nxopen_api.db          — ~160MB SQLite 数据库（含 FTS5 trigram + BM25 全文索引，首次运行自动生成）
data/nxopen_structure.json.gz  — 源数据（gzip 压缩，~3.2MB，随 skill 分发，构建数据库的输入）
```

**首次运行自动构建**：skill 包初始不含 `data/nxopen_api.db`（体积大，不利分发）。查询脚本首次执行时自动检测，若无 db 则从 `data/nxopen_structure.json.gz` 解压并自动构建（约 10s，一次性）。后续查询直接使用已构建的 db。

如需手动重建：
```bash
python scripts/build_index.py                          # 默认从 data/nxopen_structure.json 或 .gz 构建
python scripts/build_index.py --source <其他路径>        # 指定其他数据源
python scripts/build_index.py --compress                # 压缩 data/nxopen_structure.json 为 .gz
python scripts/compress.py compress data/nxopen_structure.json  # 独立压缩脚本（同上）
```

### 环境要求

⚠️ **硬性要求 SQLite ≥ 3.34.0**（Python 自带的 `sqlite3` 模块）。

原因：本工具使用 FTS5 `trigram` 分词器（SQLite 3.34.0 引入）做类名/方法名子串检索（如搜 `Body` 命中 `BodyDes`）。低于此版本，脚本会在启动时检测并直接退出，给出明确报错。

检查当前环境版本：
```bash
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

若版本不满足，任选其一解决：
- **升级 Python**：较新版本通常自带满足要求的 SQLite（推荐 conda: `conda install -c conda-forge python=3.10`）。
- **安装 pysqlite3-binary**：`pip install pysqlite3-binary`，并在两个脚本顶部插入 `__import__('pysqlite3'); sys.modules['sqlite3']=sys.modules.pop('pysqlite3')` 替换标准库。

## 查询命令

所有查询通过 `scripts/nxopen_query.py` 执行：

```bash
python scripts/nxopen_query.py <command> [args] [options]
```

### 1. 查询类/方法/属性的作用和用法

**查类详情**（含方法列表、参数、返回值、继承关系、嵌套类）：
```bash
python scripts/nxopen_query.py class "NXOpen.Body"
python scripts/nxopen_query.py class "Body"           # 支持短名，自动模糊匹配
```

**查方法详情**（按名称搜索，可按类过滤）：
```bash
python scripts/nxopen_query.py method "Create"                    # 全局搜索名为 Create 的方法
python scripts/nxopen_query.py method "Create" --cls "Body"        # 只搜 Body 相关类中的 Create
```

输出包含：方法签名、参数表（名称 + 类型 + 描述）、返回值类型与描述、返回值元组组成、版本信息。

### 2. 验证类名/方法名/属性名是否正确

```bash
python scripts/nxopen_query.py verify "NXOpen.Body"       # 验证类名
python scripts/nxopen_query.py verify "Create"           # 验证方法名（列出所有匹配处）
python scripts/nxopen_query.py verify "IsSolidBody"      # 验证属性名
```

输出：找到时显示 ✅ 并给出位置和描述；未找到时显示 ❌ 并自动推荐相似名称。

### 3. 全文搜索相关 API

```bash
python scripts/nxopen_query.py search "create body"      # 搜索类名+方法名+方法描述
python scripts/nxopen_query.py search "extrude feature"  # 按功能描述搜索
```

搜索范围：类名（trigram 子串/camelCase 命中）、类描述、方法名、方法描述、方法参数、返回值、返回类型（BM25 相关度排序），返回匹配的类和方法列表。多词为任意位置 AND 匹配。

### 4. 查看继承关系

```bash
python scripts/nxopen_query.py inherit "NXOpen.Body"     # 显示父类和子类
```

### 5. 列出模块内容

```bash
python scripts/nxopen_query.py module "CAM"              # 显示模块统计 + 顶层类列表
python scripts/nxopen_query.py module "NXOpen" --limit 50
```

输出包含：功能域、类/方法/属性统计、每个顶层类的嵌套类数/方法数/属性数。

### 6. 相似名称推荐

```bash
python scripts/nxopen_query.py suggest "Body"            # 模糊搜索相似类名和方法名
```

### 7. 统计信息

```bash
python scripts/nxopen_query.py count                     # 总体统计
python scripts/nxopen_query.py modules                    # 列出所有模块
```

### 8. 批量查询（一次进程跑多个子查询，省启动开销）

```bash
python scripts/nxopen_query.py batch -f batch.json        # 从 JSON 文件读取多个子查询
python scripts/nxopen_query.py batch '[{"cmd":"search","args":["extrude"],"limit":5},
                               {"cmd":"class","args":["NXOpen.Body"]},
                               {"cmd":"method","args":["Create"],"cls":"Body","limit":5}]'
```

每个元素：`{"name":"可选标签","cmd":"子命令","args":[...],"limit":N,"cls":"类过滤"}`
输出：聚合 JSON 数组，每个元素 `{"name":..., "result":...}`。
> Agent 多轮场景下用 `batch` 一次性跑 search+class+method+verify，比逐个调用快 ~2x（消除每进程 ~200ms 启动税）。

## 通用选项

- `--db PATH` — 指定数据库路径（默认：`data/nxopen_api.db`）
- `--limit N` — 最大返回条数（默认：30）
- `--json` — 输出 JSON 格式（用于程序化处理）

## 使用指南

### Agent 使用流程

1. **用户问"NXOpen.Body 怎么用"** → 运行 `class "NXOpen.Body"` 获取类详情和方法列表
2. **用户问"Body 有哪些方法"** → 运行 `class "NXOpen.Body"` 查看方法列表
3. **用户问"Create 方法怎么用"** → 运行 `method "Create"` 找到方法，再 `class` 查看完整签名
4. **用户问"NXOpen.Body.Create 对不对"** → 运行 `verify "Create"` 验证名称
5. **用户问"怎么创建 Body"** → 运行 `search "create body"` 搜索相关 API（多词任意位置匹配）
6. **需一次查多个东西** → 运行 `batch -f x.json` 一次进程跑多个子查询，省启动开销
7. **用户问"Body 继承了什么"** → 运行 `inherit "NXOpen.Body"` 查看继承树
8. **用户问"CAM 模块有什么"** → 运行 `module "CAM"` 列出模块内容
9. **用户拼写不确定** → 运行 `suggest "Body"` 获取相似名称推荐

### 中文意图分析与检索词选择方法论

`search` 命令使用英文关键词检索（API 名称/描述/返回值均为英文）。当用户用中文描述意图时，**不要做机械逐词翻译**，而应按以下方法论选择检索词：

**第一步：理解意图核心**——用户到底想做什么操作？作用于什么对象？要得到什么结果？
- 例："如何测量曲面的曲率半径" → 操作=测量，对象=曲面，结果=曲率半径

**第二步：基于 NXOpen 命名习惯推导英文关键词**——NXOpen API 遵循 camelCase 命名，常见模式：
- 获取属性类：`Get` + 对象 + 属性（如 `GetFaceProperties`、`GetEdges`）
- 查询数据类：`Ask` + 对象 + 数据（如 `AskFaceProps`、`AskCurveProps`，UF 模块常见）
- 创建构建器类：`Create` + 对象 + `Builder`（如 `CreateMeasureFaceBuilder`）
- 测量类：`Measure` / `MeasureManager` + 对象 + 属性
- 属性名常含完整描述：`minRadiusOfCurvature`、`InvOfMaxRadiusOfCurvature`、`FaceNormal`

**第三步：选择多个可能的检索词组合**——不要只搜一个固定翻译，尝试多种组合：
- "面的法向" → 可搜 `face normal`、`GetFaceNormal`、`AskFaceProps`、`FaceNormal`、`unitNorm`
- "曲面曲率半径" → 可搜 `face curvature radius`、`minRadiusOfCurvature`、`CalculatePointCurvature`
- "面的面积" → 可搜 `face area measure`、`MeasureFaces`、`GetFaceProperties`
- 多词空格分隔，脚本自动做 AND 跨字段匹配（类名/方法名/描述/参数/返回值/返回类型）

> 以上示例仅为启发，不是穷举映射表。Agent 应基于意图分析和命名习惯灵活选择检索词，必要时换词重搜。

### 交叉验证工作流（推荐）

为提高检索全面性和准确性，推荐以下工作流：

1. **Agent 先分析**：基于自身 NXOpen 知识，预判可能的 API（如"面法向"可能涉及 `GetFaceNormal`/`FaceNormal` 属性/UF 的 `AskFaceProps`）
2. **skill 检索**：用分析得出的英文关键词调 `search`，拿回候选 API 列表
3. **交叉验证**：对比 Agent 预判与 search 结果——
   - search 命中了 Agent 预判的 → 确认可靠
   - search 命中了 Agent 没想到的 → 补充（如 UF 底层函数 `AskFaceProps`/`Evalsf.Evaluate`）
   - Agent 预判的没在 search 结果里 → 可能名称记错，用 `suggest` 或 `verify` 核实，或换词重搜
4. **深入确认**：对关键候选用 `class`/`method` 查看完整签名和返回值，确认功能匹配

### 网络资源补充（可选）

skill 数据库包含全部 API 的签名/参数/返回值/继承，但**不含实际用法示例**，且 UF 模块函数的描述常为占位符（`Refer to UF_xxx`）。当 skill 信息不足以回答用户时，可使用网络资源补充：

- **查询 NXOpen 官方文档**：用 `fetch_web_content` 检索 NXOpen Python API Reference，补充 API 用法说明和代码示例
- **查询 UF 函数语义**：UF 函数描述为占位符时，可搜 `UF_MODL_ask_face_props` 等 C 函数名，查找官方文档的参数说明
- **交叉验证**：网络信息需与 skill 数据库的签名/参数交叉验证，确认一致性后再采用

> 网络资源为补充层，非必需。skill 离线检索应始终作为首要信息来源（权威 API 签名）。网络信息可能过时或有误，需标注来源并与 skill 数据比对。

### 命名规则

- 类全名格式：`模块名.类名`，如 `NXOpen.Body`、`CAE.CAE.Frf5`、`UF.UF.Curve`
- 嵌套类全名：`模块名.外层类.嵌套类`，如 `UF.UF.Curve.CreateCurveOptions`
- 查询时可使用短名（如 `Body`），脚本会自动模糊匹配
- 方法全名：`类全名.方法名`，如 `NXOpen.Body.GetEdges`

### 输出格式

- 默认输出：人类可读的格式化文本（中文标注 + 英文 API 名）
- `--json` 输出：JSON 格式，适合程序化处理或传给其他工具
- 方法详情包含：名称、签名、参数表（名称/类型/描述）、返回值（描述/类型/元组组成）、版本

## 数据来源

- 源数据：**Siemens NX 2212** 版本的 NXOpen Python API 类型存根文件（1778 个 `.pyi` 文件，由 NX 2212 的 `NXOpen_*.pyd` 二进制模块经反射工具解析生成）
- 数据处理：上游 `nxopen-api-map` 项目的 `parse_pyi.py`（AST 解析 + 状态机 docstring 解析）→ `nxopen_structure.json`
- 索引构建：`scripts/build_index.py`（默认从 `data/nxopen_structure.json` 或 `.json.gz` 构建，合并 clss/ 到顶层模块 + SQLite + FTS5 全文索引）
- 数据更新：重新运行 `scripts/build_index.py` 即可刷新数据库
- `data/nxopen_structure.json.gz` 随 skill 分发（gzip 压缩，~3.2MB），`--source` 可选（默认使用该文件）。

> 数据库结构详见 `doc/database-structure.md`，中间 JSON 结构详见 `doc/json-structure.md`。程序架构、开发规范等详细说明见 `AGENTS.md`。
