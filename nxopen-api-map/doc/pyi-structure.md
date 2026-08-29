# NXOpen `.pyi` 类型存根文件结构详解

> 本文档描述 NXOpen Python API 类型存根（`.pyi`）的目录结构与文档字符串（docstring）格式。
> 这是数据管线的**输入端**，由 `parse_pyi.py` 解析为中间 JSON（详见 [json-structure.md](json-structure.md)）。
>
> **注意**：源数据目录路径由用户运行时通过 `--source` 参数提供，本文档不包含任何实际路径。
>
> **来源**：本文档描述的 `.pyi` 类型存根由 **Siemens NX 2212** 版本的 `NXOpen_*.pyd` 二进制模块
> 经 [make_pyi.py](https://github.com/) 反射生成工具解析而来。该工具在 NX 内置 Python 环境中运行，
> 通过反射（introspection）扫描所有 `NXOpen_*.pyd` 模块，提取类、方法、属性等信息并生成 `.pyi` 存根。
> `.pyi` 中的 docstring 内容、签名、参数类型等均来自 `.pyd` 中编译时内嵌的原始文档字符串。

---

## 一、目录结构

```
<源数据目录>/
├── <模块名>.pyi          ← 顶层模块存根（约 99 个）
├── ...                   ← 如 NXOpen.pyi, UF.pyi, CAM.pyi, CAE.pyi ...
├── _nxopen.pyi            ← 辅助文件（解析时自动跳过）
├── __init__.py             ← 辅助文件（解析时自动跳过）
└── clss/                  ← 类存根子目录（约 1679 个）
    ├── <类名>.pyi          ← 如 Body.pyi, Edge.pyi, Face.pyi
    └── ...
```

### 1.1 顶层模块文件（`<模块名>.pyi`）

每个顶层 `.pyi` 文件代表一个 NXOpen 功能模块。文件内定义该模块的顶层类、嵌套类、枚举和模块级函数。

**命名规则**：`<模块名>.pyi`（如 `CAM.pyi`、`CAE.pyi`、`UF.pyi`）

**典型内容**：
```python
import NXOpen
from typing import List

class Layer:
    '''
    ### nxoModuleType
    Default documentation for NXOpen.Layer.
    '''
    class Category(NXOpen.NXObject):
        '''
        ### nxoType
        Represents a layer category.
        ...
        '''
        def GetMemberLayers(self, *args, **kw) -> List[int]:
            '''
            ### nxoMethodDescriptorType
            Returns all the layers that belong to the category
            Signature ``GetMemberLayers()``
            :returns:
            :rtype: list of int
            .. versionadded:: NX3.0.0
            License requirements: None.
            '''
            ...
```

### 1.2 类存根文件（`clss/<类名>.pyi`）

`clss/` 子目录下每个文件对应一个类的存根。这些类文件会被 `gen_js.py` 按继承关系归入对应顶层模块。

**命名规则**：`clss/<类名>.pyi`（如 `clss/Body.pyi`）

**典型内容**：
```python
import NXOpen
from typing import List

class Body(NXOpen.DisplayableObject):
    '''
    ### nxoType
    Represents a Body
    .. versionadded:: NX3.0.0
    '''
    def GetEdges(self, *args, **kw) -> List[NXOpen.Edge]:
        '''
        ### nxoMethodDescriptorType
        Returns the edges in the body
        Signature ``GetEdges()``
        :returns:
        :rtype: list of :py:class:`NXOpen.Edge`
        .. versionadded:: NX3.0.0
        License requirements: solid_modeling ("SOLIDS MODELING")
        '''
        ...
```

---

## 二、docstring 标记类型（`### nxo*`）

每个 docstring 的第一行通常是一个 `### nxo*Type` 标记，用于区分元素类型：

| 标记 | 含义 | 出现位置 |
|------|------|---------|
| `### nxoModuleType` | 模块/命名空间类型 | 模块级类、命名空间容器类 |
| `### nxoType` | 类型定义 | 类定义 |
| `### nxoMethodDescriptorType` | 方法描述符 | 方法定义 |
| `### nxoGetSetDescriptorType` | 属性 Get/Set 描述符 | `@property` 属性 |
| `### nxoBuiltinFunctionType` | 内置函数 | 枚举的 `ValueOf` 等内置方法 |
| `### nxoClsAliasType` | 类别名 | 枚举成员的别名声明 |

---

## 三、方法 docstring 格式详解

### 3.1 标准方法格式

```
### nxoMethodDescriptorType
方法描述文字（可能多行）...
Signature ``方法名(参数列表) -> 返回类型``
:param 参数名: 参数描述
:type 参数名: PythonType
:returns: 返回值描述
:rtype: PythonType
.. versionadded:: NX 12.0.0
License requirements: xxx
```

### 3.2 签名行（Signature）

签名有两种写法：

**写法 A — 无冒号，签名与 `Signature` 同行**（常见于 clss/ 下的类文件）：
```
Signature ``GetEdges()``
```

**写法 B — 有冒号，签名换行**（常见于 UF.pyi 等模块）：
```
Signature:
``AskFlagStatus()``
```

> ⚠️ 解析器需同时兼容两种格式。优先匹配 `Signature\s*:?\s*``...`` ` 模式。

### 3.3 参数标记（`:param` / `:type`）

```
:param edges:  The input facet, next to which facet is to find.
:type edges: :py:class:`NXOpen.ConvergentFacet`
```

- `:param name: desc` — 参数描述，支持多行续行
- `:type name: type` — 参数类型，可能含 RST 标记如 `:py:class:`NXOpen.Edge``
- 参数顺序：优先按签名中出现的顺序排列，再补充仅在 docstring 中出现的参数

### 3.4 返回值标记（`:returns` / `:rtype`）

```
:returns:  the first facet on a body.
:rtype: :py:class:`NXOpen.ConvergentFacet`
```

**返回值元组格式** — 当返回值为元组时，`:rtype` 描述元组组成，后续行为各组件：

```
:returns: a tuple
:rtype: A tuple consisting of (facetBody, upToDate). facetBody is a :py:class:`NXOpen.Facet.FacetedBody`. upToDate is a bool.
```

或组件分行写：

```
:rtype: A tuple consisting of (instance,errorStatus)
instance(`Tag`):  Tag of the new instance
errorStatus(`int`):  Error status
```

> 组件格式：`name(`type`):  description`（带冒号）或 `name(`type`)  description`（无冒号）

### 3.5 版本标记（`.. versionadded` / `.. versionchanged` / `.. deprecated`）

```
.. versionadded:: NX3.0.0
.. versionchanged:: NX12.0.0
.. deprecated:: NX2007.0.0
```

- `versionadded` 优先；`versionchanged` 追加 `(changed ...)`；`deprecated` 前缀 `deprecated`
- 遇到版本标记时，结构化字段解析结束

### 3.6 许可证标记（`License requirements`）

```
License requirements: solid_modeling ("SOLIDS MODELING")
License requirements: None.
License requirements: None
```

- 约 26% 的方法/属性带有真实许可证要求（非 `None`）
- 遇到此标记时，结构化字段解析结束

### 3.7 紧凑写法（单行 docstring）

部分方法（如枚举的 `ValueOf`）将所有标记写在一行内，无空格分隔：

```
:param value: Any integer value or bit operation result of enum members:type value: int:returns:  Enum member equivalent to the e value passed.
:rtype: Enum Member type.
```

> ⚠️ 解析器需预处理：在各字段标记前插入换行，以兼容此紧凑写法。

---

## 四、属性 docstring 格式（Get/Set）

`@property` 属性使用 `### nxoGetSetDescriptorType`，其 docstring 用 `` ``---`` `` 分隔线分为 Getter 和 Setter 两段：

```
### nxoGetSetDescriptorType
Returns or sets  the solid density of the body.
The units of the density will be in kilograms per cubic meter
``-------------------------------------``
Getter Method
Signature ``Density``
:returns:
:rtype: float
.. versionadded:: NX3.0.0
License requirements: solid_modeling ("SOLIDS MODELING")
``-------------------------------------``
Setter Method
Signature ``Density``
:param density:
:type density: float
.. versionadded:: NX3.0.0
License requirements: solid_modeling ("SOLIDS MODELING")
```

> ⚠️ `` ``---`` `` 分隔线本身是双反引号包裹的内容。解析器若直接取第一个 `` ``...`` `` 会误取分隔线而非真实签名。
> 修复方案：优先匹配 `Signature` 标记后的 `` ``...`` ``。

**AST 结构**：
```python
@property
def Density(self) -> float:
    '''...getter docstring...'''
    ...

@Density.setter
def Density(self, value: float): ...
```

- `@property` 方法 → 归入 `properties` 列表
- `@xxx.setter` 方法 → 跳过（属性以 getter 为准）

---

## 五、枚举类格式

枚举类继承 `object`，类体由多个成员赋值 + 一个 `ValueOf` classmethod 组成：

```python
class AlignmentStyleT(object):
    '''
    ### nxoType
    alignment style
    .. Usable only on Windows
    .. versionadded:: NX1953.0.0
    Enum Members
    .. csv-table::
    :header: "Enum Member", "Enum Member Description"
    "NotSet", " - "
    "Horizontal", " - "
    "Vertical", " - "
    '''
    Horizontal: NXOpen.AlignmentStyleTMemberType = ...
    '''
    ### nxoClsAliasType
    None
    '''
    NotSet: NXOpen.AlignmentStyleTMemberType = ...
    '''
    ### nxoClsAliasType
    None
    '''
    Vertical: NXOpen.AlignmentStyleTMemberType = ...
    '''
    ### nxoClsAliasType
    None
    '''

    @classmethod
    def ValueOf(cls, value: int):
        '''
        ### nxoBuiltinFunctionType
        Returns enum member equivalent to the value passed.
        Signature ``ValueOf(value)``
        :param value: ...
        :type value: int
        :returns:  Enum member equivalent to the value passed.
        :rtype: Enum Member type.
        .. versionadded:: NX9.0.1
        License requirements: None.
        '''
        ...
```

### 枚举判定规则（`_is_enum`）

枚举类的特征：
1. 类体含大量赋值（`Assign` / `AnnAssign`）——枚举成员
2. 每个成员赋值后跟一个 `Expr`（docstring 节点）
3. 含且仅含一个 `ValueOf` classmethod（内置方法）
4. **不含**其他业务方法（`FunctionDef`）

**启发式判定**：
1. 基类名含 `"Enum"` → 直接判定为枚举
2. 忽略 `ValueOf` 内置方法后，若仍有方法 → **不是枚举**（排除 `UF.UF.Curve` 这类含类型别名赋值的类）
3. `Expr`（docstring）节点不计入"其他"节点数
4. 赋值 > 3 且"其他"节点 ≤ 2 → 判定为枚举

> ⚠️ 关键修复：必须同时忽略 `ValueOf` 方法 + `Expr` 节点不计入 other，否则 194 个真枚举会被误判为普通类。

---

## 六、嵌套类与命名空间容器

NXOpen 的 `.pyi` 存根中，**有嵌套类的父类是命名空间容器，不含方法/属性**。

```python
class UF:
    '''
    ### nxoModuleType
    Default documentation for NXOpen.UF.
    '''
    class Abort(object):
        '''...'''
        def AskFlagStatus(self, *args, **kw) -> bool: ...
    class Assem(object):
        '''...'''
        def ActivateSequence(self, *args, **kw): ...
```

- `UF` 类本身是命名空间容器（无方法/属性）
- `Abort`、`Assem` 等是嵌套类，含实际方法
- 嵌套类中还可能包含 RST 超链接：`` `UF_ABORT_ask_flag_status <../ugopen_doc/...>`_ ``

---

## 七、RST 标记

docstring 中可能含以下 RST（reStructuredText）标记，解析器需清理为纯文本：

| RST 标记 | 示例 | 清理后 |
|----------|------|--------|
| 超链接 | `` `text <url>`_ `` | `text` |
| `:py:class:` | `:py:class:`NXOpen.Edge`` | `NXOpen.Edge` |
| `:py:meth:` | `:py:meth:`NXOpen.Layer.CategoryCollection.CreateCategory`` | `NXOpen.Layer.CategoryCollection.CreateCategory` |
| 双反引号代码 | ` ``code`` ` | `code` |
| 单反引号 | `` `text` `` | `text`（但不清理类型注解中的） |

---

## 八、已知格式陷阱

1. **`` ``---`` `` 分隔线**：Get/Set 属性的 docstring 用 `` ``---...---`` `` 分隔 Getter/Setter，分隔线本身是双反引号包裹内容，会被误当作签名。
2. **两种 Signature 写法**：`Signature ``...``` `（无冒号）和 `Signature:\n```...``` `（有冒号换行）并存。
3. **枚举的 ValueOf 方法**：枚举类普遍含一个 `ValueOf` classmethod，若不忽略会导致枚举被误判为普通类。
4. **枚举成员的 Expr 节点**：每个枚举成员赋值后的 docstring 是 AST `Expr` 节点，计入"其他"节点会使枚举判定阈值失效。
5. **紧凑 docstring**：部分方法将 `:param`/`:type`/`:returns`/`:rtype` 写在一行内无空格分隔。
6. **参数段截取**：签名含返回类型注解时（`method(a) -> Body`），简单的 `split('(')[-1].rstrip(')')` 会混入返回类型。
7. **clss 前缀**：`rel.startswith("clss")` 会误匹配 `clssXXX.pyi`（非 clss/ 子目录文件）。

---

## 九、docstring 行截断（make_pyi.py 副作用）

`.pyi` 文件由 `make_pyi.py`（反射生成工具）产出。该工具的 `docs()` 方法在输出 docstring 时，会按固定宽度对**每一行**做硬截断：

```python
# make_pyi.py 中 docs() 的截断逻辑（简化示意）
mx = 130              # 基础宽度上限
ll = mx - lv * 4      # 每层缩进减 4 字符（lv 为嵌套层级）
for k in range(0, len(line), ll):
    yield (lv + 1) * "\t" + line[k : min(len(line), k + ll)]
```

即：原始 docstring 的每一行被按 `130 - 缩进*4` 字符切段，超宽部分换到下一行续写。

### 9.1 影响范围

- `clss/` 目录下约 **41 处** `Signature` 行被截断为跨两行
- 截断发生在反引号**中间**，闭合的 ` `` ` 被推到下一行

### 9.2 截断示例

`FacetSelectionRuleFactory.pyi` 的 `CreateRuleFineBrushFacets` 方法（第 102-103 行）：

```
Signature ``CreateRuleFineBrushFacets(brushToolStartPoint, brushToolDirection, brushToolRadius, allowHiddenFacetsSel, seedFace
t)``
```

原始 docstring 中 `Signature ``CreateRuleFineBrushFacets(..., seedFacet)`` ` 是一行，
`make_pyi.py` 在 `seedFacet` 中间截断为 `seedFace` + `t)`，导致 ` `` ` 闭合反引号落到第二行。

### 9.3 对解析器的影响

- `Signature\s*:?\s*``([^`]+)`` ` 正则中 `[^`]+` **能匹配换行符**（`\n` 不是反引号），
  所以跨行签名**仍能被捕获**
- 但捕获到的签名文本会**残留 `\n` 字符**，如 `...seedFace\nt)`

### 9.4 解析器修复

签名提取后用 `_RE_WS`（`\s+`）将所有空白（含换行）折叠为单个空格：

```python
info["sig"] = _RE_WS.sub(' ', candidate).strip()
```

修复后签名变为 `...seedFace t)`（空格分隔），文本干净，不影响后续参数提取
（参数从 `:param` 标记解析，不受签名文本影响）。

### 9.5 其他被截断的内容

除 `Signature` 行外，`:param`/`:type`/`:returns` 描述的长行也可能被截断为多行。
解析器的预处理步骤（在各字段标记前插入换行）和续行累积逻辑已能正确处理这些情况，
描述文本会被合并为单行。
