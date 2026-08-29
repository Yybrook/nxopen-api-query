# -*- coding: utf-8 -*-
"""
批量解析 NXOpen 目录下所有 .pyi 类型存根文件。
提取 模块 → 类 → 方法 的层级结构，并保留完整的方法详情：
  - 描述（description）
  - 签名（signature）
  - 参数（params：名称、描述、类型）
  - 返回值（returns：描述、类型）
  - 版本信息（version info）
  - 许可证要求（license）

用法:
    python parse_pyi.py --source <path_to_NXOpen_folder> [--output PATH]

参数:
    --source PATH    (必填) NXOpen 文件夹的完整路径，由用户提供
    --output PATH    (可选) 输出 JSON 路径，默认为项目 data/ 目录下的 nxopen_structure.json
                     解析完成后自动压缩为 .json.gz 并删除原始 JSON 文件

注:
    --source 为必填参数，每次运行时由用户指定 NXOpen 文件夹路径，不设默认值。
    若用户无法提供 NXOpen 文件夹，请联系项目作者。

NXOpen 文件夹说明:
    NXOpen 文件夹是 Siemens NXOpen Python API 的类型存根（.pyi）目录。
    通常随 NXOpen Python API 安装包一起发布，或从 NX 安装目录下获取。

    所需内容（缺一不可）:
    1. 顶层 .pyi 文件: 每个文件代表一个 NXOpen 功能模块
       例: NXOpen.pyi, UF.pyi, CAM.pyi, CAE.pyi, Features.pyi, Drawings.pyi ...
       命名规则: <模块名>.pyi（如 CAE.pyi、CAM.pyi）
       其中 _nxopen.pyi 和 __init__.py 是辅助文件，解析时会自动跳过

    2. clss/ 子目录: 每个文件对应一个类的存根
       命名规则: clss/<类名>.pyi（如 clss/Body.pyi）
       这些类文件会被合并解析，按继承关系归入对应顶层模块

    典型目录结构:
        <NXOpen>/
        ├── AECDesign.pyi          ← 顶层模块存根
        ├── AME.pyi
        ├── Annotations.pyi
        ├── ...
        ├── UF.pyi
        ├── UIStyler.pyi
        ├── _nxopen.pyi            ← 辅助文件（自动跳过）
        ├── __init__.py             ← 辅助文件（自动跳过）
        └── clss/                  ← 类存根子目录
            ├── Body.pyi
            ├── Edge.pyi
            ├── Face.pyi
            └── ...

"""
import os
import ast
import json
import re
import sys
import time

# 脚本所在目录
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 项目根目录（scripts 的父目录）
_ROOT_DIR = os.path.dirname(_SCRIPT_DIR)
# 默认输出路径：项目 data/ 目录下的 nxopen_structure.json（压缩为 .gz）
OUTPUT_JSON = os.path.join(_ROOT_DIR, "data", "nxopen_structure.json")
# 压缩输出路径（.gz 文件体积小，可保留在仓库中）
OUTPUT_GZ = OUTPUT_JSON + ".gz"

# ── 预编译高频正则（性能优化）──
_RE_HYPERLINK = re.compile(r'`([^`<]+)\s*<[^>]+>`\w*')
_RE_PY_ROLE_LINK = re.compile(r':py:(?:class|meth|attr|func|mod|data|const|exc|obj):`([^<`]+)<[^>`]+>`')
_RE_PY_ROLE = re.compile(r':py:(?:class|meth|attr|func|mod|data|const|exc|obj):`([^`]+)`')
_RE_ROLE_LINK = re.compile(r':(?:class|meth|attr|func|mod|data|const|exc|obj):`([^<`]+)<[^>`]+>`')
_RE_ROLE = re.compile(r':(?:class|meth|attr|func|mod|data|const|exc|obj):`([^`]+)`')
_RE_DOUBLE_BT = re.compile(r'``([^`]+)``')
_RE_SINGLE_BT = re.compile(r'(?<!\w)`([^`]+)`(?!\w*\()')
_RE_WS = re.compile(r'\s+')
_RE_SIG_SIGNATURE = re.compile(r'Signature\s*:?\s*``([^`]+)``')
_RE_FIRST_BT = re.compile(r'``([^`]+)``')
_RE_SIG_NAME = re.compile(r'^[A-Za-z_]\w*$')
_RE_PARAM = re.compile(r':param\s+(\w+):\s*(.*)')
_RE_TYPE = re.compile(r':type\s+(\w+):\s*(.*)')
_RE_RETURNS = re.compile(r':returns:\s*(.*)')
_RE_RTYPE = re.compile(r':rtype:\s*(.*)')
_RE_RET_COMP_COLON = re.compile(r'(\w+)\s*\(`([^`]+)`\)\s*:\s*(.+)')
_RE_RET_COMP_NOCOLON = re.compile(r'(\w+)\s*\(`([^`]+)`\)\s+(.+)')
_RE_VERSIONADDED = re.compile(r'\.\.\s+versionadded::\s*(.+?)$', re.MULTILINE)
_RE_VERSIONCHANGED = re.compile(r'\.\.\s+versionchanged::\s*(.+?)$', re.MULTILINE)
_RE_DEPRECATED = re.compile(r'\.\.\s+deprecated::\s*(.+?)$', re.MULTILINE)
_RE_LICENSE = re.compile(r'License requirements:\s*(.+?)$', re.MULTILINE)
_RE_PRE_MARKERS = [r':param\s', r':type\s', r':returns:', r':rtype:', r'\.\.\s+version', r'License\s+requirements']


def _clean_rst(text):
    """清理文本中的 RST 标记，保留纯可读文本。"""
    if not text:
        return ""
    # RST 超链接：`text <url>`_ -> text（必须在通用反引号清理之前处理）
    text = _RE_HYPERLINK.sub(r'\1', text)
    # :py:class:`...`、:py:meth:`...` 等带可选 <link> 的形式
    text = _RE_PY_ROLE_LINK.sub(r'\1', text)
    text = _RE_PY_ROLE.sub(r'\1', text)
    # :class:`...`、:meth:`...` 等带可选 <link> 的形式
    text = _RE_ROLE_LINK.sub(r'\1', text)
    text = _RE_ROLE.sub(r'\1', text)
    # 双反引号代码：``code`` -> code
    text = _RE_DOUBLE_BT.sub(r'\1', text)
    # 单反引号：`text` -> text（但不处理类型注解中的反引号）
    text = _RE_SINGLE_BT.sub(r'\1', text)
    # 折叠多余空白
    text = _RE_WS.sub(' ', text).strip()
    return text


def clean_doc(docstr):
    """从 docstring 中提取简洁的描述摘要。"""
    if not docstr:
        return ""
    lines = docstr.strip().splitlines()
    desc_lines = []  # 描述行收集列表
    started = False   # 是否已开始收集正文描述
    for line in lines:
        stripped = line.strip()
        # 跳过 NXOpen 自动生成的标记行（如 ### nxoMethodDescriptorType）
        if stripped.startswith("### nxo"):
            continue
        # 遇到以下标记即停止收集描述（这些属于结构化字段，由 parse_method_doc 处理）
        if stripped.startswith("Signature"):
            break
        if stripped.startswith(":param"):
            break
        if stripped.startswith(":type"):
            break
        if stripped.startswith(":returns"):
            break
        if stripped.startswith(":rtype"):
            break
        if stripped.startswith(".. version"):
            break
        if stripped.startswith(".. deprecated"):
            break
        if stripped.startswith("License requirements"):
            break
        if stripped.startswith("``---"):
            break
        if stripped.startswith(".. csv-table"):
            break
        # 空行：若已开始收集正文，则视为描述结束；否则跳过前导空行
        if stripped == "":
            if started:
                break
            continue
        started = True
        desc_lines.append(stripped)
    # 合并所有描述行并清理 RST 标记
    result = " ".join(desc_lines)
    result = _clean_rst(result)
    # 截断到 500 字符以控制体积
    return result[:500]


def _parse_return_component(line):
    """解析返回值元组的单个组成项。
    形式 A：point(`list of float`):  Point on curve (3 element array).
    形式 B：name is a type.（散文式描述，不作为组成项解析）
    返回 (name, type, desc) 三元组；若不是组成项则返回 None。
    """
    line = line.strip()
    # 形式 A：name(`type`):  description（带冒号）
    m = _RE_RET_COMP_COLON.match(line)
    if m:
        return (m.group(1), m.group(2).strip(), _clean_rst(m.group(3).strip()))
    # 形式 A2：name(`type`)  description（无冒号）
    m = _RE_RET_COMP_NOCOLON.match(line)
    if m:
        return (m.group(1), m.group(2).strip(), _clean_rst(m.group(3).strip()))
    return None


def parse_method_doc(docstr):
    """使用状态机解析器从 docstring 中提取完整的方法信息。"""
    info = {
        "desc": "",               # 方法描述
        "sig": "",                 # 方法签名
        "params": [],              # 参数列表 [{name, desc, type}]
        "returns": "",             # 返回值描述
        "rtype": "",               # 返回值类型
        "return_components": [],   # 返回值元组组成项 [{name, type, desc}]
        "version": "",             # 版本信息
        "license": "",             # 许可证要求
    }
    if not docstr:
        return info

    # 1. 提取描述摘要
    info["desc"] = clean_doc(docstr)

    # 2. 提取签名：优先匹配 Signature 标记后的双反引号内容（Bug B 修复）
    #    兼容两种写法："Signature ``...``" 和 "Signature:\n``...``"
    m = _RE_SIG_SIGNATURE.search(docstr)
    if not m:
        # 回退：查找第一对双反引号包裹的内容（兼容无 Signature 标记的情况）
        m = _RE_FIRST_BT.search(docstr)
    if m:
        candidate = m.group(1).strip()
        # 判断是否像签名（含括号，或是单个属性名）
        if '(' in candidate or _RE_SIG_NAME.match(candidate):
            # 清理签名中的换行符：make_pyi.py 的 docs() 按 130 字符截断长行，
            # 可能将 ``Signature ``...`` `` 切到两行，导致签名残留 \n。
            # 用 _RE_WS 将所有空白（含换行）折叠为单个空格。
            info["sig"] = _RE_WS.sub(' ', candidate).strip()

    # 3. 预处理：将行内的字段标记前插入换行，以兼容单行紧凑写法的 docstring
    processed = docstr
    for marker in _RE_PRE_MARKERS:
        processed = re.sub(r'(?<!\n)\s+(' + marker + r')', r'\n\1', processed)

    # 状态机变量：用于解析 params / returns / rtype
    param_descs = {}      # 参数名 -> 描述
    param_types = {}      # 参数名 -> 类型
    param_order = []      # 参数名出现顺序
    returns_lines = []    # 返回值描述的累积行
    rtype_lines = []      # 返回值类型的累积行
    return_components = []  # 返回值元组组成项

    # 状态：'desc'（描述）、'param'（参数）、'returns'（返回描述）、'rtype'（返回类型）、'version'（版本）、'done'（结束）
    state = 'desc'
    current_param = None       # 当前正在解析的参数名
    current_desc_lines = []   # 当前参数描述的累积行

    def finalize_param():
        """结束当前参数的解析，保存其描述。"""
        nonlocal current_param, current_desc_lines
        if current_param:
            param_descs[current_param] = _clean_rst(' '.join(current_desc_lines))[:300]
        current_param = None
        current_desc_lines = []

    def finalize_returns():
        """结束返回值描述的解析。"""
        nonlocal returns_lines
        if returns_lines:
            info["returns"] = _clean_rst(' '.join(returns_lines))[:300]

    def finalize_rtype():
        """结束返回值类型的解析，并尝试从中提取元组组成项。"""
        nonlocal rtype_lines, return_components
        if rtype_lines:
            # 第一行作为主返回类型
            info["rtype"] = _clean_rst(rtype_lines[0])[:200]
            # 检查后续行是否为返回值元组组成项
            for line in rtype_lines[1:]:
                comp = _parse_return_component(line)
                if comp:
                    return_components.append({
                        "name": comp[0],
                        "type": comp[1],
                        "desc": comp[2][:200],
                    })
                else:
                    # 散文式续行——追加到返回类型字符串
                    info["rtype"] = _clean_rst(info["rtype"] + ' ' + line)[:300]
        rtype_lines = []

    # 逐行扫描 docstring，根据标记切换状态
    for line in processed.splitlines():
        stripped = line.strip()

        # 空行：在续行状态下保守处理（可能为字段结束或行内空行）
        if not stripped:
            if state in ('param', 'returns', 'rtype') and current_desc_lines:
                pass
            continue

        # 检测各类标记并切换状态 ↓

        # :param name: desc —— 参数描述
        m = _RE_PARAM.match(stripped)
        if m:
            finalize_param()
            finalize_returns()
            finalize_rtype()
            state = 'param'
            current_param = m.group(1)
            if current_param not in param_order:
                param_order.append(current_param)
            current_desc_lines = [m.group(2).strip()] if m.group(2).strip() else []
            continue

        # :type name: type —— 参数类型
        m = _RE_TYPE.match(stripped)
        if m:
            finalize_param()
            state = 'type'
            pname = m.group(1)
            param_types[pname] = _clean_rst(m.group(2).strip())[:100]
            current_param = None
            continue

        # :returns: desc —— 返回值描述
        m = _RE_RETURNS.match(stripped)
        if m:
            finalize_param()
            finalize_rtype()
            state = 'returns'
            returns_lines = [m.group(1).strip()] if m.group(1).strip() else []
            continue

        # :rtype: desc —— 返回值类型
        m = _RE_RTYPE.match(stripped)
        if m:
            finalize_param()
            finalize_returns()
            state = 'rtype'
            rtype_lines = [m.group(1).strip()] if m.group(1).strip() else []
            continue

        # .. versionadded / .. deprecated —— 版本信息（遇到即结束结构化字段解析）
        if stripped.startswith('.. version') or stripped.startswith('.. deprecated'):
            finalize_param()
            finalize_returns()
            finalize_rtype()
            state = 'version'
            break

        # License requirements —— 许可证要求（遇到即结束）
        if stripped.startswith('License requirements'):
            finalize_param()
            finalize_returns()
            finalize_rtype()
            state = 'done'
            break

        # 正文中的签名行（双反引号包裹）—— 跳过
        if stripped.startswith('``') and '``' in stripped[2:]:
            continue  # 跳过正文中的签名行

        # 续行处理：根据当前状态累积到对应字段
        if state == 'param' and current_param:
            current_desc_lines.append(stripped)
        elif state == 'returns':
            returns_lines.append(stripped)
        elif state == 'rtype':
            rtype_lines.append(stripped)
        # 其他情况：忽略（属于已提取的描述部分）

    # 最后收尾：保存尚未 finalize 的字段
    finalize_param()
    finalize_returns()
    finalize_rtype()

    # 按签名顺序构建参数列表（签名中出现的参数优先，再补充仅在 docstring 中出现的参数）
    sig_param_order = []
    if info["sig"] and '(' in info["sig"]:
        # Bug E 修复：用 split('(',1)[1].rsplit(')',1)[0] 精确截取括号内参数段
        # 旧写法 split('(')[-1].rstrip(')') 会混入返回类型（如 "-> Body"）
        sig_params = re.findall(r'(\w+)', info["sig"].split('(', 1)[1].rsplit(')', 1)[0])
        sig_param_order = sig_params
    for pname in param_order:
        if pname not in sig_param_order:
            sig_param_order.append(pname)

    for pname in sig_param_order:
        if pname in param_descs or pname in param_types:
            info["params"].append({
                "name": pname,
                "desc": param_descs.get(pname, ""),
                "type": param_types.get(pname, ""),
            })

    info["return_components"] = return_components

    # 版本信息：优先 versionadded，叠加 versionchanged / deprecated
    m = _RE_VERSIONADDED.search(docstr)
    if m:
        info["version"] = m.group(1).strip()
    m = _RE_VERSIONCHANGED.search(docstr)
    if m:
        info["version"] = (info["version"] + " (changed " + m.group(1).strip() + ")").strip()
    m = _RE_DEPRECATED.search(docstr)
    if m:
        info["version"] = ("deprecated " + m.group(1).strip() + " " + info["version"]).strip()

    # 许可证要求（Bug G 修复：license 现在会被写入输出字典）
    m = _RE_LICENSE.search(docstr)
    if m:
        info["license"] = m.group(1).strip()

    return info


def _get_name(node):
    """递归获取 AST 节点的完整名称（支持 Name / Attribute / Subscript）。"""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return _get_name(node.value) + "." + node.attr
    elif isinstance(node, ast.Subscript):
        return _get_name(node.value)
    return ""


# 是否支持 ast.unparse（Python 3.9+），循环外判断一次即可
_HAS_UNPARSE = hasattr(ast, 'unparse')


def _get_bases(node):
    """获取类的所有基类名称列表。优先用 ast.unparse，失败时回退到 _get_name。"""
    bases = []
    for b in node.bases:
        if _HAS_UNPARSE:
            try:
                bases.append(ast.unparse(b))
            except Exception:
                bases.append(_get_name(b))
        else:
            bases.append(_get_name(b))
    return bases


# 枚举内置方法名集合（解析枚举时忽略这些方法）
_ENUM_BUILTIN_METHODS = frozenset({"ValueOf"})


def _is_enum(node):
    """启发式判断一个类是否为枚举。
    规则：
      1. 基类名含 "Enum" 直接判定为枚举；
      2. 统计类体中的赋值/方法/其他节点数量：
         - 忽略 ValueOf 等枚举内置方法（Bug A 修复）；
         - Expr（docstring）节点不计入"其他"节点数（Bug A 修复）；
         - 含真实方法（非内置）的类不是枚举（防止 UF.UF.Curve 等含类型别名赋值的类被误判）；
         - 赋值 > 3 且「其他」节点 ≤ 2 判定为枚举；
      3. 其余情况不判为枚举。
    """
    # 规则1：显式继承 Enum
    for base in node.bases:
        bn = _get_name(base)
        if "Enum" in bn:
            return True
    # 规则2：统计类体节点
    assign_count = 0   # 赋值节点数（含 AnnAssign）
    other_count = 0    # 其他节点数（不含 Expr docstring）
    func_count = 0     # 真实方法定义数（排除内置方法）
    for m in node.body:
        if isinstance(m, (ast.Assign, ast.AnnAssign)):
            assign_count += 1
        elif isinstance(m, ast.ClassDef):
            pass
        elif isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 忽略枚举内置方法（如 ValueOf）
            if m.name in _ENUM_BUILTIN_METHODS:
                continue
            func_count += 1
        elif isinstance(m, ast.Expr):
            # docstring/注释表达式不计入 other（每个枚举成员后都有 docstring）
            continue
        else:
            other_count += 1
    # 含真实方法的类不是枚举（例如 UF.UF.Curve 有 124 个方法 + 47 个类型别名赋值）
    if func_count > 0:
        return False
    # 赋值多、其他节点少 → 判定为枚举
    if assign_count > 3 and other_count <= 2:
        return True
    return False


def parse_class(node):
    """递归解析一个 ClassDef 节点，区分方法/属性/嵌套类/嵌套枚举。"""
    cls_info = {
        "name": node.name,                # 类名
        "doc": clean_doc(ast.get_docstring(node)),  # 类描述
        "bases": _get_bases(node),        # 基类列表
        "methods": [],                    # 方法列表
        "properties": [],                 # 属性列表
        "nested_classes": [],             # 嵌套类列表
        "nested_enums": [],               # 嵌套枚举列表
    }
    for member in node.body:
        # 成员为函数定义（方法或属性）
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 判断是否为 @property 属性
            is_prop = any(isinstance(d, ast.Name) and d.id == 'property' for d in member.decorator_list)
            # 判断是否为 @xxx.setter
            is_setter = any(isinstance(d, ast.Attribute) and d.attr == 'setter' for d in member.decorator_list)
            if is_prop:
                # 属性：解析其 docstring 并归入 properties
                prop_doc = ast.get_docstring(member)
                pi = parse_method_doc(prop_doc)
                cls_info["properties"].append({
                    "name": member.name,
                    "desc": pi["desc"],
                    "sig": pi["sig"],
                    "rtype": pi["rtype"],
                    "returns": pi["returns"],
                    "return_components": pi.get("return_components", []),
                    "params": pi["params"],
                    "version": pi["version"],       # Bug D 修复：属性补 version 字段
                    "license": pi["license"],       # Bug G 修复：属性补 license 字段
                })
            elif is_setter:
                # setter 不单独记录（属性以 getter 为准）
                pass
            else:
                # 普通方法：解析 docstring 并归入 methods
                method_doc = ast.get_docstring(member)
                mi = parse_method_doc(method_doc)
                cls_info["methods"].append({
                    "name": member.name,
                    "desc": mi["desc"],
                    "sig": mi["sig"],
                    "params": mi["params"],
                    "returns": mi["returns"],
                    "rtype": mi["rtype"],
                    "return_components": mi.get("return_components", []),
                    "version": mi["version"],
                    "license": mi["license"],       # Bug G 修复：方法补 license 字段
                })
        # 成员为嵌套类
        elif isinstance(member, ast.ClassDef):
            nested = parse_class(member)
            if _is_enum(member):
                cls_info["nested_enums"].append(nested)
            else:
                cls_info["nested_classes"].append(nested)
    return cls_info


def parse_pyi(filepath, module_name):
    """解析单个 .pyi 文件，返回模块结构字典。"""
    result = {
        "name": module_name,           # 模块名
        "file": os.path.basename(filepath),  # 文件名
        "doc": "",                     # 模块描述
        "classes": [],                 # 类列表
        "enums": [],                   # 枚举列表
        "functions": [],               # 模块级函数列表
    }
    # 读取文件内容（utf-8，遇错误字符替换）
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception:
        return result
    # 解析为 AST
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return result

    # 提取模块级 docstring（Bug H 修复：移除已废弃的 ast.Str，仅用 ast.Constant）
    if (tree.body and isinstance(tree.body[0], ast.Expr) and
            isinstance(tree.body[0].value, ast.Constant)):
        result["doc"] = clean_doc(tree.body[0].value.value)

    # 遍历模块顶层节点：类定义 / 函数定义
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            cls_info = parse_class(node)
            if _is_enum(node):
                result["enums"].append(cls_info)
            else:
                result["classes"].append(cls_info)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_doc = ast.get_docstring(node)
            mi = parse_method_doc(fn_doc)
            result["functions"].append({
                "name": node.name,
                "desc": mi["desc"],
                "sig": mi["sig"],
                "params": mi["params"],
                "returns": mi["returns"],
                "rtype": mi["rtype"],
                "license": mi["license"],       # Bug G 修复：函数补 license 字段
            })
    return result


def main(source_dir):
    """主入口：扫描并解析指定 NXOpen 目录下所有 .pyi 文件，输出为 JSON。"""
    # 校验源目录是否存在
    if not os.path.isdir(source_dir):
        print(f"ERROR: NXOpen 文件夹不存在: {source_dir}")
        print("请通过 --source 参数提供有效的 NXOpen 文件夹路径。")
        print("若无法提供该文件夹，请联系项目作者。")
        sys.exit(1)
    print(f"Scanning {source_dir} ...")  # 扫描目录...
    # 收集所有 .pyi 文件及其模块名
    all_files = []
    for root, dirs, files in os.walk(source_dir):
        for f in files:
            if f.endswith(".pyi"):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, source_dir)
                mod_name = f.replace(".pyi", "")
                # 若文件位于子目录（如 clss/），则模块名带子目录前缀
                if os.sep in rel:
                    subdir = os.path.dirname(rel).replace(os.sep, ".")
                    mod_name = subdir + "." + f.replace(".pyi", "")
                all_files.append((full, mod_name, rel))  # 保存 rel 避免重复计算

    print(f"Found {len(all_files)} .pyi files")  # 找到 N 个 .pyi 文件
    start = time.time()

    # 按位置将文件分为顶层模块文件和 clss/ 子目录的类存根文件
    # Bug F 修复：用 "clss" + os.sep 精确匹配 clss/ 子目录，避免误匹配 clssXXX.pyi
    clss_prefix = "clss" + os.sep
    top_level = []
    clss_files = []
    for filepath, mod_name, rel in all_files:
        if rel.startswith(clss_prefix):
            clss_files.append((filepath, mod_name))
        else:
            top_level.append((filepath, mod_name))

    # 按模块名排序，保证输出稳定
    top_level.sort(key=lambda x: x[1])
    clss_files.sort(key=lambda x: x[1])

    all_modules = []

    # 解析顶层模块文件
    print(f"Parsing {len(top_level)} top-level modules...")  # 解析 N 个顶层模块...
    for i, (filepath, mod_name) in enumerate(top_level):
        result = parse_pyi(filepath, mod_name)
        all_modules.append(result)
        # 每 10 个打印一次进度
        if (i + 1) % 10 == 0:
            print(f"  Top-level: {i+1}/{len(top_level)} ({time.time()-start:.1f}s)")

    # 解析 clss/ 子目录的类存根文件
    print(f"Parsing {len(clss_files)} class files...")  # 解析 N 个类文件...
    for i, (filepath, mod_name) in enumerate(clss_files):
        result = parse_pyi(filepath, mod_name)
        all_modules.append(result)
        # 每 200 个打印一次进度
        if (i + 1) % 200 == 0:
            print(f"  clss: {i+1}/{len(clss_files)} ({time.time()-start:.1f}s)")

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")  # 完成，耗时 N 秒

    # 统计解析结果
    total_classes = 0
    total_methods = 0
    total_enums = 0
    total_functions = 0

    def count_class(c):
        """递归统计类及其嵌套类的数量与方法数。"""
        nonlocal total_classes, total_methods
        total_classes += 1
        total_methods += len(c["methods"]) + len(c["properties"])
        for nc in c["nested_classes"]:
            count_class(nc)
        for ne in c["nested_enums"]:
            count_class(ne)

    for m in all_modules:
        total_enums += len(m["enums"])
        total_functions += len(m["functions"])
        for c in m["classes"]:
            count_class(c)

    # 打印统计信息
    print(f"Stats: {len(all_modules)} modules, {total_classes} classes, {total_enums} enums, {total_methods} methods, {total_functions} functions")

    # 写入 JSON 文件（不转义非 ASCII，缩进 1 空格）
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_modules, f, ensure_ascii=False, indent=1)
    print(f"Written to {OUTPUT_JSON}")  # 已写入
    print(f"JSON size: {os.path.getsize(OUTPUT_JSON) / 1024 / 1024:.1f} MB")  # JSON 体积

    # 压缩为 .gz 并删除原始 JSON（压缩文件体积小，可保留在仓库中）
    from compress import compress_file
    compress_file(OUTPUT_JSON, OUTPUT_GZ)
    os.remove(OUTPUT_JSON)
    print(f"Removed {OUTPUT_JSON} (已压缩为 {OUTPUT_GZ})")


def _get_arg(name):
    """安全获取命令行参数值，返回 None 表示参数缺失或越界。"""
    if name not in sys.argv:
        return None
    idx = sys.argv.index(name)
    if idx + 1 >= len(sys.argv):
        return None
    return sys.argv[idx + 1]


if __name__ == "__main__":
    # 命令行参数解析：--source 为必填
    source_dir = _get_arg("--source")
    if source_dir is None:
        print("ERROR: 缺少必填参数 --source 或参数值缺失")
        print("用法: python parse_pyi.py --source <path_to_NXOpen_folder> [--output PATH]")
        print("请提供 NXOpen 文件夹的完整路径（详见文件头注释中的'NXOpen 文件夹说明'）。")
        print("若无法提供该文件夹，请联系项目作者。")
        sys.exit(1)
    # --output 为可选，覆盖默认输出路径
    output_val = _get_arg("--output")
    if output_val is not None:
        OUTPUT_JSON = output_val
    main(source_dir)
