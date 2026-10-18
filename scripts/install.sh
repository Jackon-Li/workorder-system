#!/bin/bash
# ============================================================
# 售后工单管理系统 - 银河麒麟 V10 (ARM64) 安装脚本
# ============================================================
set -e

# 脚本位于 <项目>/scripts/ 下，项目根目录要再往上一层
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "=========================================="
echo "售后工单管理系统 v1.0.0 安装程序"
echo "=========================================="

# 1. 环境检查
echo ""
echo "[1/4] 检查运行环境..."
python3 --version 2>/dev/null || { echo "错误: 未找到 Python3"; exit 1; }
PYVER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [ "$PYVER" != "3.8" ]; then
    echo ""
    echo "警告: 当前 Python 版本为 $PYVER，而 packages/ 里的依赖是按 Python 3.8 (cp38) 下载的。"
    echo "      继续安装大概率会报 'No matching distribution' 或 'not a supported wheel'。"
    echo "      请在有网的同架构机器上执行:"
    echo "        bash scripts/download_packages.sh   # 默认按 3.8 下载"
    echo "      或按本机版本改下载参数后重试。"
    echo ""
    read -p "仍要继续？(y/n): " cont
    [ "$cont" = "y" ] || [ "$cont" = "Y" ] || exit 1
fi

# 2. 安装依赖
echo ""
echo "[2/4] 安装 Python 依赖..."
if [ -d "$PROJECT_DIR/packages" ] && [ "$(ls -A $PROJECT_DIR/packages 2>/dev/null)" ]; then
    echo "检测到离线包目录，进行离线安装..."
    pip3 install --no-index --find-links="$PROJECT_DIR/packages" -r "$PROJECT_DIR/requirements.txt"
else
    echo "未找到离线包，尝试在线安装..."
    pip3 install -r "$PROJECT_DIR/requirements.txt"
fi
python3 -c "import flask, sqlalchemy, flask_sqlalchemy; print('依赖校验通过: Flask', flask.__version__)"
echo "依赖安装完成"

# 3. 初始化数据库
echo ""
echo "[3/4] 初始化数据库..."
cd "$PROJECT_DIR"
python3 -c "
from app import app
from models import db, User, FaultType
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', display_name='管理员', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
    for f in ['硬件故障', '软件故障', '网络故障', '系统故障', '其他']:
        if not FaultType.query.filter_by(name=f).first():
            db.session.add(FaultType(name=f))
    db.session.commit()
    print('数据库初始化完成')
"
echo "数据库初始化完成"

# 4. 可选：安装 systemd 服务
echo ""
echo "[4/4] 可选：安装系统守护服务"
read -p "是否安装开机自启服务？(y/n): " choice
if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
    cat > /etc/systemd/system/ticket-system.service << EOF
[Unit]
Description=售后工单管理系统
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$(which python3) $PROJECT_DIR/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable ticket-system
    systemctl start ticket-system
    echo "服务已启动"
fi

echo ""
echo "=========================================="
echo "安装完成！"
echo "=========================================="
echo "项目目录: $PROJECT_DIR"
echo "数据库: $PROJECT_DIR/db/workorder.db"
echo "登录账号: admin / admin123"
echo "启动命令: cd $PROJECT_DIR && python3 app.py"
echo "访问地址: http://localhost:8000"
echo ""
