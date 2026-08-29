# -*- coding: utf-8 -*-
"""
compress.py — JSON 文件压缩/解压工具

提供 JSON 文件的 gzip 压缩与解压功能，供 parse_pyi.py 和 gen_js.py 使用。
压缩格式为 .json.gz，压缩率约 93%（47MB → ~3.5MB）。

用法（命令行）:
    # 压缩
    python scripts/compress.py compress <input.json> [<output.json.gz>]

    # 解压
    python scripts/compress.py decompress <input.json.gz> [<output.json>]

用法（作为模块导入）:
    from compress import compress_file, decompress_file
    compress_file("data/nxopen_structure.json")       # → .json.gz
    decompress_file("data/nxopen_structure.json.gz")   # → .json
"""
import gzip
import json
import os
import sys
import shutil


def compress_file(input_path, output_path=None):
    """将 JSON 文件压缩为 gzip 格式。

    参数:
        input_path:  输入 JSON 文件路径
        output_path: 输出 .gz 文件路径（可选，默认在输入路径后加 .gz）

    返回:
        输出文件路径
    """
    if output_path is None:
        output_path = input_path + ".gz"

    with open(input_path, "rb") as f_in:
        with gzip.open(output_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    in_size = os.path.getsize(input_path) / 1024 / 1024
    out_size = os.path.getsize(output_path) / 1024 / 1024
    ratio = (1 - out_size / in_size) * 100 if in_size > 0 else 0
    print(f"Compressed: {input_path} ({in_size:.1f}MB) → {output_path} ({out_size:.1f}MB, {ratio:.0f}% smaller)")
    return output_path


def decompress_file(input_path, output_path=None):
    """将 gzip 压缩的 JSON 文件解压。

    参数:
        input_path:  输入 .gz 文件路径
        output_path: 输出 JSON 文件路径（可选，默认去掉 .gz 后缀）

    返回:
        输出文件路径
    """
    if output_path is None:
        if input_path.endswith(".gz"):
            output_path = input_path[:-3]
        else:
            output_path = input_path + ".json"

    with gzip.open(input_path, "rb") as f_in:
        with open(output_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    in_size = os.path.getsize(input_path) / 1024 / 1024
    out_size = os.path.getsize(output_path) / 1024 / 1024
    print(f"Decompressed: {input_path} ({in_size:.1f}MB) → {output_path} ({out_size:.1f}MB)")
    return output_path


def load_json_from_gz(gz_path):
    """直接从 gzip 压缩文件加载 JSON 数据（不解压到磁盘）。

    参数:
        gz_path: .gz 文件路径

    返回:
        解析后的 Python 对象（list / dict）
    """
    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        return json.load(f)


def main():
    """命令行入口。"""
    if len(sys.argv) < 3:
        print("用法:")
        print("  python scripts/compress.py compress <input.json> [<output.json.gz>]")
        print("  python scripts/compress.py decompress <input.json.gz> [<output.json>]")
        sys.exit(1)

    action = sys.argv[1]
    input_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    if action == "compress":
        if not os.path.exists(input_path):
            print(f"ERROR: 文件不存在: {input_path}")
            sys.exit(1)
        compress_file(input_path, output_path)
    elif action == "decompress":
        if not os.path.exists(input_path):
            print(f"ERROR: 文件不存在: {input_path}")
            sys.exit(1)
        decompress_file(input_path, output_path)
    else:
        print(f"ERROR: 未知操作: {action}（应为 compress 或 decompress）")
        sys.exit(1)


if __name__ == "__main__":
    main()
