# -*- coding: utf-8 -*-
"""
NXOpen Python API query tool — fast SQLite-backed lookup.

Usage:
    python nxopen_query.py search  <text>           Full-text search (trigram name + BM25 desc/params/returns)
    python nxopen_query.py class   <full_name>      Class details (doc, bases, methods, properties, nested)
    python nxopen_query.py method  <name> [--cls <class>]   Find methods by name
    python nxopen_query.py verify  <name>           Verify if a name exists (class/method/property)
    python nxopen_query.py module  <name>           List all classes in a module
    python nxopen_query.py inherit <class_name>     Inheritance tree (parents + children)
    python nxopen_query.py suggest <name>           Fuzzy-suggest similar class/method names
    python nxopen_query.py modules                   List all modules
    python nxopen_query.py count                     Show statistics
    python nxopen_query.py batch   '<json>'| -f f.json  Run multiple sub-queries in one process

Options:
    --db PATH        Database path (default: data/nxopen_api.db in skill root)
    --limit N        Max results (default: 30)
    --json           Output as JSON (for programmatic use)
"""
import json as _json
import os
import re
import sqlite3
import sys

# Force UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(SCRIPT_DIR)  # skill 根目录（scripts 的父目录）
DEFAULT_DB = os.path.join(_ROOT_DIR, "data", "nxopen_api.db")
DEFAULT_SOURCE = os.path.join(_ROOT_DIR, "data", "nxopen_structure.json")
DEFAULT_SOURCE_GZ = os.path.join(_ROOT_DIR, "data", "nxopen_structure.json.gz")

# BM25 column weights for methods_fts(name, desc, params, returns, rtype, rc).
# returns/rc weighted higher: return-value / struct-property hits rank higher.
BM25_WEIGHTS = (1.0, 1.0, 1.5, 2.0, 1.5, 1.5)


def _query_tokens(query):
    """Split query into lowercase tokens (for distinct-token-hit counting)."""
    return [w for w in re.split(r"\s+", str(query).strip()) if w]


def _count_token_hits(name, returns, rtype, params, rc, tokens):
    """Count distinct query tokens hit using WORD-BOUNDARY matching (not bare substring).

    For camelCase identifiers (name/returns/rtype) the field itself is the 'word',
    so we check token as substring there (trigram already handles that at recall time).
    For free-text-ish fields (rc JSON text) we use word-boundary to avoid 'normal' matching
    inside 'Returns the normal of...' prose giving false high scores.
    """
    name_l = (name or "").lower()
    ret_l = (returns or "").lower()
    rtype_l = (rtype or "").lower()
    params_l = (params or "").lower()
    rc_l = (rc or "").lower()
    cnt = 0
    for tk in tokens:
        tk_l = tk.lower()
        if not tk_l:
            continue
        # name/returns/rtype: camelCase identifiers, substring match OK (trigram domain)
        if tk_l in name_l or tk_l in ret_l or tk_l in rtype_l or tk_l in params_l:
            cnt += 1
            continue
        # rc / free text: word-boundary match to avoid false prose hits
        if re.search(r'(?<![a-z])' + re.escape(tk_l) + r'(?![a-z])', rc_l):
            cnt += 1
    return cnt


def _is_placeholder_desc(desc):
    """True if desc is a UF placeholder like 'Refer to UF_MODL_xxx for documentation.'"""
    return bool(desc) and desc.strip().startswith("Refer to UF")


def _score_method(row, q_tokens):
    """Compute a single composite sort key for a method row.

    Lower tuple = ranks first. Factors (in priority order):
    1. All-token-hit group: methods hitting ALL query tokens rank above partial hits.
    2. Token hits: more distinct tokens hit = more relevant.
    3. Placeholder bonus: UF methods with 'Refer to UF_xxx' desc get a small boost,
       but only if they also hit via body path (high-relevance) — avoids lifting
       placeholder methods that only weakly matched.
    4. Path hits: methods found by more recall paths (name/body/desc) rank higher.
    5. BM25 score: final tiebreaker by textual relevance.
    """
    n_tok = len(q_tokens) if q_tokens else 1
    tok_hits = _count_token_hits(row["name"], row.get("returns", ""), row.get("rtype", ""),
                                 row.get("params", ""), row.get("rc", ""), q_tokens)
    all_hit = 0 if (tok_hits >= n_tok and n_tok > 1) else 1  # 0=good (all hit), 1=partial
    placeholder = 1 if _is_placeholder_desc(row.get("desc", "")) else 0
    body_hit = row.get("_body", 0)
    # placeholder bonus: only applies within all-token-hit group AND body path
    ph_bonus = -placeholder if (all_hit == 0 and body_hit) else 0
    paths = row.get("_paths", 1)
    score = row.get("score", 0.0)
    return (all_hit, -tok_hits, ph_bonus, -paths, score)

# Minimum SQLite version required: trigram tokenizer introduced in 3.34.0
MIN_SQLITE = (3, 34, 0)
if sqlite3.sqlite_version_info < MIN_SQLITE:
    print(f"ERROR: SQLite {sqlite3.sqlite_version} 低于最低要求 {MIN_SQLITE[0]}.{MIN_SQLITE[1]}.{MIN_SQLITE[2]}")
    print("原因: 数据库依赖 FTS5 trigram 分词器（SQLite 3.34.0 引入）。")
    print("解决: 升级 Python（通常自带较新 SQLite），或 pip install pysqlite3-binary 并在脚本顶部替换 sqlite3。")
    sys.exit(1)


def _ensure_db(db_path):
    """If database doesn't exist, auto-build it from data/nxopen_structure.json or .json.gz.

    Search order: db → json → gz → error.
    If only .gz exists, build_index.py reads it via gzip stream (no temp file on disk).
    """
    if os.path.exists(db_path):
        return
    # Find data source: prefer .json (ready to use), fallback to .gz (decompress)
    src = None
    if os.path.exists(DEFAULT_SOURCE):
        src = DEFAULT_SOURCE
    elif os.path.exists(DEFAULT_SOURCE_GZ):
        src = DEFAULT_SOURCE_GZ
    else:
        print(f"ERROR: Database not found: {db_path}")
        print(f"       数据源也不存在: {DEFAULT_SOURCE} 或 {DEFAULT_SOURCE_GZ}")
        print(f"Run: python scripts/build_index.py --source <path>")
        sys.exit(1)
    print(f"[INFO] Database not found, auto-building from: {src}")
    print(f"[INFO] This may take ~10s (one-time)...")
    import subprocess
    build_script = os.path.join(SCRIPT_DIR, "build_index.py")
    r = subprocess.run([sys.executable, build_script, "--source", src, "--output", db_path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[ERROR] Auto-build failed:\n{r.stderr}")
        sys.exit(1)
    print(f"[INFO] Database built successfully.")


def get_db(db_path):
    _ensure_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _fts_escape(term):
    """Escape a single token for safe use in an FTS5 MATCH expression.

    FTS5 treats special chars (" * ( ) : - OR AND NOT) as syntax. Wrap any
    bare token in double quotes so it is matched literally as a phrase.
    """
    if term is None:
        return ""
    term = str(term).strip().strip('"')
    if not term:
        return ""
    # Doubled double-quote inside, then wrap in quotes
    esc = term.replace('"', '""')
    return f'"{esc}"'


def _build_fts_match(query, mode="and"):
    """Build an FTS5 MATCH string from a free-form query.

    - Splits on whitespace.
    - Each token is escaped via _fts_escape (literal phrase match).
    - mode 'and' → implicit AND (space join); 'or' → OR join.
    - Empty → returns empty string (caller should skip MATCH).
    """
    if not query:
        return ""
    tokens = [t for t in re.split(r"\s+", str(query).strip()) if t]
    if not tokens:
        return ""
    joiner = " " if mode == "and" else " OR "
    return joiner.join(_fts_escape(t) for t in tokens)


def _build_trigram_match(query):
    """Build a MATCH string for a trigram FTS5 table.

    trigram indexes match substrings, so a single escaped phrase works well;
    multi-token queries are AND-joined. Tokens shorter than 3 chars are
    skipped (trigram needs >=3 chars to produce any n-grams).
    """
    if not query:
        return ""
    tokens = [t for t in re.split(r"\s+", str(query).strip()) if len(t) >= 3]
    if not tokens:
        # fall back to any single token even if <3 (will simply not match)
        tokens = [t for t in re.split(r"\s+", str(query).strip()) if t]
        if not tokens:
            return ""
    return " ".join(_fts_escape(t) for t in tokens)


def _build_trigram_match_or(query):
    """Build a trigram MATCH string with OR semantics (any token matches)."""
    if not query:
        return ""
    tokens = [t for t in re.split(r"\s+", str(query).strip()) if len(t) >= 3]
    if not tokens:
        tokens = [t for t in re.split(r"\s+", str(query).strip()) if t]
        if not tokens:
            return ""
    return " OR ".join(_fts_escape(t) for t in tokens)


def fmt_desc(doc, max_len=300):
    if not doc:
        return ""
    doc = doc.strip()
    if len(doc) > max_len:
        doc = doc[:max_len] + "..."
    return doc


def fmt_params(params_json):
    if not params_json:
        return ""
    try:
        params = _json.loads(params_json)
    except Exception:
        return ""
    if not params:
        return ""
    lines = []
    for p in params:
        name = p.get("name", "?")
        desc = p.get("desc", "")
        ptype = p.get("type", "")
        line = f"    • {name}"
        if ptype:
            line += f" ({ptype})"
        if desc:
            d = desc.strip().replace("\n", " ")
            if len(d) > 120:
                d = d[:120] + "..."
            line += f": {d}"
        lines.append(line)
    return "\n".join(lines)


def fmt_rc(rc_json):
    if not rc_json:
        return ""
    try:
        rc = _json.loads(rc_json)
    except Exception:
        return ""
    if not rc:
        return ""
    lines = []
    for item in rc:
        if isinstance(item, list) and len(item) >= 2:
            lines.append(f"    • {item[0]}: {item[1]}")
        elif isinstance(item, str):
            lines.append(f"    • {item}")
    return "\n".join(lines)


# ── Commands ──────────────────────────────────────────────

def cmd_search(conn, args, limit=30, as_json=False):
    """Full-text search across classes and methods (trigram name + BM25 desc/params/returns)."""
    query = " ".join(args).strip()
    if not query:
        print("Usage: search <text>")
        return

    results = {"classes": [], "methods": []}
    name_match = _build_trigram_match(query)
    desc_match = _build_fts_match(query, "and")

    # --- classes: name (trigram substring) OR doc (unicode61 BM25) ---
    cls_rows = []
    if name_match:
        cls_rows = conn.execute(
            """SELECT c.id, c.full_name, c.short_name, c.doc, bm25(classes_name_fts) AS score
               FROM classes_name_fts f JOIN classes c ON c.id = f.rowid
               WHERE classes_name_fts MATCH ?
               ORDER BY score LIMIT ?""", (name_match, limit)
        ).fetchall()
    if desc_match:
        seen = {r["id"] for r in cls_rows}
        more = conn.execute(
            """SELECT c.id, c.full_name, c.short_name, c.doc, bm25(classes_fts) AS score
               FROM classes_fts f JOIN classes c ON c.id = f.rowid
               WHERE classes_fts MATCH ?
               ORDER BY score LIMIT ?""", (desc_match, limit)
        ).fetchall()
        cls_rows = list(cls_rows) + [r for r in more if r["id"] not in seen]
    # rank: exact/short-name hits first, then bm25
    cls_rows.sort(key=lambda r: (0 if r["short_name"] and query.lower() in r["short_name"].lower() else 1, r["score"]))

    for r in cls_rows[:limit]:
        results["classes"].append({
            "full_name": r["full_name"], "doc": fmt_desc(r["doc"])
        })

    # --- methods: 3-way recall (name trigram AND + body trigram AND + desc unicode61 OR) ---
    name_match = _build_trigram_match(query)
    body_and = _build_trigram_match(query)
    desc_or = _build_fts_match(query, "or")

    meth_map = {}
    # name path: all tokens must hit name (AND)
    if name_match:
        for r in conn.execute(
            """SELECT m.id, m.name, m.desc, m.sig, m.is_property, c.full_name AS cls_name,
                      m.returns, m.rtype, m.params, m.rc,
                      bm25(methods_name_fts) AS score
               FROM methods_name_fts f JOIN methods m ON m.id = f.rowid
               JOIN classes c ON m.class_id = c.id
               WHERE methods_name_fts MATCH ?
               LIMIT ?""", (name_match, limit * 2)
        ).fetchall():
            d = dict(r); d["_paths"] = 1; d.setdefault("score", 0.0); d["_body"] = 0; meth_map[r["id"]] = d
    # body path: all tokens must hit body fields (AND) — narrows to high-relevance methods
    if body_and:
        for r in conn.execute(
            """SELECT m.id, m.name, m.desc, m.sig, m.is_property, c.full_name AS cls_name,
                      m.returns, m.rtype, m.params, m.rc
               FROM methods_body_fts f JOIN methods m ON m.id = f.rowid
               JOIN classes c ON m.class_id = c.id
               WHERE methods_body_fts MATCH ?
               LIMIT ?""", (body_and, max(200, limit * 5))
        ).fetchall():
            if r["id"] in meth_map:
                meth_map[r["id"]]["_paths"] += 1
                meth_map[r["id"]]["_body"] = 1
            else:
                d = dict(r); d["_paths"] = 1; d["score"] = 0.0; d["_body"] = 1; meth_map[r["id"]] = d
    # desc path: any token in desc/params/returns/rtype/rc (OR + weighted bm25)
    if desc_or:
        for r in conn.execute(
            """SELECT m.id, m.name, m.desc, m.sig, m.is_property, c.full_name AS cls_name,
                      m.returns, m.rtype, m.params, m.rc,
                      bm25(methods_fts, ?, ?, ?, ?, ?, ?) AS score
               FROM methods_fts f JOIN methods m ON m.id = f.rowid
               JOIN classes c ON m.class_id = c.id
               WHERE methods_fts MATCH ?
               LIMIT ?""", (*BM25_WEIGHTS, desc_or, limit * 2)
        ).fetchall():
            if r["id"] in meth_map:
                meth_map[r["id"]]["_paths"] += 1
                meth_map[r["id"]]["score"] = r["score"]
            else:
                d = dict(r); d["_paths"] = 1; d["_body"] = 0; meth_map[r["id"]] = d

    # --- ranking: single clear composite score ---
    q_tokens = _query_tokens(query)
    meth_rows = list(meth_map.values())
    for r in meth_rows:
        r["_sort_key"] = _score_method(r, q_tokens)
    meth_rows.sort(key=lambda r: r["_sort_key"])

    for r in meth_rows[:limit]:
        results["methods"].append({
            "name": r["name"], "class": r["cls_name"], "desc": fmt_desc(r["desc"]),
            "sig": r["sig"] or "", "type": "property" if r["is_property"] else "method"
        })

    if as_json:
        print(_json.dumps(results, ensure_ascii=False, indent=2))
        return

    if results["classes"]:
        print(f"=== 类 ({len(results['classes'])}) ===")
        for c in results["classes"]:
            print(f"  {c['full_name']}")
            if c["doc"]:
                print(f"    {c['doc']}")
        print()

    if results["methods"]:
        print(f"=== 方法/属性 ({len(results['methods'])}) ===")
        for m in results["methods"]:
            tag = "[属性]" if m["type"] == "property" else "[方法]"
            print(f"  {tag} {m['class']}.{m['name']}")
            if m["sig"]:
                print(f"    签名: {m['sig']}")
            if m["desc"]:
                print(f"    {m['desc']}")
        print()

    if not results["classes"] and not results["methods"]:
        print(f"未找到与 '{query}' 相关的结果。")
        print(f"提示: 使用 'suggest {query}' 查看相似名称。")


def cmd_class(conn, args, limit=30, as_json=False):
    """Get full details of a specific class."""
    class_name = " ".join(args).strip()
    if not class_name:
        print("Usage: class <full_name>")
        return

    # Try exact match first, then short name
    row = conn.execute(
        "SELECT * FROM classes WHERE full_name = ?", (class_name,)
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT * FROM classes WHERE short_name = ? LIMIT 1", (class_name,)
        ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT * FROM classes WHERE full_name LIKE ? LIMIT 1", (f"%{class_name}%",)
        ).fetchone()

    if not row:
        print(f"未找到类 '{class_name}'。")
        print(f"提示: 使用 'suggest {class_name}' 查看相似名称。")
        return

    result = {
        "full_name": row["full_name"],
        "doc": row["doc"] or "",
        "bases": _json.loads(row["bases"]) if row["bases"] else [],
        "is_nested": bool(row["is_nested"]),
        "methods": [],
        "properties": [],
        "nested_classes": [],
        "parent_classes": [],
        "child_classes": []
    }

    # Get module name
    mod = conn.execute("SELECT name FROM modules WHERE id = ?", (row["module_id"],)).fetchone()
    result["module"] = mod["name"] if mod else ""

    # Bases (parents)
    for base_name in result["bases"]:
        base_row = conn.execute("SELECT full_name FROM classes WHERE full_name = ?", (base_name,)).fetchone()
        result["parent_classes"].append({
            "name": base_name,
            "found": base_row is not None
        })

    # Children (classes that have this class as base)
    child_rows = conn.execute(
        "SELECT full_name FROM classes WHERE bases LIKE ?",
        (f'%"{row["full_name"]}"%',)
    ).fetchall()
    for cr in child_rows:
        bases = _json.loads(conn.execute("SELECT bases FROM classes WHERE full_name = ?", (cr["full_name"],)).fetchone()["bases"] or "[]")
        if row["full_name"] in bases:
            result["child_classes"].append(cr["full_name"])

    # Nested classes
    nested_rows = conn.execute(
        "SELECT full_name, short_name, doc FROM classes WHERE parent_class_id = ?", (row["id"],)
    ).fetchall()
    for nr in nested_rows:
        result["nested_classes"].append({
            "full_name": nr["full_name"],
            "short_name": nr["short_name"],
            "doc": fmt_desc(nr["doc"])
        })

    # Methods
    meth_rows = conn.execute(
        "SELECT * FROM methods WHERE class_id = ? AND is_property = 0 ORDER BY name", (row["id"],)
    ).fetchall()
    for mr in meth_rows:
        result["methods"].append({
            "name": mr["name"],
            "desc": mr["desc"] or "",
            "sig": mr["sig"] or "",
            "params": _json.loads(mr["params"]) if mr["params"] else [],
            "returns": mr["returns"] or "",
            "rtype": mr["rtype"] or "",
            "rc": _json.loads(mr["rc"]) if mr["rc"] else [],
            "version": mr["version"] or ""
        })

    # Properties
    prop_rows = conn.execute(
        "SELECT * FROM methods WHERE class_id = ? AND is_property = 1 ORDER BY name", (row["id"],)
    ).fetchall()
    for pr in prop_rows:
        result["properties"].append({
            "name": pr["name"],
            "desc": pr["desc"] or "",
            "rtype": pr["rtype"] or "",
            "version": pr["version"] or ""
        })

    if as_json:
        print(_json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Print formatted
    print(f"=== 类: {result['full_name']} ===")
    if result["module"]:
        print(f"模块: {result['module']}")
    if result["doc"]:
        print(f"描述: {result['doc']}")
    if result["is_nested"]:
        print(f"嵌套类: 是")
    if result["bases"]:
        print(f"继承: {', '.join(result['bases'])}")
    print()

    if result["parent_classes"]:
        print(f"--- 父类 ({len(result['parent_classes'])}) ---")
        for p in result["parent_classes"]:
            mark = "" if p["found"] else " (外部基类)"
            print(f"  {p['name']}{mark}")
        print()

    if result["child_classes"]:
        print(f"--- 子类 ({len(result['child_classes'])}) ---")
        for c in result["child_classes"][:limit]:
            print(f"  {c}")
        if len(result["child_classes"]) > limit:
            print(f"  ... 还有 {len(result['child_classes']) - limit} 个")
        print()

    if result["nested_classes"]:
        print(f"--- 嵌套类 ({len(result['nested_classes'])}) ---")
        for nc in result["nested_classes"][:limit]:
            print(f"  {nc['full_name']}")
            if nc["doc"]:
                print(f"    {nc['doc']}")
        if len(result["nested_classes"]) > limit:
            print(f"  ... 还有 {len(result['nested_classes']) - limit} 个")
        print()

    if result["methods"]:
        print(f"--- 方法 ({len(result['methods'])}) ---")
        for m in result["methods"]:
            print(f"  ▸ {m['name']}")
            if m["sig"]:
                print(f"    签名: {m['sig']}")
            if m["desc"]:
                print(f"    {fmt_desc(m['desc'])}")
            if m["params"]:
                print(f"    参数:")
                print(fmt_params(_json.dumps(m["params"], ensure_ascii=False)))
            if m["returns"] or m["rtype"]:
                rts = f" ({m['rtype']})" if m["rtype"] else ""
                print(f"    返回: {m['returns']}{rts}")
            if m["rc"]:
                print(f"    返回组成:")
                print(fmt_rc(_json.dumps(m["rc"], ensure_ascii=False)))
            if m["version"]:
                print(f"    版本: {m['version']}")
            print()
    else:
        if not result["nested_classes"]:
            print("  (无方法)")

    if result["properties"]:
        print(f"--- 属性 ({len(result['properties'])}) ---")
        for p in result["properties"]:
            print(f"  ◇ {p['name']}")
            if p["rtype"]:
                print(f"    类型: {p['rtype']}")
            if p["desc"]:
                print(f"    {fmt_desc(p['desc'])}")
            if p["version"]:
                print(f"    版本: {p['version']}")
            print()


def cmd_method(conn, args, limit=30, as_json=False):
    """Find methods by name across all classes."""
    cls_filter = None
    if "--cls" in args:
        idx = args.index("--cls")
        if idx + 1 < len(args):
            cls_filter = args[idx + 1]
        args = args[:idx] + args[idx+2:]
    method_name = " ".join(args).strip()

    if not method_name:
        print("Usage: method <name> [--cls <class_name>]")
        return

    if cls_filter:
        rows = conn.execute(
            """SELECT m.*, c.full_name as cls_name, bm25(methods_name_fts) AS score
               FROM methods_name_fts f JOIN methods m ON m.id = f.rowid
               JOIN classes c ON m.class_id = c.id
               WHERE methods_name_fts MATCH ? AND c.full_name LIKE ?
               ORDER BY score, c.full_name, m.name LIMIT ?""",
            (_build_trigram_match(method_name), f"%{cls_filter}%", limit)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT m.*, c.full_name as cls_name, bm25(methods_name_fts) AS score
               FROM methods_name_fts f JOIN methods m ON m.id = f.rowid
               JOIN classes c ON m.class_id = c.id
               WHERE methods_name_fts MATCH ?
               ORDER BY CASE WHEN m.name LIKE ? THEN 0 ELSE 1 END, score, m.name, c.full_name LIMIT ?""",
            (_build_trigram_match(method_name), f"{method_name}%", limit)
        ).fetchall()

    if as_json:
        results = []
        for r in rows:
            results.append({
                "name": r["name"], "class": r["cls_name"],
                "desc": r["desc"] or "", "sig": r["sig"] or "",
                "is_property": bool(r["is_property"]),
                "rtype": r["rtype"] or "", "version": r["version"] or ""
            })
        print(_json.dumps(results, ensure_ascii=False, indent=2))
        return

    if not rows:
        print(f"未找到名称包含 '{method_name}' 的方法。")
        return

    print(f"=== 方法/属性: '{method_name}' ({len(rows)} 条) ===\n")
    for r in rows:
        tag = "[属性]" if r["is_property"] else "[方法]"
        print(f"  {tag} {r['cls_name']}.{r['name']}")
        if r["sig"]:
            print(f"    签名: {r['sig']}")
        if r["desc"]:
            print(f"    {fmt_desc(r['desc'])}")
        if r["rtype"]:
            print(f"    返回类型: {r['rtype']}")
        if r["version"]:
            print(f"    版本: {r['version']}")
        print()


def cmd_verify(conn, args, limit=30, as_json=False):
    """Verify if a name exists as class, method, or property."""
    name = " ".join(args).strip()
    if not name:
        print("Usage: verify <name>")
        return

    result = {"query": name, "found": False, "as_class": None, "as_methods": []}

    # Check class
    cls = conn.execute("SELECT full_name, doc FROM classes WHERE full_name = ? OR short_name = ?", (name, name)).fetchone()
    if cls:
        result["as_class"] = {"full_name": cls["full_name"], "doc": fmt_desc(cls["doc"])}
        result["found"] = True

    # Check methods (exact name)
    meths = conn.execute(
        """SELECT m.name, c.full_name as cls_name, m.is_property, m.desc
           FROM methods m JOIN classes c ON m.class_id = c.id
           WHERE m.name = ? LIMIT 10""", (name,)
    ).fetchall()
    for m in meths:
        result["as_methods"].append({
            "name": m["name"], "class": m["cls_name"],
            "type": "property" if m["is_property"] else "method",
            "desc": fmt_desc(m["desc"])
        })
        result["found"] = True

    if as_json:
        print(_json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not result["found"]:
        print(f"❌ '{name}' 未在 NXOpen Python API 中找到。")
        # Suggest similar
        cmd_suggest(conn, [name], limit=10, as_json=False)
        return

    if result["as_class"]:
        print(f"✅ 类名正确: {result['as_class']['full_name']}")
        if result["as_class"]["doc"]:
            print(f"   {result['as_class']['doc']}")
        print()

    if result["as_methods"]:
        print(f"✅ 方法/属性名正确 ({len(result['as_methods'])} 处):")
        for m in result["as_methods"]:
            tag = "属性" if m["type"] == "property" else "方法"
            print(f"   {m['class']}.{m['name']} [{tag}]")
            if m["desc"]:
                print(f"     {m['desc']}")


def cmd_module(conn, args, limit=50, as_json=False):
    """List all classes in a module."""
    mod_name = " ".join(args).strip()
    if not mod_name:
        print("Usage: module <name>")
        return

    mod = conn.execute("SELECT * FROM modules WHERE name = ?", (mod_name,)).fetchone()
    if not mod:
        mod = conn.execute("SELECT * FROM modules WHERE name LIKE ? LIMIT 1", (f"%{mod_name}%",)).fetchone()

    if not mod:
        print(f"未找到模块 '{mod_name}'。")
        return

    classes = conn.execute(
        """SELECT id, full_name, short_name, doc, is_nested FROM classes
           WHERE module_id = ? AND is_nested = 0 ORDER BY full_name LIMIT ?""",
        (mod["id"], limit)
    ).fetchall()

    all_count = conn.execute("SELECT COUNT(*) FROM classes WHERE module_id = ?", (mod["id"],)).fetchone()[0]
    nested_count = all_count - len(classes)
    meth_count = conn.execute(
        """SELECT COUNT(*) FROM methods m JOIN classes c ON m.class_id = c.id
           WHERE c.module_id = ? AND m.is_property = 0""", (mod["id"],)
    ).fetchone()[0]
    prop_count = conn.execute(
        """SELECT COUNT(*) FROM methods m JOIN classes c ON m.class_id = c.id
           WHERE c.module_id = ? AND m.is_property = 1""", (mod["id"],)
    ).fetchone()[0]

    if as_json:
        result = {
            "module": mod["name"], "doc": mod["doc"] or "",
            "domain": mod["domain"] or "",
            "top_classes": len(classes), "total_classes": all_count,
            "nested_classes": nested_count,
            "methods": meth_count, "properties": prop_count,
            "classes": [{"full_name": c["full_name"], "doc": fmt_desc(c["doc"])} for c in classes]
        }
        print(_json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"=== 模块: {mod['name']} ===")
    if mod["domain"]:
        print(f"功能域: {mod['domain']}")
    if mod["doc"]:
        print(f"描述: {mod['doc']}")
    print(f"顶层类: {len(classes)} | 总类(含嵌套): {all_count} | 方法: {meth_count} | 属性: {prop_count}")
    print()

    for c in classes:
        sub_count = conn.execute("SELECT COUNT(*) FROM classes WHERE parent_class_id = ?", (c["id"],)).fetchone()[0]
        mc = conn.execute("SELECT COUNT(*) FROM methods WHERE class_id = ? AND is_property=0", (c["id"],)).fetchone()[0]
        pc = conn.execute("SELECT COUNT(*) FROM methods WHERE class_id = ? AND is_property=1", (c["id"],)).fetchone()[0]
        info = []
        if sub_count:
            info.append(f"嵌套{sub_count}")
        if mc:
            info.append(f"方法{mc}")
        if pc:
            info.append(f"属性{pc}")
        suffix = f"  [{', '.join(info)}]" if info else ""
        print(f"  {c['full_name']}{suffix}")
        if c["doc"]:
            print(f"    {fmt_desc(c['doc'])}")


def cmd_inherit(conn, args, limit=30, as_json=False):
    """Get inheritance tree (parents and children)."""
    class_name = " ".join(args).strip()
    if not class_name:
        print("Usage: inherit <class_name>")
        return

    row = conn.execute("SELECT * FROM classes WHERE full_name = ? OR short_name = ?", (class_name, class_name)).fetchone()
    if not row:
        print(f"未找到类 '{class_name}'。")
        return

    result = {"class": row["full_name"], "parents": [], "children": []}

    # Parents
    bases = _json.loads(row["bases"]) if row["bases"] else []
    for b in bases:
        parent = conn.execute("SELECT full_name FROM classes WHERE full_name = ?", (b,)).fetchone()
        result["parents"].append({"name": b, "found": parent is not None})

    # Children
    child_rows = conn.execute(
        "SELECT full_name, bases FROM classes WHERE bases LIKE ? LIMIT 200",
        (f'%"{row["full_name"]}"%',)
    ).fetchall()
    for cr in child_rows:
        cb = _json.loads(cr["bases"]) if cr["bases"] else []
        if row["full_name"] in cb:
            result["children"].append(cr["full_name"])

    if as_json:
        print(_json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"=== 继承关系: {result['class']} ===\n")

    if result["parents"]:
        print(f"父类 ({len(result['parents'])}):")
        for p in result["parents"]:
            mark = "✓" if p["found"] else "✗ (外部)"
            print(f"  {mark} {p['name']}")
        print()
    else:
        print("父类: 无\n")

    if result["children"]:
        print(f"子类 ({len(result['children'])}):")
        for c in result["children"][:limit]:
            print(f"  {c}")
        if len(result["children"]) > limit:
            print(f"  ... 还有 {len(result['children']) - limit} 个")
    else:
        print("子类: 无")


def cmd_suggest(conn, args, limit=15, as_json=False):
    """Fuzzy-suggest similar names."""
    name = " ".join(args).strip()
    if not name:
        print("Usage: suggest <name>")
        return

    # Suggest classes (trigram substring + shortest first)
    name_match = _build_trigram_match(name)
    cls_rows = []
    if name_match:
        cls_rows = conn.execute(
            """SELECT c.full_name, c.short_name, bm25(classes_name_fts) AS score
               FROM classes_name_fts f JOIN classes c ON c.id = f.rowid
               WHERE classes_name_fts MATCH ?
               ORDER BY length(c.full_name), score LIMIT ?""", (name_match, limit)
        ).fetchall()

    # Suggest methods (trigram substring, distinct)
    meth_rows = []
    if name_match:
        meth_rows = conn.execute(
            """SELECT DISTINCT m.name FROM methods_name_fts f JOIN methods m ON m.id = f.rowid
               WHERE methods_name_fts MATCH ? ORDER BY length(m.name), m.name LIMIT ?""",
            (name_match, limit)
        ).fetchall()

    if as_json:
        print(_json.dumps({
            "classes": [r["full_name"] for r in cls_rows],
            "methods": [r["name"] for r in meth_rows]
        }, ensure_ascii=False, indent=2))
        return

    if cls_rows:
        print(f"相似类名:")
        for r in cls_rows:
            print(f"  {r['full_name']}")
        print()

    if meth_rows:
        print(f"相似方法名:")
        for r in meth_rows:
            print(f"  {r['name']}")

    if not cls_rows and not meth_rows:
        print(f"未找到与 '{name}' 相似的名称。")


def cmd_modules(conn, args, limit=9999, as_json=False):
    """List all modules."""
    rows = conn.execute("SELECT name, doc FROM modules ORDER BY name").fetchall()
    if as_json:
        print(_json.dumps([{"name": r["name"], "doc": r["doc"] or ""} for r in rows], ensure_ascii=False, indent=2))
        return
    print(f"=== 模块列表 ({len(rows)}) ===\n")
    for r in rows:
        print(f"  {r['name']}")
        if r["doc"]:
            print(f"    {fmt_desc(r['doc'])}")


def cmd_count(conn, args, limit=9999, as_json=False):
    """Show statistics."""
    mod_count = conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]
    cls_count = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    meth_count = conn.execute("SELECT COUNT(*) FROM methods WHERE is_property=0").fetchone()[0]
    prop_count = conn.execute("SELECT COUNT(*) FROM methods WHERE is_property=1").fetchone()[0]
    nested_count = conn.execute("SELECT COUNT(*) FROM classes WHERE is_nested=1").fetchone()[0]

    stats = {
        "modules": mod_count, "classes": cls_count,
        "methods": meth_count, "properties": prop_count,
        "nested_classes": nested_count
    }
    if as_json:
        print(_json.dumps(stats, ensure_ascii=False, indent=2))
        return
    print("=== NXOpen Python API 统计 ===")
    print(f"  模块:     {mod_count}")
    print(f"  类:       {cls_count}")
    print(f"  方法:     {meth_count}")
    print(f"  属性:     {prop_count}")
    print(f"  嵌套类:   {nested_count}")

# ── Batch & NL ────────────────────────────────────────────

def _run_sub(conn, spec):
    """Run a single sub-query spec within batch. Returns dict (without printing)."""
    import io, contextlib
    cmd = spec.get("cmd")
    qargs = spec.get("args", [])
    sub_limit = int(spec.get("limit", 30))
    name = spec.get("name") or cmd
    cur = sqlite3.connect(conn.execute("PRAGMA database_list").fetchone()[2])
    cur.row_factory = sqlite3.Row
    commands = {
        "search": cmd_search, "class": cmd_class, "method": cmd_method,
        "verify": cmd_verify, "module": cmd_module, "inherit": cmd_inherit,
        "suggest": cmd_suggest, "modules": cmd_modules, "count": cmd_count,
    }
    fn = commands.get(cmd)
    if not fn:
        return {"name": name, "error": f"unknown command: {cmd}"}
    sio = io.StringIO()
    with contextlib.redirect_stdout(sio):
        try:
            if cmd == "method" and spec.get("cls"):
                fake = [cmd] + list(qargs) + ["--cls", spec["cls"]]
                saved = sys.argv; sys.argv = fake
                fn(cur, qargs, limit=sub_limit, as_json=True)
                sys.argv = saved
            else:
                fn(cur, qargs, limit=sub_limit, as_json=True)
            out = sio.getvalue().strip()
            try:
                data = _json.loads(out)
            except Exception:
                data = out
        except Exception as e:
            data = {"error": str(e)}
    cur.close()
    return {"name": name, "result": data}


def cmd_batch(conn, args, limit=30, as_json=False):
    """Run multiple sub-queries in one process, return aggregated JSON.

    Usage:
      python nxopen_query.py batch '<json_array>'
      python nxopen_query.py batch -f <file.json>

    Each element: {"name":"...","cmd":"search|class|method|verify|...",
                   "args":[...],"limit":30,"cls":"Body"}
    """
    if not args:
        print('Usage: batch \'[{"cmd":"search","args":["create body"],"limit":10}, ...]\'')
        print('       batch -f <file.json>')
        return
    src = args[0]
    if src == "-f" and len(args) > 1:
        with open(args[1], "r", encoding="utf-8") as f:
            specs = _json.load(f)
    else:
        try:
            specs = _json.loads(src)
        except Exception as e:
            print(f"ERROR: 无法解析 batch JSON: {e}")
            return
    if not isinstance(specs, list):
        specs = [specs]
    out = [_run_sub(conn, spec) for spec in specs]
    print(_json.dumps(out, ensure_ascii=False, indent=2))




# ── Main ──────────────────────────────────────────────────

def main():
    db_path = DEFAULT_DB
    if "--db" in sys.argv:
        idx = sys.argv.index("--db")
        db_path = sys.argv[idx + 1]
        sys.argv.pop(idx)
        sys.argv.pop(idx)

    as_json = False
    if "--json" in sys.argv:
        as_json = True
        sys.argv.remove("--json")

    limit = 30
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        limit = int(sys.argv[idx + 1])
        sys.argv.pop(idx)
        sys.argv.pop(idx)

    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # Remove --cls and its value from args for non-method commands
    if cmd != "method" and "--cls" in args:
        idx = args.index("--cls")
        args = args[:idx] + args[idx+2:]

    conn = get_db(db_path)

    commands = {
        "search": cmd_search,
        "class": cmd_class,
        "method": cmd_method,
        "verify": cmd_verify,
        "module": cmd_module,
        "inherit": cmd_inherit,
        "suggest": cmd_suggest,
        "modules": cmd_modules,
        "count": cmd_count,
        "batch": cmd_batch,
    }

    if cmd in commands:
        commands[cmd](conn, args, limit=limit, as_json=as_json)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)

    conn.close()


if __name__ == "__main__":
    main()
