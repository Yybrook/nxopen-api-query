# -*- coding: utf-8 -*-
"""
gen_js.py — 中间 JSON → 精简 JS 数据生成脚本

功能概述:
    读取 parse_pyi.py 生成的压缩中间 JSON（nxopen_structure.json.gz），
    展平嵌套类、合并 clss/ 类、解析继承关系、按功能域分组，
    输出精简的前端 JS 数据文件（nxopen_data.js）到 data/ 目录。

数据管线:
    nxopen_structure.json.gz ──gen_js.py──▶ data/nxopen_data.js
    (压缩中间JSON,~3.5MB)      (精简+分组+继承)  (精简JS,~24.9MB)

用法:
    python scripts/gen_js.py

输入/输出路径基于项目根目录（本脚本的父目录的父目录）自动定位。

功能域映射表在 scripts/domains.py 中维护，修改模块归属请编辑该文件。
"""
import json
import os
import sys

# ── 路径常量（基于项目根目录定位）──
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(_ROOT, "data", "nxopen_structure.json.gz")
OUTPUT = os.path.join(_ROOT, "data", "nxopen_data.js")

# ── 导入功能域映射表 ──
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
from domains import DOMAINS, mod_to_domain
from compress import load_json_from_gz


# ── 截断长度常量 ──
_TRUNC_DOC_MOD = 120     # 模块描述截断
_TRUNC_DOC_CLS = 150     # 类描述截断
_TRUNC_DESC = 200        # 方法/属性描述截断
_TRUNC_RTYPE = 200       # 返回值类型截断
_TRUNC_RETURNS = 200     # 返回值描述截断
_TRUNC_PTYPE = 80        # 参数类型截断
_TRUNC_RC_DESC = 200     # 返回值组成项描述截断
_TRUNC_RC_TYPE = 80      # 返回值组成项类型截断


def _build_method_item(m):
    """将中间 JSON 的方法对象转为精简 JS 格式。

    短键名: n(名) d(描述) s(签名) p(参数) r(返回描述) rt(返回类型)
            rc(返回组成) v(版本) lc(许可证)
    空值字段自动省略以减小体积。
    """
    mi = {
        "n": m["name"],
        "d": (m.get("desc") or "")[:_TRUNC_DESC],
    }
    if m.get("sig"):
        mi["s"] = m["sig"]
    if m.get("params"):
        mi["p"] = [[p["name"], (p.get("desc") or "")[:_TRUNC_DESC], (p.get("type") or "")[:_TRUNC_PTYPE]]
                   for p in m["params"]]
    if m.get("returns"):
        mi["r"] = m["returns"][:_TRUNC_RETURNS]
    if m.get("rtype"):
        mi["rt"] = m["rtype"][:_TRUNC_RTYPE]
    if m.get("return_components"):
        mi["rc"] = [[rc["name"], (rc.get("type") or "")[:_TRUNC_RC_TYPE], (rc.get("desc") or "")[:_TRUNC_RC_DESC]]
                    for rc in m["return_components"]]
    if m.get("version"):
        mi["v"] = m["version"]
    if m.get("license"):
        mi["lc"] = m["license"]
    return mi


def _build_property_item(prop):
    """将中间 JSON 的属性对象转为精简 JS 格式（带 pr:1 标记）。

    短键名: n(名) d(描述) pr(属性标记=1) s(签名) rt(返回类型) r(返回描述)
            rc(返回组成) p(参数) v(版本) lc(许可证)
    空值字段自动省略以减小体积。
    """
    pi = {
        "n": prop["name"],
        "d": (prop.get("desc") or "")[:_TRUNC_DESC],
        "pr": 1,
    }
    if prop.get("sig"):
        pi["s"] = prop["sig"]
    if prop.get("rtype"):
        pi["rt"] = prop["rtype"][:_TRUNC_RTYPE]
    if prop.get("returns"):
        pi["r"] = prop["returns"][:_TRUNC_RETURNS]
    if prop.get("return_components"):
        pi["rc"] = [[rc["name"], (rc.get("type") or "")[:_TRUNC_RC_TYPE], (rc.get("desc") or "")[:_TRUNC_RC_DESC]]
                    for rc in prop["return_components"]]
    if prop.get("params"):
        pi["p"] = [[p["name"], (p.get("desc") or "")[:_TRUNC_DESC], (p.get("type") or "")[:_TRUNC_PTYPE]]
                   for p in prop["params"]]
    if prop.get("version"):
        pi["v"] = prop["version"]
    if prop.get("license"):
        pi["lc"] = prop["license"]
    return pi


def _count_methods_recursive(cls):
    """递归统计类及其所有嵌套类的方法/属性总数（用于 sub 数组的计数列）。"""
    count = len(cls.get("methods", [])) + len(cls.get("properties", []))
    for nc in cls.get("nested_classes", []):
        count += _count_methods_recursive(nc)
    for ne in cls.get("nested_enums", []):
        count += _count_methods_recursive(ne)
    return count


def flatten_classes(classes, prefix=""):
    """展平嵌套类，输出精简格式的类条目列表。

    每个类条目格式: [全名, 描述, 方法/属性数组, sub?, par?, chl?]
    - sub (索引 3): 嵌套类摘要数组 [[短名, 全名, 方法数], ...]
    - par (索引 4): 父类数组（临时存原始 bases，后续由 resolve_inheritance 替换）
    - chl (索引 5): 子类数组（由 resolve_inheritance 添加）

    修复: 同时处理 classes 和 enums（旧版仅处理 classes，导致 194 个枚举全部丢失）。
    """
    result = []
    for c in classes:
        full_name = (prefix + "." if prefix else "") + c["name"]
        doc = (c.get("doc") or "")[:_TRUNC_DOC_CLS]

        # 合并方法与属性到统一数组（属性带 pr:1 标记）
        methods = []
        for m in c.get("methods", []):
            methods.append(_build_method_item(m))
        for prop in c.get("properties", []):
            methods.append(_build_property_item(prop))

        entry = [full_name, doc, methods]

        # 嵌套类摘要（索引 3: sub）
        nested = c.get("nested_classes", []) + c.get("nested_enums", [])
        if nested:
            sub = []
            for nc in nested:
                nc_full = full_name + "." + nc["name"]
                nc_mc = _count_methods_recursive(nc)
                sub.append([nc["name"], nc_full, nc_mc])
            entry.append(sub)

        # 原始基类（索引 4: par，临时存原始值，后续由 resolve_inheritance 解析替换）
        bases = c.get("bases", [])
        if bases:
            if len(entry) == 3:
                entry.append(None)  # sub 占位
            entry.append(bases)

        result.append(entry)

        # 递归展平嵌套类和嵌套枚举
        for nc in c.get("nested_classes", []):
            result.extend(flatten_classes([nc], full_name))
        for ne in c.get("nested_enums", []):
            result.extend(flatten_classes([ne], full_name))

    return result


def resolve_inheritance(top_data):
    """在所有模块合并完成后，第二阶段解析继承关系。

    将每个类条目索引 4 的原始 bases 替换为解析后的 par 列表，
    并为有子类的类添加 chl 列表（索引 5）。

    解析策略:
      1. 全名精确匹配（如 NXOpen.Body → top_data 中对应的条目）
      2. 短名回退匹配（如 Body → 取第一个同名类）
      3. 外部基类（如 object）标记为不可跳转
    """
    # 构建 全名 → (模块名, 条目) 映射表
    name_map = {}
    # 构建 短名 → [(模块名, 全名), ...] 回退映射表
    short_map = {}

    for mod_name, mod_data in top_data.items():
        for entry in mod_data["classes"]:
            full = entry[0]
            name_map[full] = (mod_name, entry)
            short = full.split('.')[-1]
            short_map.setdefault(short, []).append((mod_name, full))

    def resolve_one(base_name):
        """将 Python 基类名解析为 (模块名, 全名) 元组，无法解析返回 None。"""
        if base_name == 'object':
            return None
        # 去掉 NXOpen. 前缀
        relative = base_name[7:] if base_name.startswith('NXOpen.') else base_name
        parts = relative.split('.')
        class_name = parts[-1]

        # 策略 1: 多段路径 → 尝试在对应模块中精确匹配
        if len(parts) >= 2:
            mod_name_candidate = parts[0]
            if mod_name_candidate in top_data:
                # 尝试精确嵌套路径匹配
                for entry in top_data[mod_name_candidate]["classes"]:
                    entry_parts = entry[0].split('.')
                    if len(entry_parts) == len(parts) and all(
                        entry_parts[i] == parts[i] for i in range(len(parts))
                    ):
                        return (mod_name_candidate, entry[0])
                # 回退: 在该模块中按短名匹配
                for entry in top_data[mod_name_candidate]["classes"]:
                    if entry[0].split('.')[-1] == class_name:
                        return (mod_name_candidate, entry[0])

        # 策略 2: 单段或回退 → 按短名全局匹配
        candidates = short_map.get(class_name, [])
        if candidates:
            # 优先匹配模块名与类名相同或 NXOpen 模块的
            for mod, full in candidates:
                if mod == class_name or mod == 'NXOpen':
                    return (mod, full)
            return candidates[0]

        return None

    # 第一遍: 解析所有 bases → par 列表，同时构建 children 映射
    children = {}  # 父类全名 → [[子类短名, 子类模块名, 子类全名], ...]
    for full_name, (mod_name, entry) in name_map.items():
        raw = entry[4] if len(entry) > 4 and entry[4] else None
        if not raw:
            continue
        par = []
        for b in raw:
            if b == 'object':
                continue
            resolved = resolve_one(b)
            if resolved:
                short = resolved[1].split('.')[-1]
                par.append([short, resolved[0], resolved[1]])
                # 注册当前类为父类的子类
                child_short = full_name.split('.')[-1]
                children.setdefault(resolved[1], []).append([child_short, mod_name, full_name])
            else:
                par.append([b, "", ""])  # 外部基类，不可跳转
        # 用解析后的 par 替换原始 bases
        entry[4] = par if par else None
        if not par and len(entry) > 4:
            entry[4] = None

    # 第二遍: 为有子类的类添加 chl 列表（索引 5）
    for parent_full, chl_list in children.items():
        if parent_full in name_map:
            entry = name_map[parent_full][1]
            # 确保条目有足够元素
            while len(entry) < 4:
                entry.append(None)
            if len(entry) == 4:
                entry.append(None)  # par 占位
            entry.append(chl_list)  # 索引 5: chl


def main():
    """主入口: 读取中间 JSON，展平合并，解析继承，分组输出精简 JS。"""
    # 从 gzip 压缩文件加载中间 JSON（不解压到磁盘）
    modules = load_json_from_gz(INPUT)

    # 分离顶层模块和 clss 子目录模块
    top_modules = [m for m in modules if not m["name"].startswith("clss.")]
    clss_modules = [m for m in modules if m["name"].startswith("clss.")]

    # 展平顶层模块的类和枚举
    top_data = {}
    for m in top_modules:
        name = m["name"]
        if name == "_nxopen":
            continue
        # 修复: 同时处理 classes 和 enums（旧版仅处理 classes）
        all_classes = m.get("classes", []) + m.get("enums", [])
        flat = flatten_classes(all_classes, name)
        top_data[name] = {
            "d": (m.get("doc") or "")[:_TRUNC_DOC_MOD],
            "classes": flat,
        }

    # 将 clss/ 类按继承关系归入顶层模块
    nxopen_fallback = []
    for m in clss_modules:
        # 修复: clss 模块的 enums 也要处理
        all_classes = m.get("classes", []) + m.get("enums", [])
        for c in all_classes:
            parent = None
            for b in c.get("bases", []):
                parts = b.split(".")
                if len(parts) >= 3 and parts[0] == "NXOpen":
                    if parts[1] in top_data:
                        parent = parts[1]
                        break
            flat = flatten_classes([c])
            if parent:
                top_data[parent]["classes"].extend(flat)
            else:
                nxopen_fallback.extend(flat)

    # 无匹配父模块的类回退到 NXOpen
    if nxopen_fallback:
        top_data.setdefault("NXOpen", {"d": "NXOpen core API", "classes": []})
        top_data["NXOpen"]["classes"].extend(nxopen_fallback)

    # 第二阶段: 解析继承关系（在所有合并完成后）
    resolve_inheritance(top_data)

    # 按功能域分组
    domains = {}
    for mod_name, mod_data in top_data.items():
        domain = mod_to_domain.get(mod_name, "其他")
        domains.setdefault(domain, []).append({
            "n": mod_name,
            "d": mod_data["d"],
            "c": mod_data["classes"],
        })

    # 按方法数降序排列功能域（cls[2] 是方法/属性数组，len 求和得到方法总数）
    domain_order = sorted(domains.keys(), key=lambda d: -sum(
        sum(len(cls[2]) for cls in m["c"]) for m in domains[d]
    ))

    # 构建最终结果
    result = []
    for domain in domain_order:
        mods = domains[domain]
        # 域内模块按方法数降序
        mods.sort(key=lambda x: -sum(len(c[2]) for c in x["c"]))
        total_cls = sum(len(m["c"]) for m in mods)
        total_mc = sum(sum(len(c[2]) for c in m["c"]) for m in mods)
        result.append({
            "n": domain,
            "cc": total_cls,
            "mc": total_mc,
            "mods": mods,
        })

    # 写入精简 JS 文件
    js_content = "window.NXOPEN_DATA = " + json.dumps(result, ensure_ascii=False, separators=(',', ':')) + ";"
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(js_content)

    # ── 统计输出 ──
    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    par_count = 0
    chl_count = 0
    lic_count = 0
    total_cls = 0
    for d in result:
        for m in d["mods"]:
            for c in m["c"]:
                total_cls += 1
                if len(c) > 4 and c[4]:
                    par_count += 1
                if len(c) > 5 and c[5]:
                    chl_count += 1
                for mi in c[2]:
                    if isinstance(mi, dict) and mi.get("lc"):
                        lic_count += 1
    print(f"Domains: {len(result)}")
    for d in result:
        print(f"  {d['n']:15s} modules={len(d['mods']):3d} classes={d['cc']:6d} methods={d['mc']:6d}")
    print(f"Total classes: {total_cls}")
    print(f"Classes with parents: {par_count}")
    print(f"Classes with children: {chl_count}")
    print(f"Methods/properties with license: {lic_count}")
    print(f"Output: {OUTPUT}")
    print(f"Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
