#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前 PII 门禁：扫描将要公开的静态页面与文档，命中即失败。

用法：
    python scripts/check_pii.py            # 检查 docs/ 与 README 等公开文件
    python scripts/check_pii.py --all      # 连模板、脚本一起检查

规则：
    1. 11 位中国大陆手机号（1[3-9] 开头）
    2. 18 位身份证号
    3. 邮箱地址（允许 example.com 等保留域，以及 noreply 类地址）
    4. 常见真实姓名的"姓名 + 11 位号码"同现组合（本仓库演示数据禁止出现）

命中时以脱敏形式打印（前 3 位 + **** + 后 4 位），不把原文写进日志。
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 默认只检查会对外公开的内容
PUBLIC_GLOBS = ("docs", "README.md", "CHANGELOG.md", "LICENSE")
ALL_GLOBS = ("docs", "templates", "static", "scripts", "app.py", "models.py", "config.py",
             "install.py", "README.md", "CHANGELOG.md", "LICENSE", "部署说明书.md")

SKIP_DIRS = {".git", "packages", "__pycache__", ".github"}
TEXT_EXT = {".html", ".htm", ".md", ".py", ".js", ".css", ".txt", ".csv", ".json", ".yml", ".yaml", ".sql"}

PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
IDCARD = re.compile(r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
SAFE_EMAIL_DOMAINS = ("example.com", "example.org", "users.noreply.github.com", "localhost")

# 演示数据禁止使用的"看起来像真人"的姓名
BANNED_NAMES = ("张伟", "王芳", "李娜", "刘洋", "陈静", "杨帆", "赵敏", "黄磊",
                "周杰", "吴昊", "徐静", "孙丽", "马超", "朱婷", "胡军", "郭涛")


def mask(s):
    if len(s) == 11:
        return s[:3] + "****" + s[-4:]
    if len(s) == 18:
        return s[:6] + "********" + s[-4:]
    if "@" in s:
        name, _, domain = s.partition("@")
        return (name[:2] + "***@" + domain)
    return s[:2] + "***"


def iter_files(targets):
    for t in targets:
        p = os.path.join(ROOT, t)
        if os.path.isfile(p):
            yield p
            continue
        for dp, dn, fn in os.walk(p):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            for f in fn:
                if os.path.splitext(f)[1].lower() in TEXT_EXT:
                    yield os.path.join(dp, f)


def scan():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="连模板与脚本一起检查")
    args = parser.parse_args()

    targets = ALL_GLOBS if args.all else PUBLIC_GLOBS
    problems = []

    for path in iter_files(targets):
        try:
            text = open(path, "r", encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        for i, line in enumerate(text.splitlines(), 1):
            if "pii-safe" in line:
                continue
            for m in PHONE.finditer(line):
                problems.append((rel, i, "手机号", mask(m.group(0))))
            for m in IDCARD.finditer(line):
                problems.append((rel, i, "身份证号", mask(m.group(0))))
            for m in EMAIL.finditer(line):
                if not m.group(0).lower().endswith(SAFE_EMAIL_DOMAINS):
                    problems.append((rel, i, "邮箱", mask(m.group(0))))
            if PHONE.search(line):
                for name in BANNED_NAMES:
                    if name in line:
                        problems.append((rel, i, "姓名+手机号同现", name + " / " + mask(PHONE.search(line).group(0))))

    print("检查范围：" + "、".join(targets))
    if not problems:
        print("PASS 未发现手机号 / 身份证 / 邮箱 / 真实姓名组合，可发布。")
        return 0

    print("FAIL 命中 %d 处，禁止发布：" % len(problems))
    for rel, line, kind, hit in problems:
        print("  %-28s L%-5d [%s] %s" % (rel, line, kind, hit))
    print("\n处置：演示数据请改用 138****0001 这类掩码占位，单位以「某」代替，姓名用张三/李四。")
    print("确属安全的占位值（如导入模板示例行）可在该行加注释 pii-safe 豁免，并在评审中说明理由。")
    return 1


if __name__ == "__main__":
    sys.exit(scan())
