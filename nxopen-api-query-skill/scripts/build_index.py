# -*- coding: utf-8 -*-
"""
Build SQLite index from nxopen_structure.json for fast API queries.
Merges clss/ classes into top-level modules (same logic as nxopen-api-map/gen_js.py),
so class full names follow NXOpen convention (e.g. "NXOpen.Body", "CAE.CAE.Frf5").

数据来源: Siemens NX 2212 版本的 NXOpen Python API 类型存根（.pyi），由上游
nxopen-api-map 项目的 parse_pyi.py 解析为 nxopen_structure.json.gz。

Usage:
    python build_index.py [--source PATH] [--output PATH] [--compress]

Arguments:
    --source PATH    (可选) nxopen_structure.json 路径，默认为 data/nxopen_structure.json
    --output PATH    (可选) 输出数据库路径，默认为 data/nxopen_api.db

注:
    --source 可选。不指定时默认使用 skill 的 data/nxopen_structure.json。
    首次运行查询脚本时会自动调用本脚本构建数据库（无需手动运行）。
"""
import json
import os
import sqlite3
import sys
import time

# Minimum SQLite version required: trigram tokenizer introduced in 3.34.0
MIN_SQLITE = (3, 34, 0)
if sqlite3.sqlite_version_info < MIN_SQLITE:
    print(f"ERROR: SQLite {sqlite3.sqlite_version} 低于最低要求 {MIN_SQLITE[0]}.{MIN_SQLITE[1]}.{MIN_SQLITE[2]}")
    print("原因: 本工具依赖 FTS5 trigram 分词器（SQLite 3.34.0 引入）用于类名/方法名子串检索。")
    print("解决: 升级 Python 到自带较新 SQLite 的版本，或安装 pysqlite3-binary 并设置环境。")
    print("      conda: conda install -c conda-forge python=3.10  (通常自带较新 SQLite)")
    print("      pip:   pip install pysqlite3-binary  (并在脚本顶部 __import__('pysqlite3') 替换)")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(SCRIPT_DIR)  # skill 根目录（scripts 的父目录）
DEFAULT_OUTPUT = os.path.join(_ROOT_DIR, "data", "nxopen_api.db")
DEFAULT_SOURCE = os.path.join(_ROOT_DIR, "data", "nxopen_structure.json")
DEFAULT_SOURCE_GZ = os.path.join(_ROOT_DIR, "data", "nxopen_structure.json.gz")

# 导入功能域映射表和压缩工具（与 nxopen-api-map 保持一致）
sys.path.insert(0, SCRIPT_DIR)
from domains import DOMAINS
from compress import compress_file, load_json_from_gz


def flatten_classes(classes, prefix, mod_id, conn, parent_id=None):
    """Recursively insert classes and their methods/properties/nested classes."""
    for c in classes:
        full_name = (prefix + "." if prefix else "") + c.get("name", "")
        short_name = c.get("name", "")
        bases_json = json.dumps(c.get("bases", []), ensure_ascii=False)
        cur = conn.execute(
            "INSERT INTO classes (module_id, full_name, short_name, doc, bases, parent_class_id, is_nested) VALUES (?,?,?,?,?,?,?)",
            (mod_id, full_name, short_name, c.get("doc", ""), bases_json, parent_id, 1 if parent_id else 0)
        )
        cls_id = cur.lastrowid

        for m in c.get("methods", []):
            conn.execute(
                "INSERT INTO methods (class_id, name, desc, sig, params, returns, rtype, rc, version, is_property) VALUES (?,?,?,?,?,?,?,?,?,0)",
                (cls_id, m.get("name", ""), m.get("desc", ""), m.get("sig", ""),
                 json.dumps(m.get("params", []), ensure_ascii=False),
                 m.get("returns", ""), m.get("rtype", ""),
                 json.dumps(m.get("return_components", []), ensure_ascii=False),
                 m.get("version", ""))
            )

        for p in c.get("properties", []):
            conn.execute(
                "INSERT INTO methods (class_id, name, desc, sig, params, returns, rtype, rc, version, is_property) VALUES (?,?,?,?,?,?,?,?,?,1)",
                (cls_id, p.get("name", ""), p.get("desc", ""), p.get("sig", ""),
                 json.dumps(p.get("params", []), ensure_ascii=False),
                 p.get("returns", ""), p.get("rtype", ""),
                 json.dumps(p.get("return_components", []), ensure_ascii=False),
                 p.get("version", ""))
            )

        for nc in c.get("nested_classes", []):
            flatten_classes([nc], full_name, mod_id, conn, cls_id)
        for nc in c.get("nested_enums", []):
            flatten_classes([nc], full_name, mod_id, conn, cls_id)


def _rc_text(rc_json):
    """Extract plain text from return_components JSON (name + desc of each field)."""
    if not rc_json:
        return ""
    try:
        items = json.loads(rc_json)
    except Exception:
        return ""
    parts = []
    for it in items:
        if isinstance(it, dict):
            n = it.get("name", "")
            d = it.get("desc", "")
            if n:
                parts.append(n)
            if d:
                parts.append(d)
        elif isinstance(it, str):
            parts.append(it)
    return " ".join(parts)


def _backfill_struct_props(conn):
    """B'': backfill return-struct property semantics into method returns.
    For each method whose rtype points to a struct/class in the classes table,
    append that struct's property name+desc to the method's returns field.
    e.g. Evalsf.Evaluate (returns Srfvalue) gets 'SrfUnormal unit normal' in returns,
    so searching 'normal' finds it. One level deep only. Batch-optimized."""
    import re
    # 1) build full_name -> class_id map (one query)
    name_map = {}
    for r in conn.execute("SELECT id, full_name FROM classes").fetchall():
        name_map[r[1]] = r[0]
    # 2) pre-fetch all properties grouped by class_id (one query)
    props_by_cls = {}
    for r in conn.execute("SELECT class_id, name, desc FROM methods WHERE is_property=1").fetchall():
        props_by_cls.setdefault(r[0], []).append((r[1], r[2]))
    # 3) iterate methods with rtype, resolve struct, build UPDATE batch
    updates = []
    for mid, rtype, returns in conn.execute("SELECT id, rtype, returns FROM methods WHERE rtype LIKE 'NXOpen.%'").fetchall():
        if not rtype:
            continue
        m = re.match(r'(NXOpen\.[A-Za-z0-9_.]+)', rtype)
        if not m:
            continue
        ref = m.group(1)
        cls_id = name_map.get(ref)
        if cls_id is None:
            for cand in (ref + "_Struct", ref.replace(".", "") + "_Struct", ref + "Struct"):
                if cand in name_map:
                    cls_id = name_map[cand]
                    break
        if cls_id is None or cls_id not in props_by_cls:
            continue
        prop_parts = []
        for pn, pd in props_by_cls[cls_id]:
            if pn:
                prop_parts.append(pn)
            if pd:
                prop_parts.append(pd)
        if not prop_parts:
            continue
        implied = " ".join(prop_parts)
        new_returns = (returns + " " + implied) if returns else implied
        updates.append((new_returns, mid))
    # 4) batch update
    if updates:
        conn.executemany("UPDATE methods SET returns=? WHERE id=?", updates)
        print(f"      Backfilled struct props into {len(updates)} methods' returns")



def build(source_path, output_path):
    t0 = time.time()
    print(f"[1/4] Loading JSON: {source_path}")
    if source_path.endswith(".gz"):
        modules = load_json_from_gz(source_path)
    else:
        with open(source_path, "r", encoding="utf-8") as f:
            modules = json.load(f)
    print(f"      Loaded {len(modules)} modules in {time.time()-t0:.1f}s")

    # Separate top-level and clss/ modules (same as nxopen-api-map/gen_js.py)
    top_modules = [m for m in modules if not m["name"].startswith("clss.")]
    clss_modules = [m for m in modules if m["name"].startswith("clss.")]

    # Build top_data: module_name -> {doc, classes (raw)}
    top_data = {}
    for m in top_modules:
        name = m["name"]
        if name == "_nxopen":
            continue
        top_data[name] = {"doc": m.get("doc", ""), "classes": m.get("classes", []),
                         "enums": m.get("enums", [])}

    # Merge clss/ classes into parent modules
    for m in clss_modules:
        for c in m.get("classes", []):
            parent = None
            for b in c.get("bases", []):
                parts = b.split(".")
                if len(parts) >= 3 and parts[0] == "NXOpen":
                    if parts[1] in top_data:
                        parent = parts[1]
                        break
            if parent:
                top_data[parent]["classes"].extend([c])
            else:
                if "NXOpen" not in top_data:
                    top_data["NXOpen"] = {"doc": "NXOpen core API", "classes": [], "enums": []}
                top_data["NXOpen"]["classes"].extend([c])
        for e in m.get("enums", []):
            parent = None
            for b in e.get("bases", []):
                parts = b.split(".")
                if len(parts) >= 3 and parts[0] == "NXOpen":
                    if parts[1] in top_data:
                        parent = parts[1]
                        break
            if parent:
                top_data[parent]["enums"].extend([e])
            else:
                if "NXOpen" not in top_data:
                    top_data["NXOpen"] = {"doc": "NXOpen core API", "classes": [], "enums": []}
                top_data["NXOpen"]["enums"].extend([e])

    print(f"      Top-level modules: {len(top_data)}")

    if os.path.exists(output_path):
        os.remove(output_path)

    conn = sqlite3.connect(output_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")

    print("[2/4] Creating schema...")
    conn.executescript("""
        CREATE TABLE modules (
            id      INTEGER PRIMARY KEY,
            name    TEXT,
            doc     TEXT,
            domain  TEXT
        );
        CREATE TABLE classes (
            id              INTEGER PRIMARY KEY,
            module_id       INTEGER,
            full_name       TEXT,
            short_name      TEXT,
            doc             TEXT,
            bases           TEXT,
            parent_class_id INTEGER DEFAULT NULL,
            is_nested       INTEGER DEFAULT 0,
            FOREIGN KEY (module_id) REFERENCES modules(id)
        );
        CREATE TABLE methods (
            id          INTEGER PRIMARY KEY,
            class_id    INTEGER,
            name        TEXT,
            desc        TEXT,
            sig         TEXT,
            params      TEXT,
            returns     TEXT,
            rtype       TEXT,
            rc          TEXT,
            version     TEXT,
            is_property INTEGER DEFAULT 0,
            FOREIGN KEY (class_id) REFERENCES classes(id)
        );
    """)

    print("[3/4] Inserting data...")
    mod_count = 0
    cls_count = 0
    meth_count = 0

    for mod_name, mod_data in top_data.items():
        domain = "其他"
        for d, mods in DOMAINS.items():
            if mod_name in mods:
                domain = d
                break
        mod_cur = conn.execute(
            "INSERT INTO modules (name, doc, domain) VALUES (?,?,?)",
            (mod_name, mod_data.get("doc", ""), domain)
        )
        mod_id = mod_cur.lastrowid
        mod_count += 1

        flatten_classes(mod_data["classes"], mod_name, mod_id, conn)
        flatten_classes(mod_data.get("enums", []), mod_name, mod_id, conn)

    conn.commit()

    # Count
    cls_count = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    meth_count = conn.execute("SELECT COUNT(*) FROM methods").fetchone()[0]
    print(f"      Modules: {mod_count}, Classes: {cls_count}, Methods/Properties: {meth_count}")

    _backfill_struct_props(conn)
    print("[4/4] Building indexes...")
    conn.executescript("""
        CREATE INDEX idx_classes_full   ON classes(full_name);
        CREATE INDEX idx_classes_short   ON classes(short_name);
        CREATE INDEX idx_classes_mod     ON classes(module_id);
        CREATE INDEX idx_classes_parent  ON classes(parent_class_id);
        CREATE INDEX idx_methods_class   ON methods(class_id);
        CREATE INDEX idx_methods_name    ON methods(name);
        CREATE INDEX idx_methods_prop    ON methods(is_property);
        CREATE INDEX idx_mod_domain      ON modules(domain);
    """)

    # Register _rc_text as a SQLite function so it can be used in INSERT ... SELECT
    conn.create_function("_rc_text", 1, _rc_text)

    conn.executescript("""
        -- 类名/短名子串检索（trigram，支持 camelCase 子串命中，如搜 Body 命中 BodyDes）
        CREATE VIRTUAL TABLE classes_name_fts USING fts5(
            full_name, short_name,
            content=classes, content_rowid=id,
            tokenize='trigram'
        );
        INSERT INTO classes_name_fts(rowid, full_name, short_name)
            SELECT id, full_name, COALESCE(short_name,'') FROM classes;

        -- 方法名子串检索（trigram，支持 camelCase 子串命中）
        CREATE VIRTUAL TABLE methods_name_fts USING fts5(
            name,
            content=methods, content_rowid=id,
            tokenize='trigram'
        );
        INSERT INTO methods_name_fts(rowid, name) SELECT id, name FROM methods;

        -- 类文档全文检索（unicode61 词级 + BM25）
        CREATE VIRTUAL TABLE classes_fts USING fts5(
            full_name, doc,
            content=classes, content_rowid=id,
            tokenize='unicode61'
        );
        INSERT INTO classes_fts(rowid, full_name, doc) SELECT id, full_name, COALESCE(doc,'') FROM classes;

        -- 方法全文检索（unicode61 词级 + BM25，含 rc 列；returns 已含结构体属性回灌文本）
        CREATE VIRTUAL TABLE methods_fts USING fts5(
            name, desc, params, returns, rtype, rc,
            content=methods, content_rowid=id,
            tokenize='unicode61'
        );
        INSERT INTO methods_fts(rowid, name, desc, params, returns, rtype, rc)
            SELECT id, name, COALESCE(desc,''), COALESCE(params,''),
                   COALESCE(returns,''), COALESCE(rtype,''), COALESCE(rc,'')
            FROM methods;

        -- 方法标识符类字段子串检索（trigram，让 unitNorm/srf_unormal 等 camelCase 可被 normal 命中）
        CREATE VIRTUAL TABLE methods_body_fts USING fts5(
            name, returns, rtype, params, rc_text,
            tokenize='trigram'
        );
        INSERT INTO methods_body_fts(rowid, name, returns, rtype, params, rc_text)
            SELECT m.id, m.name, COALESCE(m.returns,''), COALESCE(m.rtype,''),
                   COALESCE(m.params,''), _rc_text(m.rc)
            FROM methods m;
    """)

    conn.commit()
    conn.close()

    db_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nDone in {time.time()-t0:.1f}s")
    print(f"Database: {output_path} ({db_size:.1f} MB)")


if __name__ == "__main__":
    # --source optional: default to data/nxopen_structure.json (shipped with skill)
    # --compress: compress data/nxopen_structure.json to .gz, then exit
    if "--compress" in sys.argv:
        src = DEFAULT_SOURCE
        dst = DEFAULT_SOURCE_GZ
        if not os.path.exists(src):
            print(f"ERROR: 源文件不存在: {src}")
            sys.exit(1)
        compress_file(src, dst)
        sys.exit(0)

    # --source optional: find json or gz in data/
    if "--source" in sys.argv:
        source = sys.argv[sys.argv.index("--source") + 1]
    else:
        if os.path.exists(DEFAULT_SOURCE):
            source = DEFAULT_SOURCE
        elif os.path.exists(DEFAULT_SOURCE_GZ):
            source = DEFAULT_SOURCE_GZ
        else:
            print(f"ERROR: 数据源不存在: {DEFAULT_SOURCE} 或 {DEFAULT_SOURCE_GZ}")
            print(f"用法: python build_index.py --source <path> [--output PATH] [--compress]")
            sys.exit(1)
        print(f"使用默认数据源: {source}")
    output = sys.argv[sys.argv.index("--output") + 1] if "--output" in sys.argv else DEFAULT_OUTPUT
    build(source, output)
