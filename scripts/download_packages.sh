#!/bin/bash
# ============================================================
# 售后工单管理系统 - ARM64 离线依赖下载脚本
# 在一台「同架构 + 有网」的机器上执行，产出可直接拷进内网的 packages/
#
# 关键点：必须用 --python-version 38 指定目标解释器版本。
# 不指定的话 pip 会按「本机 Python 版本」挑包，拿到最新 Flask 3.x，
# 到麒麟自带的 Python 3.8 上会被 Requires-Python 直接拒绝。
# ============================================================
set -e

# 脚本位于 <项目>/scripts/ 下，项目根目录要再往上一层
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PACKAGES_DIR="$SCRIPT_DIR/packages"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
MIRROR="${MIRROR:-https://pypi.tuna.tsinghua.edu.cn/simple}"

echo "=========================================="
echo "ARM64 / Python 3.8 离线依赖包下载"
echo "=========================================="
echo "目标目录: $PACKAGES_DIR"
echo "索引源  : $MIRROR"
echo ""

mkdir -p "$PACKAGES_DIR"
rm -f "$PACKAGES_DIR"/*.whl

echo "[1/1] 下载 aarch64 + cp38 轮子（含子依赖，不编译源码）..."
pip3 download \
    --dest "$PACKAGES_DIR" \
    --platform manylinux2014_aarch64 \
    --python-version 38 \
    --implementation cp \
    --abi cp38 \
    --only-binary=:all: \
    -r "$REQUIREMENTS" \
    -i "$MIRROR"

echo ""
echo "=========================================="
echo "下载完成"
echo "=========================================="
echo "包总数: $(ls -1 "$PACKAGES_DIR" | wc -l)"
ls -lh "$PACKAGES_DIR"
echo ""
echo "现场离线安装："
echo "  pip3 install --no-index --find-links=$PACKAGES_DIR -r $REQUIREMENTS"
echo ""
echo "装完建议核验一次（应输出全部 OK）："
echo "  python3 -c \"import flask, sqlalchemy, flask_sqlalchemy; print('OK', flask.__version__)\""
echo ""
