# NXOpen Python 类型存根生成器（make-nxopen-pyi）

## 📖 项目简介

本项目是一个 **NXOpen Python 类型存根（`.pyi`）自动生成工具**。

Siemens NX 是一款工业级 CAD/CAM/CAE 软件，它提供了基于 Python 的二次开发 API（NXOpen）。然而，NX 的 Python API 是编译好的二进制模块（`.pyd` 文件），IDE 无法直接从中获取类型信息，导致编写 NX Python 脚本时**没有代码补全、类型检查和文档提示**。

本工具通过**反射（introspection）**技术，在 NX 内置的 Python 环境中动态扫描所有 NXOpen 模块，提取其中的类、方法、属性、成员等信息，并自动生成对应的 `.pyi` 类型存根文件，从而让 IDE 获得完整的智能提示能力。

---

## 🚀 功能特性

- ✅ 自动扫描所有 `NXOpen_*.pyd` 二进制模块
- ✅ 提取类、实例方法、类方法、属性、成员变量等信息
- ✅ 自动解析文档字符串（docstring）中的返回类型注解
- ✅ 自动处理继承关系，避免在子类中重复声明父类成员
- ✅ 特殊处理基础类型（`NXObject`、`TaggedObject`、`INXObject`）的继承链
- ✅ 生成结构化的 `.pyi` 文件，支持 IDE 智能提示

---

## 📋 运行前提

| 条件 | 说明 |
|------|------|
| **NX 软件** | 需安装 Siemens NX（提供 Python 运行环境及 NXOpen 模块） |
| **环境变量** | `UGII_BASE_DIR` 必须指向 NX 安装根目录（NX 启动时自动设置） |
| **运行环境** | 必须在 NX 内置的 Python 环境中运行（通常通过 NX 的 Journal 功能启动） |

> ⚠️ **注意**：由于脚本需要 `import NXOpen` 并访问 NX 安装目录下的 `.pyd` 文件，因此无法在普通的 Python 环境中直接运行，必须通过 NX 的 Python 脚本入口执行。

> ✅ **测试环境**：本项目已在 **Siemens NX 2212** 版本中测试通过。

---

## 🔧 使用方法

### 方法一：通过 NX 的 Journal 功能运行

1. 打开 NX 软件
2. 菜单栏 → `File` → `Execute` → `Journal...`（或对应版本的 Python 脚本入口）
3. 选择本项目的 `make_pyi.py` 文件执行
4. 脚本运行完成后，在当前工作目录下会生成 `NXOpen/` 文件夹

### 方法二：通过命令行在 NX Python 环境中运行

```bash
# 确保 UGII_BASE_DIR 环境变量已设置
echo %UGII_BASE_DIR%

# 使用 NX 自带的 Python 解释器运行脚本
"<NX安装路径>\nxbin\python\python.exe" make_pyi.py
```

---

## 📁 输出文件结构

脚本运行后，会在当前目录下生成如下结构：

```
NXOpen/
├── __init__.py              # 包初始化文件，导入所有子模块和类
├── _nxopen.pyi              # 主类型存根，导入所有类定义
├── Features.pyi             # 子模块存根示例（Features 模块）
├── Drawings.pyi             # 子模块存根示例（Drawings 模块）
├── ...                      # 其他子模块存根
└── clss/                    # 各类的独立存根文件目录
    ├── NXObject.pyi         # NXObject 基类存根
    ├── TaggedObject.pyi     # TaggedObject 基类存根
    ├── INXObject.pyi        # INXObject 基类存根
    ├── Session.pyi          # Session 类存根
    └── ...                  # 其他类存根
```

### 生成的 .pyi 文件示例

```python
# NXOpen/clss/NXObject.pyi 示例
import NXOpen
from typing import List

class NXObject(NXOpen.TaggedObject,NXOpen.INXObject):
    '''
    ### nxoType
    Represents an NX object.
    '''
    @property
    def Name(self)->str:
        '''
        ### nxoGetSetDescriptorType
        Returns the name of the object.
        '''
        ...
    @Name.setter
    def Name(self,value:str):...
    
    def Dispose(self):
        '''
        ### nxoMethodDescriptorType
        Frees the object.
        '''
        ...
```

---

## 🏗️ 技术架构

### 类继承关系

```
pyibase (基类 —— 所有节点的根基)
  ├── nxoModuleType              # 子模块节点
  ├── basetps                    # 基础类型节点（NXObject/TaggedObject/INXObject）
  ├── nxoType                    # 普通类节点
  ├── nxoMethodDescriptorType    # 实例方法节点
  ├── nxoGetSetDescriptorType    # 属性节点（getter/setter）
  ├── nxoMemberDescriptorType    # 成员变量节点
  ├── nxoBuiltinFunctionType      # 类方法/内建函数节点
  ├── nxoClsAliasType             # 类别名节点
  └── mainModules                # 顶层入口节点
```

### 工作流程

```
┌─────────────────────────────────────────────────────┐
│ 1. 读取环境变量 UGII_BASE_DIR                        │
│    定位 NX 安装目录下的 nxbin/python 文件夹          │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ 2. 扫描并导入所有 NXOpen_*.pyd 二进制模块            │
│    存储到 imp_mds 字典中                             │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ 3. 创建 mainModules 实例                            │
│    反射扫描 NXOpen 主模块 + 所有子模块               │
│    对每个成员按类型分类存储到不同字典中               │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ 4. 调用 pyi() 方法                                  │
│    遍历所有节点，调用各自的 toStr() 生成 .pyi 代码    │
│    写入到 ./NXOpen/ 目录下的各文件中                 │
└─────────────────────────────────────────────────────┘
```

### 成员分类逻辑

| Python 类型 | 对应节点类 | 存储字典 | .pyi 输出形式 |
|-------------|-----------|---------|--------------|
| `ModuleType` | `nxoModuleType` | `chdmdls` | `class 模块名: ...` |
| `type`（类） | `nxoType` / `basetps` | `chdtps` | `class 类名(父类): ...` |
| `MethodDescriptorType` | `nxoMethodDescriptorType` | `MdDescriptor` | `def 方法名(self,*args,**kw): ...` |
| `GetSetDescriptorType` | `nxoGetSetDescriptorType` | `GSDescriptor` | `@property` + setter |
| `MemberDescriptorType` | `nxoMemberDescriptorType` | `mberDescriptor` | `变量名: 类型 = ...` |
| `BuiltinFunctionType` | `nxoBuiltinFunctionType` | `mthdorbutin` | `@classmethod def 方法名(cls,...)` |
| NXOpen 实例 | `nxoClsAliasType` | `nxc` | `名称: 类型 = ...` |

### 返回类型解析

脚本使用 4 个正则表达式，按优先级从文档字符串中提取返回类型：

| 优先级 | 正则模式 | 匹配示例 | 输出类型 |
|--------|---------|---------|---------|
| 1 | `:rtype: :py:class:\`XXX\`` | `:rtype: :py:class:\`Part\`` | `Part` |
| 2 | `:rtype: list of :py:class:\`XXX\`` | `:rtype: list of :py:class:\`Face\`` | `List[Face]` |
| 3 | `:rtype: XXX` | `:rtype: int` | `int` |
| 4 | `:rtype: list of XXX` | `:rtype: list of str` | `List[str]` |

---

## ❓ 常见问题

### Q: 运行时报 `ModuleNotFoundError: No module named 'NXOpen'`

**A**: 需要在 NX 的 Python 环境中运行，而非系统默认 Python。NXOpen 模块由 NX 软件提供，仅在其内置 Python 中可用。

### Q: 运行时报 `UGII_BASE_DIR is None`

**A**: 环境变量 `UGII_BASE_DIR` 未设置。请确保通过 NX 启动脚本运行，或手动设置该环境变量指向 NX 安装根目录。

### Q: 生成的 .pyi 文件中有些方法没有返回类型

**A**: 这是因为 NXOpen 的文档字符串中未包含 `:rtype:` 信息，`findrtype()` 函数无法解析出返回类型。这是 NX API 文档的限制，非脚本 bug。

### Q: 如何在 IDE 中使用生成的存根文件？

**A**: 将生成的 `NXOpen/` 文件夹放置在项目的 Python 路径中（如 `site-packages/` 或项目根目录），IDE 即可自动识别 `.pyi` 文件并提供智能提示。

---

## 📚 参考文档

- [NXOpen Python API 二次开发相关](https://www.cnblogs.com/unm001/p/16259771.html?_refluxos=a10)

