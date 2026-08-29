# 中间 JSON 结构说明（`nxopen_structure.json`）

> 本文档说明 `parse_pyi.py` 解析 `.pyi` 类型存根后输出的**中间 JSON** 结构及转换方法。
> 这是数据管线的**中间产物**，随后由 `gen_js.py` 精简为前端 JS 数据（详见 [js-structure.md](js-structure.md)）。
> `.pyi` 文件格式详见 [pyi-structure.md](pyi-structure.md)。

---

## 一、数据管线定位

```
NXOpen/*.pyi ──parse_pyi.py──▶ data/nxopen_structure.json.gz ──gen_js.py──▶ data/nxopen_data.js
 (1778个)     (本文档)          (压缩中间JSON,~3.5MB)            (见 js-structure.md)   (精简JS,~24.9MB)

 .pyi 存根由 make-nxopen-pyi 项目从 NX 2212 的 .pyd 文件反射生成。解析后自动压缩为 .json.gz，原始 .json 已删除。.json.gz 随仓库分发。
```

| 阶段 | 文件 | 体积 | 格式 | 说明文档 |
|------|------|------|------|---------|
| 输入 | `NXOpen/*.pyi` | ~62MB | Python 类型存根 | [pyi-structure.md](pyi-structure.md) |
| **中间** | `data/nxopen_structure.json.gz` | ~3.5MB | gzip 压缩 JSON | **本文档** |
| 输出 | `data/nxopen_data.js` | ~24.9MB | JS（无缩进） | [js-structure.md](js-structure.md) |

---

## 二、转换方法（`parse_pyi.py`）

### 2.1 总体流程

1. **扫描目录**：`os.walk` 遍历源目录，收集所有 `.pyi` 文件，按位置分为顶层模块文件和 `clss/` 子目录文件
2. **AST 解析**：对每个文件用 `ast.parse` 解析为 AST
3. **递归提取**：遍历 AST，提取模块 → 类 → 方法/属性层级
4. **docstring 解析**：用状态机逐行解析 docstring，提取描述、签名、参数、返回值、版本、许可证
5. **RST 清理**：清理 docstring 中的 RST 标记（超链接、`:py:class:` 等）
6. **输出 JSON**：汇总所有模块，写入 `data/nxopen_structure.json`

### 2.2 关键转换逻辑

| 转换环节 | 实现函数 | 说明 |
|---------|---------|------|
| docstring 描述提取 | `clean_doc()` | 截取 `Signature`/`:param` 等标记前的正文，清理 RST，截断 500 字符 |
| docstring 结构化解析 | `parse_method_doc()` | 状态机逐行解析 `:param`/`:type`/`:returns`/`:rtype`/版本/许可证 |
| 签名提取 | `parse_method_doc()` 内 | 优先匹配 `Signature\s*:?\s*``...`` `，回退取第一个 `` ``...`` `` |
| 返回值元组组成项 | `_parse_return_component()` | 解析 `name(`type`):  desc` 格式 |
| 类解析 | `parse_class()` | 递归解析 ClassDef，区分方法/属性/嵌套类/嵌套枚举 |
| 枚举判定 | `_is_enum()` | 启发式：忽略 ValueOf + Expr 不计入 other + 赋值>3 且 other≤2 |
| 基类提取 | `_get_bases()` | 用 `ast.unparse` 获取基类全名 |
| RST 清理 | `_clean_rst()` | 清理超链接、`:py:class:`、双/单反引号等 |

### 2.3 文件分类

- **顶层模块文件**：不在 `clss/` 子目录下的 `.pyi`（如 `NXOpen.pyi`、`UF.pyi`），模块名 = 文件名
- **类存根文件**：`clss/` 子目录下的 `.pyi`（如 `clss/Body.pyi`），模块名 = `clss.<类名>`
- **辅助文件**：`_nxopen.pyi` 和 `__init__.py` 在解析时自动跳过

### 2.4 输出参数

```bash
python scripts/parse_pyi.py --source <path_to_NXOpen_folder> [--output PATH]
```

- `--source`（必填）：NXOpen 文件夹路径
- `--output`（可选）：输出 JSON 路径，默认 `data/nxopen_structure.json`
- JSON 格式：`ensure_ascii=False`（中文不转义），`indent=1`（每层 1 空格），解析后自动 gzip 压缩为 `.json.gz`

---

## 三、JSON 结构

### 3.1 顶层结构

中间 JSON 是一个**模块数组**，每个元素代表一个 `.pyi` 文件：

```json
[
  {
    "name": "模块名",
    "file": "文件名.pyi",
    "doc": "模块描述",
    "classes": [],
    "enums": [],
    "functions": []
  }
]
```

### 3.2 模块（Module）

```json
{
  "name": "AECDesign",
  "file": "AECDesign.pyi",
  "doc": "",
  "classes": [],
  "enums": [],
  "functions": []
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 模块名（顶层文件名，或 `clss.类名`） |
| `file` | string | 源文件名 |
| `doc` | string | 模块描述（截断至 500 字符） |
| `classes` | Class[] | 类列表 |
| `enums` | Class[] | 枚举列表（结构与类相同） |
| `functions` | Function[] | 模块级函数列表 |

### 3.3 类（Class）

```json
{
  "name": "AECDesignNavigator",
  "doc": "Represents ...",
  "bases": ["NXOpen.NXObject"],
  "methods": [],
  "properties": [],
  "nested_classes": [],
  "nested_enums": []
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 类名（不含模块前缀） |
| `doc` | string | 类描述（截断至 500 字符） |
| `bases` | string[] | 基类全名列表 |
| `methods` | Method[] | 方法列表 |
| `properties` | Property[] | 属性列表 |
| `nested_classes` | Class[] | 嵌套类列表（递归结构，同 Class） |
| `nested_enums` | Class[] | 嵌套枚举列表（递归结构，同 Class） |

> **枚举**：结构与类完全相同，区别在于被 `_is_enum` 判定为枚举并归入 `enums` 列表。枚举的 `bases` 通常为 `["object"]`，`methods` 通常只含一个 `ValueOf` 方法。

### 3.4 方法（Method）

```json
{
  "name": "Hide",
  "desc": "Hides a navigator.",
  "sig": "Hide()",
  "params": [],
  "returns": "",
  "rtype": "",
  "return_components": [],
  "version": "NX2206.0.0",
  "license": "nx_bim (\"AEC Design\")"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 方法名 |
| `desc` | string | 方法描述（截断至 500 字符） |
| `sig` | string | 方法签名（从 `Signature` 标记提取） |
| `params` | Param[] | 参数列表 |
| `returns` | string | 返回值描述（截断至 300 字符） |
| `rtype` | string | 返回值类型（截断至 200 字符） |
| `return_components` | ReturnComponent[] | 返回值元组组成项 |
| `version` | string | 版本信息 |
| `license` | string | 许可证要求 |

### 3.5 属性（Property）

```json
{
  "name": "Density",
  "desc": "Returns or sets ...",
  "sig": "Density",
  "rtype": "float",
  "returns": "",
  "return_components": [],
  "params": [],
  "version": "NX3.0.0",
  "license": "solid_modeling (\"SOLIDS MODELING\")"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 属性名 |
| `desc` | string | 属性描述（截断至 500 字符） |
| `sig` | string | 属性签名（通常等于属性名） |
| `rtype` | string | 返回值类型（截断至 200 字符） |
| `returns` | string | 返回值描述（截断至 300 字符） |
| `return_components` | ReturnComponent[] | 返回值元组组成项 |
| `params` | Param[] | 参数列表（属性通常为空） |
| `version` | string | 版本信息 |
| `license` | string | 许可证要求 |

> 属性由 `@property` 装饰器标识，`@xxx.setter` 不单独记录（以 getter 为准）。

### 3.6 参数（Param）

```json
{
  "name": "viewIndex",
  "desc": "ship navigator id",
  "type": "int"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 参数名 |
| `desc` | string | 参数描述（截断至 300 字符） |
| `type` | string | 参数类型（截断至 100 字符，RST 已清理） |

> **参数顺序**：优先按签名中出现的顺序排列，再补充仅在 docstring `:param` 中出现但不在签名中的参数。

### 3.7 返回值元组组成项（ReturnComponent）

```json
{
  "name": "facetBody",
  "type": "NXOpen.Facet.FacetedBody",
  "desc": "a NXOpen.Facet.FacetedBody"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 组件名 |
| `type` | string | 组件类型 |
| `desc` | string | 组件描述（截断至 200 字符） |

> **两种格式**：
> - **分行式**（如 UF 方法）：`name(`type`):  desc` 写在独立行，解析为 `return_components` 数组
> - **内联式**（如 Body.GetFacetedBody）：全部写在 `:rtype` 一行内，保留在 `rtype` 字符串中，`return_components` 为空数组

### 3.8 模块级函数（Function）

```json
{
  "name": "函数名",
  "desc": "函数描述",
  "sig": "函数签名",
  "params": [],
  "returns": "返回值描述",
  "rtype": "返回值类型",
  "license": "许可证要求"
}
```

> 模块级函数不含 `return_components` 和 `version` 字段。

---

## 四、字段截断规则汇总

| 字段路径 | 最大长度 | 说明 |
|---------|---------|------|
| `module.doc` / `class.doc` / `method.desc` / `property.desc` | 500 | 描述摘要 |
| `method.returns` / `property.returns` | 300 | 返回值描述 |
| `method.rtype` / `property.rtype` | 200 | 返回值类型 |
| `param.desc` | 300 | 参数描述 |
| `param.type` | 100 | 参数类型 |
| `return_component.desc` | 200 | 组件描述 |

---

## 五、数据统计

| 指标 | 数量 |
|------|------|
| 模块数（JSON 条目） | 1778 |
| 类（含嵌套） | 23183 |
| 枚举 | 194 |
| 方法 | 89324 |
| 属性 | 48017 |
| 文件体积 | ~47MB |

> **模块名规则**：顶层文件为 `<文件名>`（如 `"AECDesign"`），clss 子目录文件为 `"clss.<类名>"`（如 `"clss.Body"`）。`gen_js.py` 会将 `clss.` 前缀的类按继承关系归入对应顶层模块。
