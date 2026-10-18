# -*- coding: utf-8 -*-
"""
售后工单管理系统 - 数据库模型
使用 Flask-SQLAlchemy ORM
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
import hashlib

db = SQLAlchemy()


class User(db.Model):
    """用户表"""
    __tablename__ = 'auth_user'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(64), default='')
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''
        }


class FaultType(db.Model):
    """故障类型表"""
    __tablename__ = 'fault_type'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'is_active': self.is_active
        }


class Ticket(db.Model):
    """工单主表"""
    __tablename__ = 'ticket'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    serial_no = db.Column(db.String(32), unique=True, nullable=False, index=True)
    receive_date = db.Column(db.Date, nullable=False)
    receiver = db.Column(db.String(64), default='')
    province = db.Column(db.String(32), default='云南省')
    city = db.Column(db.String(32), default='')
    county = db.Column(db.String(32), default='')
    user_unit = db.Column(db.String(256), nullable=False)
    contact_person = db.Column(db.String(64), nullable=False)
    contact_phone = db.Column(db.String(16), nullable=False)
    problem_desc = db.Column(db.Text, nullable=False)
    solution_detail = db.Column(db.Text, default='')
    fault_type = db.Column(db.String(128), default='')
    custom_fault_type = db.Column(db.String(128), default='')
    need_onsite = db.Column(db.Boolean, default=False)
    onsite_person = db.Column(db.String(64), default='')
    onsite_date = db.Column(db.Date, nullable=True)
    product_sn = db.Column(db.String(128), default='')
    remark = db.Column(db.Text, default='')
    priority = db.Column(db.String(16), default='中')  # 低/中/高/紧急
    status = db.Column(db.String(16), default='待处理')  # 待处理/处理中/已完成/已关闭
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    completed_at = db.Column(db.DateTime, nullable=True)
    completed_by = db.Column(db.String(64), default='')
    created_by = db.Column(db.String(64), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'serial_no': self.serial_no,
            'receive_date': self.receive_date.strftime('%Y-%m-%d') if self.receive_date else '',
            'receiver': self.receiver,
            'province': self.province,
            'city': self.city,
            'county': self.county,
            'user_unit': self.user_unit,
            'contact_person': self.contact_person,
            'contact_phone': self.contact_phone,
            'problem_desc': self.problem_desc,
            'solution_detail': self.solution_detail,
            'fault_type': self.fault_type,
            'custom_fault_type': self.custom_fault_type,
            'need_onsite': self.need_onsite,
            'onsite_person': self.onsite_person,
            'onsite_date': self.onsite_date.strftime('%Y-%m-%d') if self.onsite_date else '',
            'product_sn': self.product_sn,
            'remark': self.remark,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M') if self.completed_at else '',
            'completed_by': self.completed_by,
            'created_by': self.created_by
        }


class TicketHistory(db.Model):
    """操作历史表"""
    __tablename__ = 'ticket_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False, index=True)
    action = db.Column(db.String(32), nullable=False)  # create/edit/delete/complete/close
    field_name = db.Column(db.String(64), default='')
    old_value = db.Column(db.Text, default='')
    new_value = db.Column(db.Text, default='')
    operator = db.Column(db.String(64), default='')
    created_at = db.Column(db.DateTime, default=datetime.now)

    ticket = db.relationship(
        'Ticket',
        # 删工单时不回写子表外键、也不级联删历史：
        # 历史记录要独立留存，否则"谁删了哪张单"事后查不到
        backref=db.backref('histories', lazy='dynamic', passive_deletes=True)
    )

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'action': self.action,
            'field_name': self.field_name,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'operator': self.operator,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''
        }


def init_db(app):
    """初始化数据库"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        # WAL：读写互不阻塞，多人同时录单时不会因为一个查询把写入挡住
        # （journal_mode 是写进数据库文件的，设置一次即长期生效）
        db.session.execute(text('PRAGMA journal_mode=WAL'))
        db.session.execute(text('PRAGMA synchronous=NORMAL'))
        db.session.commit()
        # 创建默认管理员
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', display_name='管理员', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
        # 创建默认故障类型
        default_faults = ['硬件故障', '软件故障', '网络故障', '系统故障', '其他']
        for fname in default_faults:
            if not FaultType.query.filter_by(name=fname).first():
                db.session.add(FaultType(name=fname))
        db.session.commit()
