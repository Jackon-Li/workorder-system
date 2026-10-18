# -*- coding: utf-8 -*-
"""
售后工单管理系统 - 配置文件
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据库
DB_PATH = os.path.join(BASE_DIR, 'db', 'workorder.db')
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# 服务配置
SECRET_KEY = 'ticket-system-secret-key-2026'
HOST = '0.0.0.0'
PORT = 8000
DEBUG = False

# 工单编号前缀
TICKET_PREFIX = 'SG'

# 分页
PAGE_SIZE = 10

# 管理员默认账号
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# 导入模板字段
IMPORT_TEMPLATE_FIELDS = [
    '工单编号', '接收日期', '接收人', '省份', '州市', '区县',
    '用户单位', '联系人', '联系电话', '问题现象', '处理详情',
    '故障类型', '自定义故障类型', '是否需要上门处理', '上门人员',
    '上门日期', '产品序列号', '备注'
]
