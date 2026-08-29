# 精简 JS 数据结构说明（`nxopen_data.js`）

> 本文档说明 `gen_js.py` 从中间 JSON 精简生成的**前端 JS 数据**结构及转换方法。
> 这是数据管线的**最终产物**，供 `viewer.html` + `app.js` 前端加载。
> 中间 JSON 结构详见 [json-structure.md](json-structure.md)，`.pyi` 格式详见 [pyi-structure.md](pyi-structure.md)。

---

## 一、数据管线定位

```
NXOpen/*.pyi ──parse_pyi.py──▶ data/nxopen_structure.json.gz ──gen_js.py──▶ data/nxopen_data.js
 (1778个)     (见 pyi-structure.md)  (压缩中间JSON,~3.5MB)        (本文档)          (精简JS,~24.9MB)

 .pyi 存根由 make-nxopen-pyi 项目从 NX 2212 的 .pyd 文件反射生成。gen_js.py 直接从 .json.gz 解压加载，不解压到磁盘。
```

| 阶段 | 文件 | 体积 | 格式 | 说明文档 |
|------|------|------|------|---------|
| 输入 | `NXOpen/*.pyi` | ~62MB | Python 类型存根 | [pyi-structure.md](pyi-structure.md) |
| 中间 | `data/nxopen_structure.json.gz` | ~3.5MB | gzip 压缩 JSON | [json-structure.md](json-structure.md) |
| **输出** | `data/nxopen_data.js` | ~24.9MB | JS（无缩进） | **本文档** |

---

## 二、转换方法（`gen_js.py`）

### 2.1 总体流程

1. **加载压缩 JSON**：从 `data/nxopen_structure.json.gz` 解压加载（不解压到磁盘）
2. **分离模块**：按模块名前缀 `clss.` 分为顶层模块和类存根模块
3. **展平嵌套类**：`flatten_classes()` 将嵌套类展平为顶层条目，类名加父类前缀
4. **归并 clss 类**：按继承关系（`bases` 含 `NXOpen.<模块>.<类>`）将 clss 类归入对应顶层模块
5. **解析继承**：`resolve_inheritance()` 在所有模块合并完成后第二阶段运行，生成 `par`/`chl`
6. **功能域分组**：将 99 个模块归入 12 个功能域
7. **精简输出**：用短键名 + 数组索引格式输出 `window.NXOPEN_DATA = ...`

### 2.2 关键转换逻辑

| 转换环节 | 实现函数 | 说明 |
|---------|---------|------|
| 展平嵌套类 | `flatten_classes()` | 嵌套类递归展平，输出 `[全名, 描述, 方法, sub?, par?, chl?]` |
| clss 类归并 | `main()` 内 | 按 `bases` 中的 `NXOpen.<模块>.<类>` 匹配父模块；无匹配回退到 `NXOpen` |
| 继承解析 | `resolve_inheritance()` | 第二阶段：全名精确匹配 + 短名回退，生成 `par`/`chl` |
| 功能域分组 | `scripts/domains.py` 中的映射表 | 99 个模块 → 12 个功能域的映射表 |
| 体积精简 | `flatten_classes()` 内 | 短键名 + 空值省略 + 描述截断 |

### 2.3 继承解析细节

`resolve_inheritance()` 在所有模块合并完成后运行：

1. 构建 `全名 → (模块名, 条目)` 映射表 `name_map`
2. 构建 `短名 → [(模块名, 全名)]` 回退映射表 `short_map`
3. 对每个类的 `bases`（原始 Python 基类名），解析为 `(模块名, 全名)`：
   - `object` → 返回 None（外部基类，不可跳转）
   - 全名精确匹配（如 `NXOpen.Body`）→ 命中
   - 短名回退匹配（如 `Body`）→ 取第一个命中
   - 33 个外部基类（非 NXOpen 内部类）标记为不可跳转
4. 将解析结果写入 `par`（索引 4），反向构建 `chl`（索引 5）

### 2.4 输出参数

```bash
python scripts/gen_js.py
```

- 输入路径：`data/nxopen_structure.json.gz`（压缩文件，基于项目根目录定位）
- 输出路径：`data/nxopen_data.js`（基于项目根目录定位）
- JS 格式：`window.NXOPEN_DATA = <JSON>;`，`ensure_ascii=False`，`separators=(',', ':')`（无缩进，最小体积）

---

## 三、JS 数据结构

### 3.1 顶层结构

```javascript
window.NXOPEN_DATA = [
  {
    "n": "核心基础",
    "cc": 4281,
    "mc": 16634,
    "mods": []
  }
]
```

| 键 | 类型 | 说明 |
|----|------|------|
| `n` | string | 功能域名 |
| `cc` | number | 域内类总数 |
| `mc` | number | 域内方法总数 |
| `mods` | Module[] | 模块列表 |

> 12 个功能域按方法数降序排列。

### 3.2 模块（Module）

```javascript
{
  "n": "NXOpen",
  "d": "NXOpen core API",
  "c": []
}
```

| 键 | 类型 | 说明 |
|----|------|------|
| `n` | string | 模块名 |
| `d` | string | 模块描述（截断至 120 字符） |
| `c` | Class[] | 类列表 |

> 模块按方法数降序排列。

### 3.3 类（Class）

精简格式中，类是一个**数组**（非对象），用索引而非键名节省体积：

```javascript
[
  "NXOpen.Body",
  "Represents a Body",
  [],
  []
]
```

| 索引 | 键名 | 类型 | 说明 |
|------|------|------|------|
| 0 | — | string | 类全名（含模块前缀） |
| 1 | — | string | 类描述（截断至 150 字符） |
| 2 | — | Method[] | 方法/属性数组 |
| 3 | sub | array? | 嵌套类数组 |
| 4 | par | array? | 父类数组（继承关系） |
| 5 | chl | array? | 子类数组（继承关系） |

> 索引 3/4/5 为可选字段，无值时省略。

### 3.4 嵌套类数组（sub，索引 3）

```javascript
[
  ["嵌套类短名", "父类全名.嵌套类名", 方法数]
]
```

| 元素 | 类型 | 说明 |
|------|------|------|
| 0 | string | 嵌套类短名 |
| 1 | string | 嵌套类全名（父类全名 + "." + 短名） |
| 2 | number | 嵌套类的方法/属性数（含二级嵌套类方法数） |

### 3.5 父类/子类数组（par/chl，索引 4/5）

```javascript
// 父类 par [4]
[
  ["父类全名", "父类所在模块名"]
]

// 子类 chl [5]
[
  ["子类全名", "子类所在模块名"]
]
```

> 继承关系在所有模块合并完成后由 `resolve_inheritance()` 第二阶段解析。
> 33 个外部基类（非 NXOpen 内部类，如 `object`）标记为不可跳转。

### 3.6 方法/属性（Method/Property）

方法与属性合并在索引 [2] 数组中，用 `pr` 字段区分：

```javascript
// 方法
{
  "n": "GetEdges",
  "d": "Returns the ...",
  "s": "GetEdges()",
  "p": [["facet", "desc", "type"]],
  "r": "a tuple",
  "rt": "list of NXOpen.Edge",
  "rc": [["name", "type", "desc"]],
  "v": "NX3.0.0"
}

// 属性（带 pr:1 标记）
{
  "n": "Density",
  "d": "Returns or sets ...",
  "pr": 1,
  "s": "Density",
  "rt": "float",
  "r": "",
  "p": []
}
```

| 短键 | 全名 | 类型 | 说明 |
|------|------|------|------|
| `n` | name | string | 方法/属性名 |
| `d` | desc | string | 描述（截断至 200 字符） |
| `s` | sig | string? | 签名（无则省略） |
| `p` | params | array? | `[[name, desc, type], ...]`，desc 截断 200，type 截断 80 |
| `r` | returns | string? | 返回值描述（截断至 200 字符） |
| `rt` | rtype | string? | 返回值类型（截断至 200 字符） |
| `rc` | return_components | array? | `[[name, type, desc], ...]`，type 截断 80，desc 截断 200 |
| `v` | version | string? | 版本信息 |
| `lc` | license | string? | 许可证要求（约 26% 非空） |
| `pr` | property | 1? | 属性标记（仅属性有，=1） |

> **字段可选性**：值为空字符串或空数组的字段会被省略（`if m.get("sig")` 等判断），减小体积。

> **license 已传递**：中间 JSON 的 method/property 含 `license` 字段，`gen_js.py` 通过 `lc` 短键将其写入精简 JS（约 76251 条非空）。

---

## 四、中间 JSON → 精简 JS 字段映射

| 中间 JSON 路径 | 精简 JS 位置 | 说明 |
|---------------|-------------|------|
| `module.name` | `domain.mods[].n` | 模块名 |
| `module.doc` | `domain.mods[].d` | 截断 120 |
| `class.name` → 加前缀 | `class[0]` | 全名 |
| `class.doc` | `class[1]` | 截断 150 |
| `class.methods[]` + `class.properties[]` | `class[2]` | 合并 |
| `class.nested_classes[]` | `class[3]` (sub) | 仅名称+计数 |
| `class.bases` | `class[4]` (par) | 解析后 |
| — | `class[5]` (chl) | 反向解析 |
| `method.name` | `method.n` | |
| `method.desc` | `method.d` | 截断 200 |
| `method.sig` | `method.s` | 可选 |
| `method.params[]` | `method.p` | `[[name, desc, type]]` |
| `method.returns` | `method.r` | 可选 |
| `method.rtype` | `method.rt` | 可选 |
| `method.return_components[]` | `method.rc` | 可选 |
| `method.version` | `method.v` | 可选 |
| `method.license` | `method.lc` | 可选 |
| `property.*` | `method.*` + `pr:1` | 同方法 |

---

## 五、12 个功能域分组

`gen_js.py` 将 99 个模块归入 12 个功能域（映射表在 `scripts/domains.py` 中独立维护）：

| 功能域 | 模块数 | 代表模块 |
|--------|--------|---------|
| 核心基础 | 9 | NXOpen, Layer, Display, Select, Fields |
| 建模与特征 | 13 | Features, GeometricUtilities, Facet, SheetMetal |
| 制图与标注 | 7 | Drawings, Drafting, Annotations, MBD |
| 装配与产品数据 | 8 | Assemblies, PDM, Positioning, Placement |
| 仿真分析 | 7 | CAE, SIM, DesignSimulation, GeometricAnalysis |
| 制造加工 | 5 | CAM, Mfg, MfgModel, Tooling, Die |
| 运动与机构 | 3 | Motion, Mechatronics, AME |
| 电气与管路布线 | 7 | Routing, ElectricalRouting, MechanicalRouting |
| 模具与复合材料 | 5 | MoldCooling, Falcon, Composites, Fabric |
| 编程与定制 | 9 | UF, BlockStyler, UIStyler, UserDefinedObjects |
| 报告与可视化 | 4 | Report, VisualReporting, MendixReporting, Markup |
| 行业专用 | 22 | ShipDesign, StageModel, AnimationDesigner, PID |

> 不在 `scripts/domains.py` 中的映射表中的模块归入"其他"域。

---

## 六、数据统计

| 指标 | 中间 JSON | 精简 JS | 差异说明 |
|------|----------|---------|---------|
| 模块数 | 1778 | 99 | clss 类按继承关系归入顶层模块 |
| 功能域 | — | 12 | 精简 JS 新增分组层 |
| 类（含嵌套） | 23183 | 23377 | 含枚举合并后微增 |
| 枚举 | 194 | — | 精简 JS 不区分枚举 |
| 方法+属性 | 89324 | 89518 | 枚举 ValueOf 方法计入 |
| 属性 | 48017 | 48017 | 一致 |
| 有父类的类 | — | 7418 | 精简 JS 解析继承 |
| 有子类的类 | — | 583 | 精简 JS 解析继承 |
| 文件体积 | ~47MB | ~24.9MB | 短键名 + 省略空值 + license 字段 |

> **方法数差异**：中间 JSON 的 `89324` 是方法+属性总数（parse_pyi.py 统计 `methods + properties`）；精简 JS 的 `89518` 同为方法+属性总数，多出的 194 来自枚举的 `ValueOf` 方法（新版处理了枚举）。纯方法数 41501，纯属性数 48017。

> **模块数差异**：中间 JSON 有 1778 个条目（每个 .pyi 一个），精简 JS 合并为 99 个顶层模块（`clss/` 下的类按继承关系归入对应模块）。

---

## 七、注意事项

1. **模块名前缀**：中间 JSON 中 clss/ 文件的模块名带 `clss.` 前缀（如 `"clss.Body"`）；精简 JS 中类按继承关系归入顶层模块，无 `clss.` 前缀。
2. **license 已传递**：中间 JSON 的 method/property 含 `license` 字段，`gen_js.py` 通过 `lc` 短键写入精简 JS（约 76251 条非空）。功能域映射表在 `scripts/domains.py` 中独立维护。
3. **继承关系第二阶段解析**：`resolve_inheritance()` 在所有模块合并完成后运行，生成 `par`（父类）和 `chl`（子类）字段。33 个外部基类标记为不可跳转。
4. **字段可选性**：精简 JS 中，值为空字符串或空数组的字段会被省略（`if m.get("sig")` 等判断），减小体积。
5. **描述截断**：精简 JS 的截断比中间 JSON 更激进（模块描述 120 字符、类描述 150 字符、方法描述 200 字符），以控制体积。
6. **类用数组而非对象**：精简 JS 中类用数组索引（`[0]`全名 / `[1]`描述 / ...）而非对象键名，每条类记录可节省约 40% 体积。