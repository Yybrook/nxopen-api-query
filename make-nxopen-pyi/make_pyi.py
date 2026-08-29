# -*- coding: utf-8 -*-
"""
make_pyi.py — NXOpen Python 类型存根（.pyi）自动生成工具

功能概述:
    本脚本运行在 NX 内置的 Python 环境中，通过反射（introspection）扫描
    Siemens NX 软件提供的所有 NXOpen 二进制模块（.pyd），自动提取其中
    的类、方法、属性、成员等信息，并生成对应的 Python 类型存根文件
    （.pyi），以便在 VS Code / PyCharm 等 IDE 中获得代码补全、类型检查
    和文档提示能力。

前置条件:
    1. 需在 NX 的 Python 环境中运行（通常通过 NX 的 \"Journal\" 或
       \"Python Script\" 功能启动）。
    2. 环境变量 UGII_BASE_DIR 必须指向 NX 的安装根目录。

输出结构:
    ./NXOpen/
    ├── __init__.py          # 包初始化文件，导入所有子模块
    ├── _nxopen.pyi          # 主类型存根，导入所有类
    ├── <子模块名>.pyi       # 各子模块对应的存根文件（如 Features.pyi）
    └── clss/
        └── <类名>.pyi       # 各类单独的存根文件（如 NXObject.pyi）
"""

from typing import Dict, Generator, List, Optional
import NXOpen          # NX 官方 Python API 主模块
import types           # Python 内置类型检测模块
import os
import re              # 正则表达式，用于解析文档字符串中的返回类型
from importlib import import_module  # 动态导入模块

# ===========================================================================
# 第一部分：加载 NX 安装目录下的所有 NXOpen_*.pyd 二进制模块
# ===========================================================================

# 获取 NX 安装根目录（环境变量 UGII_BASE_DIR 由 NX 自动设置）
ugii_base_dir = os.getenv("UGII_BASE_DIR")

# NX 内置 Python 模块所在的路径，例如: C:\\Program Files\\Siemens\\NX xxx\\nxbin\\python
pp = os.path.join(str(ugii_base_dir), "nxbin", "python")

# imp_mds: 存储所有成功导入的子模块，键为短名（如 "Features"），值为模块对象
imp_mds = {}
# 遍历 nxbin/python 目录，仅扫描第一层（不递归子目录）
for root, dirs, files in os.walk(pp, topdown=True):

    if root != pp:
        # 只处理顶层目录，遇到子目录就停止
        continue

    for ff in files:
        # 只处理以 "NXOpen_" 开头、以 ".pyd" 结尾的二进制扩展模块文件
        if str(ff).startswith("NXOpen_") and str(ff).endswith(".pyd"):
            module_name = str(ff)[:-4]  # 去掉 .pyd 后缀，得到完整模块名
            try:
                # 取模块名最后一段作为短名，例如 "NXOpen_Features" -> "Features"
                ms = module_name.split("_")[-1]
                imp_mds[ms] = import_module(module_name)
            except Exception as e:
                # 导入失败时打印错误信息，但不中断整个流程
                print("error:", module_name, e)


# ===========================================================================
# 第二部分：定义所有节点类型的基类 pyibase
# ===========================================================================

class pyibase:
    """
    所有 NXOpen 反射节点的基类。

    NXOpen API 中的每种成员（模块、类、方法、属性等）都对应一个子类，
    它们继承自 pyibase，并实现各自的 toStr() 方法来生成 .pyi 代码。

    核心属性说明:
        name          : 成员名称
        doc           : 成员的文档字符串（__doc__）
        chdmdls       : 子模块字典  {名称: nxoModuleType}
        chdtps        : 子类型字典  {名称: nxoType / basetps}
        MdDescriptor  : 方法描述符字典  {名称: nxoMethodDescriptorType}
        GSDescriptor  : 属性描述符字典  {名称: nxoGetSetDescriptorType}
        unct          : 预留字典（当前未使用）
        nxc           : 类别名字典  {名称: nxoClsAliasType}
        mthdorbutin   : 内建函数/类方法字典  {名称: nxoBuiltinFunctionType}
        mberDescriptor: 成员变量描述符字典  {名称: nxoMemberDescriptorType}
        tpsinvoke     : 需要以赋值形式导入的类型  {名称: [模块路径, 类名]}
        nn            : 记录所有已处理的成员名列表（用于调试）
    """

    # 三个基础类型的名称，它们是 NXOpen 类体系的根基，需要特殊处理
    ecpts = [
        "NXObject",      # 所有 NX 对象的基类
        "TaggedObject",  # 带标签对象基类
        "INXObject",     # NX 对象接口基类
    ]

    def __init__(self) -> None:
        self.name: str = ""
        self.doc: Optional[str] = ""
        self.chdmdls: Dict = {}
        self.chdtps: Dict = {}
        self.MdDescriptor: Dict = {}
        self.GSDescriptor: Dict = {}
        self.unct: Dict = {}
        self.nxc: Dict[str, "nxoClsAliasType | pyibase"] = {}
        self.mthdorbutin: Dict = {}
        self.mberDescriptor: Dict = {}

        self.tpsinvoke: Dict[str, List] = {}
        self.nn: List[str] = []

    def dcts(self) -> Generator["pyibase", None, None]:
        """
        生成器方法：依次遍历所有成员字典中的值并 yield。

        用于在 toStr() 中统一遍历所有子成员，生成嵌套的 .pyi 代码。
        """
        for dc in [
            self.chdmdls,
            self.chdtps,
            self.MdDescriptor,
            self.GSDescriptor,
            self.unct,
            self.nxc,
            self.mthdorbutin,
            self.mberDescriptor,
        ]:
            for v in dc.values():
                yield v

    def addmember(self, m, dm: List[str] = None):
        """
        扫描对象 m 的所有公开成员（不以 "_" 开头的），根据类型分类存储。

        参数:
            m  : 要扫描的对象（模块、类等）
            dm : 需要排除的成员名列表（用于排除父类已有成员，避免重复声明）

        分类逻辑:
            - ModuleType          -> chdmdls（子模块）
            - type（类）          -> chdtps（子类型）或 tpsinvoke（别名导入）
            - MethodDescriptorType -> MdDescriptor（实例方法）
            - GetSetDescriptorType  -> GSDescriptor（属性）
            - MemberDescriptorType  -> mberDescriptor（成员变量）
            - BuiltinFunctionType   -> mthdorbutin（类方法/内建函数）
            - 其他 NXOpen 对象       -> nxc（类别名）
        """
        dirm = dir(m)
        if dm is not None:
            # 排除指定成员（通常是父类已声明的成员）
            dirm = [i for i in dirm if i not in dm]
        for i in dirm:
            if i == "GetSession":
                print(i)
            if not i.startswith("_"):
                att = getattr(m, i)
                self.nn.append(i)
                if isinstance(att, types.ModuleType):
                    # 成员是一个模块 -> 归入子模块字典
                    self.chdmdls[i] = nxoModuleType(att)
                elif isinstance(att, type):
                    # 成员是一个类
                    if i != att.__name__:
                        # 名称与类名不一致，说明是别名导入，记录其完整路径
                        self.tpsinvoke[i] = [att.__module__, att.__name__]
                    elif i not in pyibase.ecpts:
                        # 普通类，归入子类型字典
                        self.chdtps[i] = nxoType(att)
                elif isinstance(att, types.MethodDescriptorType):
                    # 实例方法描述符
                    self.MdDescriptor[i] = nxoMethodDescriptorType(att)
                elif isinstance(att, types.GetSetDescriptorType):
                    # 属性描述符（getter/setter）
                    self.GSDescriptor[i] = nxoGetSetDescriptorType(att)
                elif isinstance(att, types.MemberDescriptorType):
                    # 成员变量描述符
                    self.mberDescriptor[i] = nxoMemberDescriptorType(att)
                else:
                    _md = att.__class__.__module__
                    if "NXOpen" in str(_md):
                        # NXOpen 内部的类实例别名
                        self.nxc[i] = nxoClsAliasType(att, i)
                    elif i == "ValueOf":
                        # ValueOf 是特殊的工厂方法
                        self.mthdorbutin[i] = nxoBuiltinFunctionType(att)
                    elif isinstance(att, types.BuiltinFunctionType):
                        # 内建函数（通常是类方法）
                        self.mthdorbutin[i] = nxoBuiltinFunctionType(
                            att, cname=self.name
                        )
                    else:
                        assert TypeError(i, att, type(att))

    def docs(self, lv: int = 0, mx: int = 130):
        """
        生成成员的文档字符串（docstring），写入 .pyi 文件中。

        参数:
            lv: 缩进层级（每层对应一个 tab）
            mx: 每行最大字符数，用于自动换行

        输出格式:
            '''
            ### <类名>
            <文档内容（自动按 mx 宽度截断）>
            '''
        """
        dd = str(self.doc)
        dd = dd.strip()
        dd2 = dd.splitlines()
        dd2 = [i.strip() for i in dd2]

        ll = mx - lv * 4  # 计算每行可容纳的最大字符数
        yield (lv + 1) * "\t" + "'''"
        yield (lv + 1) * "\t" + f"### {self.__class__.__name__}"

        for i in dd2:
            # 按 ll 宽度对每行文档进行截断
            for k in range(0, len(i), ll):
                yield (lv + 1) * "\t" + i[k : min(len(i), k + ll)]
        yield (lv + 1) * "\t" + "'''"

    def toStr(self, lv: int = 0, mx: int = 130):
        """
        生成该节点的 .pyi 代码行（生成器）。基类默认实现仅输出名称标记。
        子类会重写此方法以生成具体的 Python 语法。
        """
        yield lv * "\t" + f"{self.name}:-->"


# ===========================================================================
# 第三部分：模块类型节点
# ===========================================================================

class nxoModuleType(pyibase):
    """
    表示一个 NXOpen 子模块（如 NXOpen.Features）。

    在 .pyi 中，子模块被表示为一个以模块名命名的类，其中包含
    该模块下的所有类、方法等成员。
    """

    def __init__(self, m: types.ModuleType) -> None:
        super().__init__()
        assert isinstance(m, types.ModuleType)
        self.doc = m.__doc__
        self.name = m.__name__.split(".")[-1]  # 取最后一段作为短名

        self.addmember(m)

    def toStr(self, lv: int = 0, mx: int = 130):
        """生成模块对应的 .pyi 代码：class <模块名>: ..."""
        yield lv * "\t" + f"class {self.name}:"
        for i in self.docs(lv):
            yield i
        # 遍历所有子成员并生成嵌套代码
        for dc in self.dcts():
            for i in dc.toStr(lv + 1):
                yield i
        # 以赋值方式导入的别名类型
        for i, v in self.tpsinvoke.items():
            _a = ".".join(v)
            yield "\t" + f"{i}={_a}"


# ===========================================================================
# 第四部分：基础类型节点（NXObject / TaggedObject / INXObject）
# ===========================================================================

class basetps(pyibase):
    """
    表示 NXOpen 的三个基础类型（NXObject, TaggedObject, INXObject）。

    这三个类型是整个 NXOpen 类体系的根基，需要手动指定继承关系：
        - TaggedObject(object)
        - INXObject(object)
        - NXObject(NXOpen.TaggedObject, NXOpen.INXObject)
    """

    def __init__(self, m: type, name="") -> None:
        super().__init__()
        assert name in pyibase.ecpts  # 确保只处理三个基础类型
        self.name = name
        self.doc = m.__doc__
        self.mo = type.mro(m)  # 方法解析顺序（MRO）
        self.addmember(m)

    def toStr(self, lv=0, mx=130):
        """根据基础类型名称生成对应的类声明及继承关系。"""
        if self.name in ["TaggedObject", "INXObject"]:
            yield lv * "\t" + f"class {self.name}(object):"
        elif self.name == "NXObject":
            # NXObject 同时继承 TaggedObject 和 INXObject
            yield lv * "\t" + f"class {self.name}(NXOpen.TaggedObject,NXOpen.INXObject):"
        else:
            yield lv * "\t" + f"class {self.name}(object):"
        for i in self.docs(lv):
            yield i
        for v in self.dcts():
            for ss in v.toStr(lv + 1):
                yield ss
        for i, v in self.tpsinvoke.items():
            _a = ".".join(v)
            yield lv * "\t" + "\t" + f"{i}={_a}"


# ===========================================================================
# 第五部分：普通类类型节点
# ===========================================================================

class nxoType(pyibase):
    """
    表示一个普通的 NXOpen 类（非基础类型）。

    会自动排除父类（MRO 中排第一位之后的所有类）已声明的成员，
    避免在子类中重复声明继承来的方法和属性。
    """

    def __init__(self, m: type) -> None:
        super().__init__()
        assert isinstance(m, type)
        self.doc = m.__doc__
        self.name = m.__name__
        self.mo = type.mro(m)      # 获取方法解析顺序
        self.sp = self.mo[1]       # 直接父类（MRO 中第二个元素）
        # 收集所有父类（MRO[1:]）的公开成员名，用于排除
        ll = []
        for k in self.mo[1:]:
            for s in dir(k):
                if not s.startswith("_"):
                    ll.append(s)
        # 扫描当前类成员时，排除父类已有成员
        self.addmember(m, ll)

    def toStr(self, lv=0, mx=130):
        """
        生成类的 .pyi 代码。

        继承关系通过 str(self.sp)[8:-2] 提取，例如:
            <class 'NXOpen.NXObject'> -> NXOpen.NXObject
        """
        yield lv * "\t" + f"class {self.name}({str(self.sp)[8:-2]}):"
        for i in self.docs(lv):
            yield i

        for v in self.dcts():
            for i in v.toStr(lv + 1):
                yield i
        for i, v in self.tpsinvoke.items():
            _a = ".".join(v)
            yield lv * "\t" + "\t" + f"{i}={_a}"


# ===========================================================================
# 第六部分：正则表达式 —— 从文档字符串中提取返回类型
# ===========================================================================

# 匹配 :rtype: :py:class:`XXX` 格式（Sphinx 风格的类引用）
pt1 = r":returns:[ \S]*[\n]?\s*:rtype: :py:class:`([\S]+)`"
p1 = re.compile(pt1)
# 匹配 :rtype: list of :py:class:`XXX` 格式（列表类型）
pt2 = r":returns:[ \S]*[\n]?\s*:rtype: list of :py:class:`([\S]+)`"
p2 = re.compile(pt2)
# 匹配 :rtype: XXX 格式（基本类型，如 int/str/float/bool）
pt3 = r":returns:[ \S]*[\n]?\s*:rtype: ([\S]+)"
p3 = re.compile(pt3)
# 匹配 :rtype: list of XXX 格式（基本类型列表）
pt4 = r":returns:[ \S]*[\n]?\s*:rtype: list of ([\S]+)"
p4 = re.compile(pt4)


def findrtype(ss: str):
    """
    从文档字符串中解析返回类型。

    依次尝试 4 种正则模式，按优先级匹配:
        1. :py:class:`XXX`  -> 返回 "XXX"
        2. list of :py:class:`XXX` -> 返回 "List[XXX]"
        3. 基本类型（int/str/float/bool）-> 返回该类型名
        4. list of 基本类型 -> 返回 "List[类型名]"

    如果无法匹配或类型不在允许范围内，返回空字符串。
    """
    rtp = ""
    # 模式1：Sphinx 类引用
    r = p1.search(ss)
    if r is not None:
        rtp = r.groups()[0]
    if rtp == "":
        # 模式2：列表类型的 Sphinx 类引用
        r = p2.search(ss)
        if r is not None:
            rtp = f"List[{r.groups()[0]}]"
    if rtp == "":
        # 模式3：基本类型
        r = p3.search(ss)
        if r is not None:
            rtp = r.groups()[0]
            if rtp not in ["int", "str", "float", "bool"]:
                rtp = ""
    if rtp == "":
        # 模式4：基本类型列表
        r = p4.search(ss)
        if r is not None:
            rtp = r.groups()[0]
            if rtp not in ["int", "str", "float", "bool"]:
                rtp = ""
            else:
                rtp = f"List[{rtp}]"
    return rtp


# ===========================================================================
# 第七部分：方法描述符节点
# ===========================================================================

class nxoMethodDescriptorType(pyibase):
    """
    表示一个实例方法（MethodDescriptorType）。

    生成 .pyi 时输出: def 方法名(self, *args, **kw) -> 返回类型: ...
    其中 Dispose 方法特殊处理，不接受可变参数。
    """

    def __init__(self, m: types.MethodDescriptorType) -> None:
        super().__init__()
        assert isinstance(m, types.MethodDescriptorType)
        self.doc = m.__doc__
        self.name = m.__name__

    def toStr(self, lv: int = 0, mx: int = 130):
        rtp = findrtype(str(self.doc))  # 解析返回类型

        if rtp == "":
            rr = ""
        else:
            rr = f"->{rtp}"
        if self.name == "Dispose":
            # Dispose 方法特殊处理：不接受可变参数
            yield lv * "\t" + f"def {self.name}(self){rr}:"
        else:
            yield lv * "\t" + f"def {self.name}(self,*args,**kw){rr}:"
        for i in self.docs(lv):
            yield i
        yield lv * "\t" + "\t" + "..."


# ===========================================================================
# 第八部分：属性描述符节点（getter/setter）
# ===========================================================================

class nxoGetSetDescriptorType(pyibase):
    """
    表示一个属性（GetSetDescriptorType），对应 @property 装饰器。

    生成 .pyi 时同时输出 getter 和 setter：
        @property
        def 属性名(self) -> 返回类型: ...
        @属性名.setter
        def 属性名(self, value: 返回类型): ...
    """

    def __init__(self, m: types.GetSetDescriptorType) -> None:
        super().__init__()
        assert isinstance(m, types.GetSetDescriptorType)
        self.doc = m.__doc__
        self.name = m.__name__

    def toStr(self, lv: int = 0, mx: int = 130):
        rtp = findrtype(str(self.doc))

        # getter 部分
        yield lv * "\t" + f"@property"
        if rtp == "":
            yield lv * "\t" + f"def {self.name}(self):"
        else:
            yield lv * "\t" + f"def {self.name}(self)->{rtp}:"
        for i in self.docs(lv):
            yield i
        yield lv * "\t" + "\t" + "..."

        # setter 部分
        yield lv * "\t" + f"@{self.name}.setter"
        if rtp == "":
            yield lv * "\t" + f"def {self.name}(self,value):..."
        else:
            yield lv * "\t" + f"def {self.name}(self,value:{rtp}):..."
        yield ""


# ===========================================================================
# 第九部分：成员变量描述符节点
# ===========================================================================

class nxoMemberDescriptorType(pyibase):
    """
    表示一个成员变量（MemberDescriptorType）。

    生成 .pyi 时输出: 变量名: 类型名 = ...
    """

    def __init__(self, m: types.MemberDescriptorType) -> None:
        super().__init__()
        assert isinstance(m, types.MemberDescriptorType)
        self.doc = m.__doc__
        self.name = m.__name__
        self._tp = type(m).__name__  # 描述符自身的类型名

    def toStr(self, lv: int = 0, mx: int = 130):
        yield lv * "\t" + f"{self.name}:{self._tp}=..."
        for i in self.docs(lv):
            yield i


# ===========================================================================
# 第十部分：内建函数/类方法节点
# ===========================================================================

class nxoBuiltinFunctionType(pyibase):
    """
    表示一个内建函数（BuiltinFunctionType），通常是类方法或静态方法。

    生成 .pyi 时输出 @classmethod 装饰的方法签名。

    特殊处理:
        - ValueOf 方法：参数固定为 (cls, value: int)
        - Get<类名> 工厂方法：返回类型推断为对应的类
        - 其他方法：返回类型从文档字符串解析，无则省略
    """

    def __init__(
        self, m: "types.MemberDescriptorType |types.BuiltinMethodType", cname=""
    ) -> None:
        super().__init__()
        assert isinstance(m, types.BuiltinFunctionType) and isinstance(
            m, types.BuiltinMethodType
        )
        self.doc = m.__doc__
        self.name = m.__name__
        self.cname = cname  # 所属类名，用于推断 Get 工厂方法的返回类型

    def toStr(self, lv: int = 0, mx: int = 130):
        rtp = findrtype(str(self.doc))
        yield lv * "\t" + f"@classmethod"
        if self.name == "ValueOf":
            # ValueOf 方法：固定参数为 (cls, value: int)
            yield lv * "\t" + f"def {self.name}(cls,value:int):"
        elif rtp != "":
            # 文档字符串中能解析出返回类型
            yield lv * "\t" + f"def {self.name}(cls,*args,**kw)->{rtp}:"
        elif self.cname != "" and self.name == "Get" + self.cname:
            # Get<类名> 是工厂方法，返回类型为对应类
            if hasattr(NXOpen, self.cname):
                yield lv * "\t" + f"def {self.name}(cls,*args,**kw)->NXOpen.{self.cname}:"
            else:
                yield lv * "\t" + f"def {self.name}(cls,*args,**kw)->{self.cname}:"
        else:
            # 无法确定返回类型
            yield lv * "\t" + f"def {self.name}(cls,*args,**kw):"
        for i in self.docs(lv):
            yield i
        yield lv * "\t" + "\t" + "..."


# ===========================================================================
# 第十一部分：类别名节点
# ===========================================================================

class nxoClsAliasType(pyibase):
    """
    表示一个 NXOpen 内部的类别名实例（非 type，而是某个类的实例）。

    当模块成员既不是模块也不是类，但其所属模块属于 NXOpen 时，
    将其作为类别名处理。生成 .pyi 时输出: 名称: 类型 = ...
    """

    def __init__(self, m, name="") -> None:
        super().__init__()
        _md = m.__class__.__module__
        assert "NXOpen" in str(_md)
        self.doc = m.__doc__
        self.name = m.__name__ if hasattr(m, "__name__") else name
        self.attp = str(m.__class__.__name__)  # 实际类名
        self.body = m

    def toStr(self, lv=0, mx=130):
        nn = self.attp
        if hasattr(NXOpen, nn):
            att = getattr(NXOpen, nn)
            if isinstance(att, type):
                # 如果 NXOpen 中存在同名类，使用 "NXOpen.类名" 格式
                nn = f"NXOpen.{nn}"
        else:
            # 否则使用完整路径 "模块.类名"
            nn = self.body.__class__.__module__ + "." + self.body.__class__.__name__
        if self.name == "KeyPerformanceInterface":
            print(self.name, f"{self.name}:{nn}=...")
        yield lv * "\t" + f"{self.name}:{nn}=..."
        for i in self.docs(lv - 1):
            yield i


# ===========================================================================
# 第十二部分：顶层入口 —— mainModules
# ===========================================================================

class mainModules(pyibase):
    """
    顶层入口类，负责扫描整个 NXOpen 主模块及所有子模块，
    并将结果写入 .pyi 文件。

    工作流程:
        1. 扫描 NXOpen 主模块的所有成员
        2. 为三个基础类型创建 basetps 节点
        3. 为所有已导入的子模块创建 nxoModuleType 节点
        4. 调用 pyi() 方法将结果写入磁盘
    """

    def __init__(
        self,
    ) -> None:
        super().__init__()
        m = NXOpen
        self.doc = m.__doc__
        self.name = m.__name__
        self.addmember(m)
        # 为三个基础类型创建特殊节点
        for i in pyibase.ecpts:
            self.chdtps[i] = basetps(getattr(NXOpen, i), i)
        # 为所有子模块创建节点
        for k, v in imp_mds.items():
            self.chdmdls[k] = nxoModuleType(v)

    def pyi(self):
        """
        将所有扫描结果写入 .pyi 存根文件。

        输出文件结构:
            ./NXOpen/__init__.py       — 包初始化，导入所有子模块
            ./NXOpen/_nxopen.pyi       — 主存根，导入所有类
            ./NXOpen/<模块名>.pyi      — 各子模块存根
            ./NXOpen/clss/<类名>.pyi   — 各类单独存根
        """
        mm = self
        # 创建输出目录
        if not os.path.exists("./NXOpen/"):
            os.mkdir("./NXOpen")

        if not os.path.exists("./NXOpen/clss/"):
            os.mkdir("./NXOpen/clss/")

        p11 = "./NXOpen/"
        p22 = os.path.join(p11, "clss/")

        # 写入包初始化文件 __init__.py
        with open(os.path.join(p11, "__init__.py"), "w", encoding="utf8") as f:
            m: nxoModuleType
            # 遍历所有子模块，为每个模块生成独立的 .pyi 文件
            for v in mm.chdmdls.values():
                m = v
                mn = m.name.split(".")[-1]
                mName = mn + ".pyi"
                with open(os.path.join(p11, mName), "w") as f2:
                    f2.write("import NXOpen\n")
                    f2.write("from typing import List\n")
                    for _s in m.toStr():
                        f2.write(_s + "\n")

                # 在 __init__.py 中添加导入语句
                f.write(f"from .{mn} import {mn} as {mn}" + "\n")
            f.write(f"from ._nxopen import *\n")

            # 写入主存根文件 _nxopen.pyi，并生成各类的独立文件
            with open(os.path.join(p11, "_nxopen.pyi"), "w", encoding="utf8") as f2:
                m2: nxoType
                f2.write("import NXOpen\n")
                f2.write("from typing import List\n")

                for k, v in mm.chdtps.items():
                    m2 = v
                    nn = m2.name
                    # 在 _nxopen.pyi 中添加导入语句
                    f2.write(f"from .clss.{nn} import {nn} as {nn}" + "\n")
                    # 为每个类生成独立的存根文件
                    with open(
                        os.path.join(p22, f"{nn}.pyi"), "w", encoding="utf8"
                    ) as f3:
                        f3.write("import NXOpen\n")
                        f3.write("from typing import List\n")
                        for _s in m2.toStr():
                            f3.write(f"{_s}\n")


# ===========================================================================
# 程序入口
# ===========================================================================

if __name__ == "__main__":

    def main():
        """程序主入口：创建 mainModules 实例并执行 .pyi 文件生成。"""
        mainModules().pyi()

    main()
