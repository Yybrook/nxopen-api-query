# SQLite 数据库结构说明（`nxopen_api.db`）

> 本文档说明本 skill 的 `scripts/build_index.py` 从中间 JSON 构建的 SQLite 数据库结构。
> 中间 JSON 结构详见 [json-structure.md](json-structure.md)，`.pyi` 格式详见上游 `nxopen-api-map/doc/pyi-structure.md`。

---

## 一、数据管线定位

```
nxopen_structure.json.gz  ──build_index.py──▶  nxopen_api.db
 (压缩中间JSON,~3.2MB)      (本 skill)         (~160MB SQLite+FTS5)
```

| 阶段 | 文件 | 体积 | 说明文档 |
|------|------|------|---------|
| 输入 | `data/nxopen_structure.json.gz` | ~3.2MB | [json-structure.md](json-structure.md) |
| **产物** | `data/nxopen_api.db` | ~160MB | **本文档** |

> **API 来源**：基于 **Siemens NX 2212** 版本的 NXOpen Python API。

---

## 二、主表

### 2.1 `modules`（模块表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| name | TEXT | 模块名，如 NXOpen、CAM、Features |
| doc | TEXT | 模块文档 |
| domain | TEXT | 功能域（12 大分类之一） |

### 2.2 `classes`（类表，含嵌套类）

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

### 2.3 `methods`（方法 + 属性共用表，用 `is_property` 区分）

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

> **注意**：`license` 字段存在于中间 JSON 中，但当前数据库未存储该字段（license 不影响搜索结果）。如需后续增加，在 `methods` 表添加 `license TEXT` 列并在 `build_index.py` 的 INSERT 语句中补充即可。

---

## 三、FTS5 全文索引表（5 张虚拟表）

| 表名 | 索引列 | 分词器 | 用途 |
|------|--------|--------|------|
| `classes_name_fts` | full_name, short_name | **trigram** | 类名子串/camelCase 命中（搜 `Body` 命中 `BodyDes`） |
| `methods_name_fts` | name | **trigram** | 方法名子串/camelCase 命中 |
| `classes_fts` | full_name, doc | unicode61 | 类文档词级全文 + BM25 排序 |
| `methods_fts` | name, desc, params, returns, rtype, rc | unicode61 | 方法描述/参数/返回值/返回类型/rc 全文 + BM25 |
| `methods_body_fts` | name, returns, rtype, params, rc_text | **trigram** | 方法标识符类字段子串检索（让 unitNorm/srf_unormal 等 camelCase 被 normal 命中） |

### FTS5 设计要点

- **name 字段用 trigram**：支持 camelCase 子串命中（搜 `Body` 命中 `BodyDes`），避免 unicode61 不拆 camelCase 的回归。
- **doc/desc/params/returns 用 unicode61**：英文散文词级分词 + BM25 相关度排序。
- **多词查询**：FTS5 MATCH 为任意位置 AND（非连续子串），召回率高于 LIKE。
- trigram 对 <3 字符 token 无 n-gram，`_build_trigram_match` 自动跳过过短 token。
- FTS5 查询词经 `_fts_escape` 双引号转义，防特殊字符（`* ( ) : -` 等）被当作语法。
- `methods_body_fts` 是 contentless FTS5 表（未指定 `content=`），不能增量更新，只能全量重建。`rc_text` 列由 Python 函数 `_rc_text`（注册为 SQLite function）从 rc JSON 解析为纯文本。
- BM25 列权重固定为 `(1.0, 1.0, 1.5, 2.0, 1.5, 1.5)`（name/desc/params/returns/rtype/rc），returns/rc 加权较高以突出返回值/结构体属性命中。

> trigram 分词器需 SQLite ≥ 3.34.0；unicode61 自 SQLite 3.9.0 可用。脚本启动时硬性检测版本。

---

## 四、B-tree 索引

| 索引名 | 表 | 列 |
|--------|----|----|
| `idx_classes_full` | classes | full_name |
| `idx_classes_short` | classes | short_name |
| `idx_classes_mod` | classes | module_id |
| `idx_classes_parent` | classes | parent_class_id |
| `idx_methods_class` | methods | class_id |
| `idx_methods_name` | methods | name |
| `idx_methods_prop` | methods | is_property |
| `idx_mod_domain` | modules | domain |

---

## 五、构建流程（`build_index.py`）

```
[1/4] 加载 JSON    — 读 .json 或 .gz（通过 compress.load_json_from_gz）
[2/4] 建表         — 3 张主表
[3/4] 插入数据     — 合并 clss/ → 顶层模块 → 递归插入类/方法/属性/嵌套类
                   — 结构体属性回灌（_backfill_struct_props）
[4/4] 建索引       — 8 个 B-tree + 5 张 FTS5 虚拟表
```

### 关键逻辑

- **`flatten_classes(classes, prefix, mod_id, conn, parent_id)`** — 递归插入类及其方法/属性/嵌套类。
- **clss/ 模块合并**：看类 `bases` 形如 `NXOpen.X.Y`（≥3 段且首段 NXOpen）则归入模块 X，否则归入 NXOpen。与上游 `nxopen-api-map/scripts/gen_js.py` 保持一致。
- **12 大功能域分组**：`DOMAINS` 字典，定义在 `scripts/domains.py`（独立维护），与上游一致。
- **结构体属性回灌**（`_backfill_struct_props`）：方法返回值若是结构体类，将该结构体属性名+描述追加到方法的 `returns` 字段，使搜 `normal` 能命中 `Evalsf.Evaluate`（返回 `Srfvalue`，含 `SrfUnormal`）。

---

## 六、数据规模

| 指标 | 数量 |
|------|------|
| 模块 | 99 |
| 类（顶层+嵌套） | 23,377 |
| 方法 | 41,501 |
| 属性 | 48,017 |
| 嵌套类 | 21,601 |
| 数据库体积 | ~160MB |

---

## 七、路径约定

- 数据库默认输出到 skill 根目录 `data/nxopen_api.db`。
- 首次运行查询脚本时若数据库不存在，自动从 `data/nxopen_structure.json` 或 `.json.gz` 构建（约 10s，一次性）。
- 路径解析基于 skill 根目录（`scripts/` 的父目录），无论从哪个工作目录调用都正确。
