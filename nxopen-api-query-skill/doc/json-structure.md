# 中间 JSON 结构说明（`nxopen_structure.json`）

> 本文档说明本 skill 的输入数据——**中间 JSON**（`nxopen_structure.json` / `.json.gz`）的结构。
> 该文件由上游项目 `nxopen-api-map` 的 `scripts/parse_pyi.py` 解析 `.pyi` 类型存根后生成，
> 本 skill 的 `scripts/build_index.py` 读取它构建 SQLite 数据库（详见 [database-structure.md](database-structure.md)）。

---

## 一、数据管线定位

```
NXOpen_*.pyd  ──make-nxopen-pyi──▶  NXOpen/*.pyi  ──parse_pyi.py──▶  nxopen_structure.json.gz  ──build_index.py──▶  nxopen_api.db
 (NX 2212)    (反射生成.pyi)       (1778个)       (上游 nxopen-api-map)  (压缩中间JSON,~3.2MB)   (本 skill)         (~160MB SQLite+FTS5)
```

| 阶段 | 文件 | 体积 | 说明文档 |
|------|------|------|---------|
| 输入 | `NXOpen/*.pyi` | ~62MB | 上游 `nxopen-api-map/doc/pyi-structure.md` |
| **中间** | `data/nxopen_structure.json.gz` | ~3.2MB | **本文档** |
| 产物 | `data/nxopen_api.db` | ~160MB | [database-structure.md](database-structure.md) |

> **API 来源**：`.pyi` 类型存根由 **Siemens NX 2212** 版本的 `NXOpen_*.pyd` 二进制模块经反射工具解析生成，共约 1778 个 `.pyi` 文件，覆盖 99 个顶层模块。详见上游项目 `nxopen-api-map`。

---

## 二、顶层结构

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

---

## 三、模块（Module）

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
| `doc` | string | 模块描述 |
| `classes` | Class[] | 类列表 |
| `enums` | Class[] | 枚举列表（结构与类相同，当前数据中模块级均为 `[]`） |
| `functions` | Function[] | 模块级函数列表（当前数据中均为 `[]`） |

> **模块名规则**：顶层文件为 `<文件名>`（如 `"AECDesign"`），`clss/` 子目录文件为 `"clss.<类名>"`（如 `"clss.Body"`）。`build_index.py` 会将 `clss.` 前缀的类按继承关系归入对应顶层模块。

---

## 四、类（Class）

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
| `name` | string | 类名 |
| `doc` | string | 类描述 |
| `bases` | string[] | 父类全名列表（如 `["NXOpen.NXObject"]`） |
| `methods` | Method[] | 方法列表 |
| `properties` | Property[] | 属性列表 |
| `nested_classes` | Class[] | 嵌套类列表（递归结构） |
| `nested_enums` | Class[] | 嵌套枚举列表（递归结构，同 Class） |

> **枚举**：结构与类相同，区别在于被上游 `_is_enum` 判定为枚举并归入 `enums` 列表。枚举的 `bases` 通常为 `["object"]`，`methods` 通常只含一个 `ValueOf` 方法。
>
> **嵌套类**：NXOpen 的 `.pyi` 存根中，有嵌套类的父类是命名空间容器，不含方法/属性。

---

## 五、方法（Method）

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
| `desc` | string | 方法描述 |
| `sig` | string | 方法签名（从 `Signature` 标记提取） |
| `params` | Param[] | 参数列表 |
| `returns` | string | 返回值描述 |
| `rtype` | string | 返回值类型 |
| `return_components` | ReturnComponent[] | 返回值元组组成项 |
| `version` | string | 版本信息 |
| `license` | string | 许可证要求（约 30% 非空） |

---

## 六、属性（Property）

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
| `desc` | string | 属性描述 |
| `sig` | string | 属性签名（通常等于属性名） |
| `rtype` | string | 返回值类型 |
| `returns` | string | 返回值描述 |
| `return_components` | ReturnComponent[] | 返回值元组组成项 |
| `params` | Param[] | 参数列表（属性通常为空） |
| `version` | string | 版本信息 |
| `license` | string | 许可证要求 |

> 属性由 `@property` 装饰器标识，`@xxx.setter` 不单独记录（以 getter 为准）。

---

## 七、参数（Param）

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
| `desc` | string | 参数描述 |
| `type` | string | 参数类型（RST 已清理） |

> **参数顺序**：优先按签名中出现的顺序排列，再补充仅在 docstring `:param` 中出现但不在签名中的参数。

---

## 八、返回值元组组成项（ReturnComponent）

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
| `desc` | string | 组件描述 |

> **两种格式**：
> - **分行式**（如 UF 方法）：`name(`type`):  desc` 写在独立行，解析为 `return_components` 数组
> - **内联式**（如 Body.GetFacetedBody）：全部写在 `:rtype` 一行内，保留在 `rtype` 字符串中，`return_components` 为空数组

---

## 九、字段截断规则

| 字段路径 | 最大长度 | 说明 |
|---------|---------|------|
| `module.doc` / `class.doc` / `method.desc` / `property.desc` | 500 | 描述摘要 |
| `method.returns` / `property.returns` | 300 | 返回值描述 |
| `method.rtype` / `property.rtype` | 200 | 返回值类型 |
| `param.desc` | 300 | 参数描述 |
| `param.type` | 100 | 参数类型 |
| `return_component.desc` | 200 | 组件描述 |

> 截断由上游 `parse_pyi.py` 执行。`build_index.py` 不再截断，原样存入 SQLite。

---

## 十、数据统计

| 指标 | 数量 |
|------|------|
| 模块数（JSON 条目） | 1778 |
| 顶层模块 | 99 |
| 类（含嵌套） | 23,377 |
| 方法 | 41,501 |
| 属性 | 48,017 |
| 有 license 的方法/属性 | ~27,371（30.6%） |

> 详细的数据格式说明见上游项目 `nxopen-api-map/doc/` 目录。
