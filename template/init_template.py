#!/usr/bin/env python3
"""从模板初始化新项目

用法：
    python init_template.py                    # 交互式
    python init_template.py --name my-project  # 非交互式
"""
import argparse
import re
import secrets
import shutil
import sys
from pathlib import Path

# 需要替换占位符的文件（相对路径）及对应的占位符
PLACEHOLDER_FILES = [
    "pyproject.toml",
    "alembic.ini",
    "core/config.py",
    ".env.example",
    "README.md",
    "main.py",
    "tests/conftest.py",
]


def collect_info(args) -> dict:
    """收集项目信息，优先用命令行参数，缺失的交互式询问"""
    values = {}
    mapping = [
        ("project_name", "项目名称（英文，用作目录名和包名）", True),
        ("db_name", "数据库名", True),
        ("db_user", "数据库用户名", False, "root"),
        ("db_password", "数据库密码", True),
        ("db_host", "数据库主机", False, "localhost"),
        ("db_port", "数据库端口", False, "3306"),
    ]
    for key, prompt, required, *default in mapping:
        arg_val = getattr(args, key, None)
        if arg_val:
            values[key] = arg_val
        elif required or not default:
            values[key] = input(f"{prompt}: ").strip()
        else:
            # 可选字段带默认值：交互时允许回车用默认；非交互（EOF）直接用默认
            try:
                values[key] = input(f"{prompt} [{default[0]}]: ").strip() or default[0]
            except EOFError:
                values[key] = default[0]
    # 自动生成 SECRET_KEY（32 位随机 hex）
    values["secret_key"] = secrets.token_hex(32)
    return values


def build_replacer(values: dict):
    """构建替换函数"""
    mapping = {
        "{{project_name}}": values["project_name"],
        "{{db_name}}": values["db_name"],
        "{{db_user}}": values["db_user"],
        "{{db_password}}": values["db_password"],
        "{{db_host}}": values["db_host"],
        "{{db_port}}": values["db_port"],
        "{{secret_key}}": values["secret_key"],
    }
    pattern = re.compile("|".join(re.escape(k) for k in mapping.keys()))

    def replacer(text: str) -> str:
        return pattern.sub(lambda m: mapping[m.group(0)], text)

    return replacer


def main():
    parser = argparse.ArgumentParser(description="从模板初始化新项目")
    parser.add_argument("--name", dest="project_name", help="项目名称")
    parser.add_argument("--db", dest="db_name", help="数据库名")
    parser.add_argument("--db-user", dest="db_user", help="数据库用户名")
    parser.add_argument("--db-pass", dest="db_password", help="数据库密码")
    parser.add_argument("--db-host", dest="db_host", help="数据库主机")
    parser.add_argument("--db-port", dest="db_port", help="数据库端口")
    parser.add_argument("--target", default=".", help="输出目录（默认当前目录下的 <project_name>/）")
    args = parser.parse_args()

    template_dir = Path(__file__).parent.resolve()
    values = collect_info(args)
    replacer = build_replacer(values)

    target_name = values["project_name"].replace(" ", "-").lower()
    target_dir = Path(args.target) / target_name
    if target_dir.exists():
        print(f"目录已存在：{target_dir}")
        sys.exit(1)

    print(f"\n初始化项目：{target_name}")
    print(f"   目标目录：{target_dir}\n")

    # 1. 复制整个 template 目录（排除自身和 __pycache__）
    shutil.copytree(
        template_dir,
        target_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
    )

    # 2. 删除模板自身的初始化脚本（不复制到新项目）
    init_script = target_dir / "init_template.py"
    if init_script.exists():
        init_script.unlink()

    # 3. 替换占位符
    replaced = 0
    for rel_path in PLACEHOLDER_FILES:
        file_path = target_dir / rel_path
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        new_content = replacer(content)
        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")
            replaced += 1
            print(f"   已配置：{rel_path}")

    # 4. 生成 .env（从 .env.example 复制并填入真实值）
    env_example = target_dir / ".env.example"
    env_file = target_dir / ".env"
    if env_example.exists():
        env_content = env_example.read_text(encoding="utf-8")
        env_content = replacer(env_content)
        env_file.write_text(env_content, encoding="utf-8")
        print(f"   已生成：.env")

    # 5. 输出后续步骤
    print(f"\n{'='*50}")
    print(f"项目 {target_name} 初始化完成！")
    print(f"\n后续步骤：")
    print(f"   cd {target_name}")
    print(f"   python -m venv .venv && .venv\\Scripts\\activate")
    print(f"   pip install -e \".[test]\"")
    print(f"   # 手动建库：mysql -u {values['db_user']} -p -e \"CREATE DATABASE {values['db_name']} CHARACTER SET utf8mb4;\"")
    print(f"   alembic revision --autogenerate -m \"init\"")
    print(f"   alembic upgrade head")
    print(f"   uvicorn main:app --reload")
    print(f"\n   # 运行测试")
    print(f"   pytest tests/ -v")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
