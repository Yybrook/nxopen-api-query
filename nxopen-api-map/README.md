# NXOpen Python API 全景思维导图

一个将 **Siemens NXOpen Python API** 类型存根可视化为交互式思维导图的静态网页项目。

> **API 来源**：本项目基于 **Siemens NX 2212** 版本的 NXOpen Python API。
> `.pyi` 类型存根由 NX 2212 的 `NXOpen_*.pyd` 二进制模块经反射工具解析生成，
> 共约 1778 个 `.pyi` 文件，覆盖 99 个顶层模块。

从全部 NXOpen 类型存根中提取模块、类、方法、属性及其文档和继承关系，按 12 个功能域分组呈现，
支持全局与面板内搜索、类型跳转、继承关系浏览。**纯静态页面，无需后端与构建工具，浏览器直接打开即可使用。**

## 功能特性

- 🗺 **三层思维导图**：功能域 → 模块 → 类，支持展开/折叠、缩放、平移、适应屏幕
- 🔍 **全局搜索**：类/方法/属性多标签过滤，按匹配度排序，全库 8 万+ 条记录即时检索
- 📄 **详情面板**：模块类列表、类详情、方法签名/参数/返回值/版本/许可证完整展示
- 🔗 **类型链接跳转**：参数与返回值中的 `NXOpen.*` 类型可点击直达对应类
- 🧭 **面包屑与继承浏览**：父类/子类/嵌套类互链，快速导航
- 📊 **面板内搜索**：模块/类详情内二次过滤，突破 300 条展示上限
- 🔑 **许可证信息**：约 30% 的方法/属性标注了所需的 NX 许可证模块

## 项目结构

```
nxopen-api-map/
├── README.md                ← 本项目说明
├── AGENTS.md                ← 工作区/开发说明（数据管线、设计决策、注意事项）
├── viewer.html              ← 主页面（HTML 结构）
├── viewer.css               ← 样式表
├── app.js                   ← 交互逻辑（D3.js v7）
├── doc/                     ← 结构说明文档
│   ├── pyi-structure.md     ← .pyi 类型存根文件结构详解
│   ├── json-structure.md    ← 中间 JSON 结构说明
│   └── js-structure.md      ← 精简 JS 数据结构说明
├── scripts/                 ← 数据管线脚本
│   ├── parse_pyi.py         ← .pyi 类型存根 → 完整中间 JSON（压缩为 .gz）
│   ├── gen_js.py            ← 压缩 JSON → 精简 JS 数据（分组 + 继承解析）
│   ├── domains.py           ← 功能域映射表（12 域 → 99 模块）
│   └── compress.py          ← JSON 文件压缩/解压工具
└── data/
    ├── nxopen_data.js       ← 精简数据（约 24.9 MB，前端加载）
    └── nxopen_structure.json.gz ← 压缩中间 JSON（约 3.5 MB，随仓库分发）
```

## 快速开始

### 直接使用

用浏览器打开根目录 `viewer.html` 即可（页面通过相对路径加载 `app.js`、`viewer.css` 与 `data/nxopen_data.js`）：

```bash
# Windows
start viewer.html

# macOS / Linux
open viewer.html
```

页面加载 `nxopen_data.js`（约 24.9 MB）需要一定时间，请耐心等待滚动加载。

### 重新生成数据（可选）

如需重新生成解析数据，需先获得 NXOpen Python API 的 `.pyi` 类型存根目录
（99 个顶层模块 + `clss/` 子目录约 1679 个类存根，共约 1778 个文件）。
`.pyi` 存根可通过 `make-nxopen-pyi` 项目从 NX 2212 的 `.pyd` 文件解析生成。依次执行：

```bash
# 步骤 0：（可选）从 .pyd 生成 .pyi 存根 — 使用 make-nxopen-pyi 项目（需 NX 软件）
# python make_pyi.py   # 在 NX 内置 Python 环境中运行

# 步骤 1：解析 .pyi → data/nxopen_structure.json.gz（自动压缩，需 Python 3.10+）
python scripts/parse_pyi.py --source <path_to_NXOpen_folder>

# 步骤 2：精简 + 分组 → data/nxopen_data.js
python scripts/gen_js.py
```

## 数据统计

| 指标 | 数量 |
|------|------|
| 类型存根文件 / 顶层模块 | 1,778 / 99 |
| 功能域 | 12 |
| 类（含嵌套） | 23,377 |
| 方法 / 属性 | 41,501 / 48,017 |
| 有父类 / 有子类的类 | 7,418 / 583 |
| 有许可证的方法/属性 | 27,371（30.6%） |

## 技术栈

- **解析**：Python 3.10+ + `ast`（状态机 docstring 解析）
- **数据**：JSON 中间格式 → 精简 JS（短键名 + 描述截断 + license 字段）
- **前端**：原生 HTML/CSS/JS + [D3.js v7](https://d3js.org/)（CDN 引入），无构建工具，无后端
- **运行环境**：任意现代浏览器

## 常见问题

- **页面空白或卡顿**：数据文件较大（24.9 MB），请等待页面加载完成后操作；建议用 Chrome/Edge 最新版本。
- **`nxopen_structure.json` 在哪里**：仓库中保存的是压缩文件 `nxopen_structure.json.gz`（约 3.5 MB）。`parse_pyi.py` 解析后自动压缩并删除原始 JSON。如需重新生成，先通过 `make-nxopen-pyi` 项目从 NX 2212 的 `.pyd` 文件反射生成 `.pyi` 存根，再运行 `python scripts/parse_pyi.py --source <.pyi目录路径>`。
