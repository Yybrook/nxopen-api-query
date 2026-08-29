# NXOpen Python API 全景思维导图

## 本目录定位

本目录 `nxopen-api-map/` 是 **NXOpen Python API 全景思维导图** 项目的工作区，包含：

- 数据解析脚本（`.pyi` 类型存根 → 完整中间 JSON）
- 数据生成脚本（完整中间 JSON → 前端精简 JS 数据）
- 前端页面（D3.js 交互式思维导图，无需后端服务）
- 各阶段生成的数据文件
- 结构说明文档（`doc/` 目录）

源数据（NXOpen `.pyi` 类型存根文件夹）为**只读输入**，不随仓库分发，由用户使用时提供。
`.pyi` 文件来自 **Siemens NX 2212** 版本的 `NXOpen_*.pyd` 二进制模块经反射工具解析生成。

## 目录结构

```
nxopen-api-map/
├── README.md                        ← 项目总览与使用说明（面向使用者）
├── AGENTS.md                        ← 本文件（工作区说明，面向开发/维护）
├── viewer.html                      ← 主页面（HTML 结构）
├── viewer.css                       ← 样式表（从 viewer.html 分离）
├── app.js                           ← 交互逻辑（D3.js v7）
├── doc/                             ← 结构说明文档（详见下方「文档说明」）
│   ├── pyi-structure.md             ← .pyi 类型存根文件结构详解
│   ├── json-structure.md            ← 中间 JSON 结构说明
│   └── js-structure.md              ← 精简 JS 数据结构说明
├── scripts/                         ← 数据管线脚本
│   ├── parse_pyi.py                 ← .pyi 批量解析脚本（AST + 状态机 docstring 解析）
│   ├── gen_js.py                    ← 数据精简 + 功能域分组 + 继承关系解析脚本
│   └── domains.py                   ← 功能域映射表（12 域 → 99 模块，独立维护）
└── data/                            ← 数据产物
    ├── nxopen_data.js               ← 精简 JS 数据（约 24.9 MB，由 gen_js.py 生成）
    └── nxopen_structure.json.gz     ← 压缩中间 JSON（约 3.5 MB，随仓库分发）
```

> 📦 注意：`data/nxopen_structure.json.gz`（压缩中间 JSON，约 3.5 MB）**随仓库分发**，可直接用于 `gen_js.py`。原始 `.json` 文件已被 `.gitignore` 排除，`parse_pyi.py` 解析后自动压缩并删除。如需从 `.pyi` 重新生成，先通过 `make-nxopen-pyi` 项目从 NX 2212 的 `.pyd` 文件反射生成 `.pyi` 存根，再运行 `parse_pyi.py --source`。

## 文档说明（`doc/` 目录）

`doc/` 目录包含三个结构说明文档，分别对应数据管线的三个阶段，供开发/维护参考：

| 文档 | 说明 | 对应阶段 |
|------|------|---------|
| [pyi-structure.md](doc/pyi-structure.md) | `.pyi` 类型存根的目录结构、docstring 格式、枚举/属性/方法格式、已知格式陷阱、行截断副作用 | 输入端（NXOpen `.pyi`） |
| [json-structure.md](doc/json-structure.md) | 中间 JSON 的结构、字段说明、截断规则、`parse_pyi.py` 转换方法 | 中间产物（`nxopen_structure.json`） |
| [js-structure.md](doc/js-structure.md) | 精简 JS 数据的结构、短键名、继承解析、功能域分组、`gen_js.py` 转换方法、字段映射 | 最终产物（`nxopen_data.js`） |

**使用建议**：
- 修改 `parse_pyi.py` 前，先阅读 `pyi-structure.md`（了解 `.pyi` 格式）和 `json-structure.md`（了解输出结构）
- 修改 `gen_js.py` 前，先阅读 `json-structure.md`（了解输入）和 `js-structure.md`（了解输出）
- 调整模块功能域归属时，编辑 `scripts/domains.py`（无需改动其他文件）
- 详细的数据格式说明已移至 `doc/`，本文件仅保留要点索引

## 数据管线

```
NXOpen_*.pyd  ──make-nxopen-pyi──▶  NXOpen/*.pyi  ──scripts/parse_pyi.py──▶  data/nxopen_structure.json.gz  ──scripts/gen_js.py──▶  data/nxopen_data.js
(NX 2212)     (反射生成.pyi)       (1778个)       (--source必填)             (压缩中间JSON,~3.5MB)           (精简+分组+继承)           (精简JS,~24.9MB)
                                                                                                    │
                                                          viewer.html + viewer.css + app.js ◀──────┘
                                                          (D3.js 渲染)
```

### 步骤 0：从 .pyd 生成 .pyi 存根（make-nxopen-pyi 项目，可选）

`.pyi` 存根由 `make-nxopen-pyi` 项目（独立的反射工具）从 NX 2212 的 `NXOpen_*.pyd` 二进制模块生成。
该工具需在 NX 内置 Python 环境中运行，详见 `make-nxopen-pyi` 项目的说明文档。
若已获得 `.pyi` 存根目录，可跳过此步。

### 步骤 1：解析 .pyi 文件（parse_pyi.py）

```bash
cd nxopen-api-map
python scripts/parse_pyi.py --source <path_to_NXOpen_folder> [--output PATH]
```

- **`--source`（必填）**：NXOpen 文件夹的完整路径，由用户提供，不设默认值
- **`--output`（可选）**：输出 JSON 路径，默认写至项目 `data/nxopen_structure.json`，解析后自动压缩为 `.json.gz` 并删除原始 JSON
- **方法**：Python `ast` 模块解析类型存根，状态机逐行解析 docstring
- **提取字段**：描述、签名、参数、返回值、返回值元组组成、版本信息、许可证要求
- **关键函数**：`parse_class()` / `parse_method_doc()` / `_is_enum()` / `_clean_rst()`
- **格式细节**：详见 [doc/pyi-structure.md](doc/pyi-structure.md)

### 步骤 2：精简数据 + 功能域分组（gen_js.py）

```bash
python scripts/gen_js.py
```

- **输入**：`data/nxopen_structure.json.gz`（压缩文件，路径基于项目根目录定位）
- **输出**：`data/nxopen_data.js`（约 24.9 MB）
- **功能域映射表**：`scripts/domains.py`（12 域 → 99 模块，独立维护）
- **关键函数**：`flatten_classes()` / `resolve_inheritance()`
- **结构细节**：详见 [doc/json-structure.md](doc/json-structure.md) 和 [doc/js-structure.md](doc/js-structure.md)

### 步骤 3：打开网页

直接用浏览器打开根目录 `viewer.html` 即可，无需后端服务。

## 数据统计

| 指标 | 数量 |
|------|------|
| 类型存根文件 | 1,778 |
| 顶层模块 | 99 |
| 功能域 | 12 |
| 类（含嵌套） | 23,377 |
| 方法 | 41,501 |
| 属性 | 48,017 |
| 有父类的类 | 7,418 |
| 有子类的类 | 583 |
| 有许可证的方法/属性 | 27,371（30.6%） |
| 外部基类（不可跳转） | 33 |

## 关键设计决策

- **`_is_enum` 启发式判断**：忽略 `ValueOf` 内置方法 + `Expr`(docstring) 不计入 other 节点 + 赋值 > 3 且 other ≤ 2 判为枚举（修复后 194 个枚举全部正确识别）
- **签名提取优先匹配 `Signature` 标记**：避免 `` ``---`` `` 分隔线被误取为签名（修复后 75% 属性签名恢复）
- **数据精简策略**：12 功能域分组 + 短键名 + 描述截断 + license 字段 → 24.9MB JS 数据文件
- **状态机 docstring 解析**：`parse_method_doc` 逐行跟踪状态，支持多行续行、紧凑写法
- **继承解析时机**：在所有模块合并完成后第二阶段解析（`resolve_inheritance()`）
- **路径参数化**：`parse_pyi.py` 的 `--source` 为必填参数；两个脚本的输入/输出路径均基于项目根目录定位

## 网页功能要点

- **思维导图（左侧）**：D3.js 水平树状布局，功能域 → 模块 → 类，支持缩放/平移/适应屏幕
- **全局搜索（顶部）**：类/方法/属性三标签多选过滤，按匹配度排序，200ms 防抖
- **面板内搜索**：模块/类详情各有搜索框 + 类/方法/属性筛选标签，上限 500 条
- **详情面板（右侧）**：方法卡片含签名、参数表（类型链接）、返回值、返回值组成、版本（🏷️）、许可证（🔑）
- **面板调节**：可拖拽分割线，调节两侧宽度（15%~85%）

## 注意事项

- NX 源数据目录为只读输入，**不要修改**其中的内容
- 重新生成数据需按顺序执行：先用 `make-nxopen-pyi` 项目从 NX 2212 的 `.pyd` 生成 `.pyi` 存根，再 `parse_pyi.py`（需 `--source`）生成 `data/nxopen_structure.json.gz`（自动压缩），最后 `gen_js.py` 生成 `data/nxopen_data.js`
- `nxopen_data.js`（24.9 MB）体积较大，浏览器加载需耐心等待；`nxopen_structure.json.gz`（11 MB）为压缩中间文件
- 嵌套类/子类卡片最多显示 300 条防卡顿；面板搜索可突破该上限至 500 条
- 类卡片右侧数字：有嵌套类时显示嵌套类数量，无嵌套类时显示方法/属性数量
- NXOpen 的 `.pyi` 存根中嵌套类与方法/属性互斥——有嵌套类的父类是命名空间容器，不含方法/属性
- **枚举成员未提取**：`parse_pyi.py` 的 `parse_class()` 只提取 `FunctionDef`（方法）和 `ClassDef`（嵌套类），不提取 `Assign`/`AnnAssign`（赋值语句）。因此枚举的成员名（如 `R18`、`V2022`）在 JSON 中丢失，只保留了枚举的"壳"（类名、描述、`ValueOf` 方法）。如需补充，需在 `parse_class()` 中为枚举类额外收集 `Assign`/`AnnAssign` 的目标名作为成员列表，并联动修改 `gen_js.py`、`app.js`、文档
- **csv-table 被截断**：枚举类的 docstring 中通常含 `.. csv-table::` 成员描述表（如 `"R18", " - "`），但 `clean_doc()` 在遇到 `.. csv-table` 时停止收集描述，导致成员表被丢弃。成员描述信息量较低（87% 为 `" - "`），影响有限
