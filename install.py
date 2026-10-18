#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
售后工单管理系统 - 一键安装脚本
在银河麒麟 V10 (ARM64) 上离线安装
"""

import os
import sys
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGES_DIR = os.path.join(BASE_DIR, 'packages')
REQUIREMENTS = os.path.join(BASE_DIR, 'requirements.txt')
SYSTEMD_SERVICE = """
[Unit]
Description=售后工单管理系统
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={workdir}
ExecStart={python} {app}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def check_environment():
    """检查运行环境"""
    print("=" * 50)
    print("售后工单管理系统 - 环境检查")
    print("=" * 50)

    # Python 版本
    py_version = sys.version_info
    if py_version.major == 3 and py_version.minor >= 8:
        print(f"[✓] Python 版本: {sys.version}")
    else:
        print(f"[✗] Python 版本不符: {sys.version}，需要 Python 3.8+")
        return False

    # 磁盘空间（简单检查）
    usage = shutil.disk_usage(BASE_DIR)
    free_gb = usage.free / (1024 ** 3)
    if free_gb >= 2:
        print(f"[✓] 磁盘空间: {free_gb:.1f}GB 可用")
    else:
        print(f"[✗] 磁盘空间不足: {free_gb:.1f}GB，需要至少 2GB")
        return False

    print("[✓] 环境检查通过")
    return True


def install_dependencies():
    """离线安装 Python 依赖"""
    print("\n" + "=" * 50)
    print("安装 Python 依赖包")
    print("=" * 50)

    packages = os.path.join(PACKAGES_DIR)
    if not os.path.exists(packages) or not os.listdir(packages):
        print("[!] 未找到离线包目录，尝试在线安装...")
        cmd = [sys.executable, '-m', 'pip', 'install', '-r', REQUIREMENTS]
    else:
        print(f"[*] 正在从 {packages} 离线安装...")
        cmd = [sys.executable, '-m', 'pip', 'install', '--no-index',
               '--find-links', packages, '-r', REQUIREMENTS]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("[✓] 依赖安装成功")
        return True
    else:
        print(f"[✗] 安装失败:\n{result.stderr}")
        return False


def init_database():
    """初始化数据库"""
    print("\n" + "=" * 50)
    print("初始化数据库")
    print("=" * 50)

    db_dir = os.path.join(BASE_DIR, 'db')
    os.makedirs(db_dir, exist_ok=True)

    # 通过导入 app 创建数据库
    sys.path.insert(0, BASE_DIR)
    from app import app
    from models import db, User, FaultType

    with app.app_context():
        db.create_all()
        print("[✓] 数据库表创建完成")

        # 创建默认管理员
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', display_name='管理员', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("[✓] 默认管理员已创建 (admin / admin123)")

        # 创建默认故障类型
        for fname in ['硬件故障', '软件故障', '网络故障', '系统故障', '其他']:
            if not FaultType.query.filter_by(name=fname).first():
                db.session.add(FaultType(name=fname))
        db.session.commit()
        print("[✓] 默认故障类型已创建")

    print("[✓] 数据库初始化完成")
    return True


def install_systemd():
    """安装 systemd 服务"""
    print("\n" + "=" * 50)
    print("安装系统服务（可选）")
    print("=" * 50)

    python_path = sys.executable
    app_path = os.path.join(BASE_DIR, 'app.py')
    service_content = SYSTEMD_SERVICE.format(
        workdir=BASE_DIR,
        python=python_path,
        app=app_path
    )

    service_path = '/etc/systemd/system/ticket-system.service'
    try:
        with open(service_path, 'w') as f:
            f.write(service_content)
        subprocess.run(['systemctl', 'daemon-reload'])
        subprocess.run(['systemctl', 'enable', 'ticket-system'])
        print(f"[✓] 服务已安装: {service_path}")
        print("[*] 启动命令: systemctl start ticket-system")
        print("[*] 查看状态: systemctl status ticket-system")
        return True
    except PermissionError:
        print("[!] 无权限安装系统服务（需要 root 权限）")
        print(f"[*] 手动启动: cd {BASE_DIR} && {python_path} app.py")
        return False


def main():
    """主安装流程"""
    print("\n售后工单管理系统 v1.0.0 安装程序")
    print("目标系统: 银河麒麟 V10 (ARM64)")
    print()

    if not check_environment():
        sys.exit(1)

    if not install_dependencies():
        sys.exit(1)

    if not init_database():
        sys.exit(1)

    install_systemd()

    print("\n" + "=" * 50)
    print("安装完成！")
    print("=" * 50)
    print(f"项目目录: {BASE_DIR}")
    print(f"数据库: {os.path.join(BASE_DIR, 'db', 'workorder.db')}")
    print(f"登录账号: admin / admin123")
    print(f"启动命令: python3 app.py")
    print(f"访问地址: http://localhost:8000")
    print()


if __name__ == '__main__':
    main()
