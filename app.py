# -*- coding: utf-8 -*-
"""
售后工单管理系统 - 主程序
Python 3.8 + Flask + SQLite3
"""

import os
import sys
import csv
import io
import re
import uuid
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    jsonify, session, send_file, flash, Response
)
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError

from config import (BASE_DIR, SECRET_KEY, DB_PATH, TICKET_PREFIX, PAGE_SIZE,
                    HOST, PORT)
from models import db, init_db, User, Ticket, TicketHistory, FaultType
from yunnan_regions import YUNNAN_REGIONS, get_all_prefectures, get_counties

# ---------------------------------------------------------------------------
# App 工厂
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# SQLite 默认 5 秒锁等待，多人同时录单时容易 database is locked；放宽到 20 秒
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {'timeout': 20},
    'pool_pre_ping': True
}
app.config['JSON_AS_ASCII'] = False
# 导入文件大小上限（10MB），避免异常上传拖垮内存
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

init_db(app)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def generate_serial_no():
    """生成工单编号：SG + 年月日 + 4位序号

    尾号解析放宽：导入的历史编号可能不是纯数字，此时从 1 重新计数，
    不再因为 int('ABCD') 抛异常导致整张工单存不进去。
    """
    today = date.today()
    prefix = f"{TICKET_PREFIX}{today.strftime('%Y%m%d')}"
    last_ticket = Ticket.query.filter(
        Ticket.serial_no.like(f"{prefix}%")
    ).order_by(Ticket.serial_no.desc()).first()
    seq = 0
    if last_ticket:
        tail = last_ticket.serial_no[len(prefix):]
        if tail.isdigit():
            seq = int(tail)
    return f"{prefix}{seq + 1:04d}"


def decode_csv(raw):
    """把上传的 CSV 字节解成文本。

    现场大量文件是 Excel「另存为 CSV」，默认是 GBK/GB18030 而非 UTF-8；
    只认 utf-8-sig 会让用户看到"文件格式错误"却不知道是编码问题。
    """
    for enc in ('utf-8-sig', 'utf-8', 'gb18030'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError('无法识别文件编码，请另存为「CSV UTF-8」后重试')


def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """管理员装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('需要管理员权限', 'danger')
            return redirect(url_for('ticket_list'))
        return f(*args, **kwargs)
    return decorated


def log_history(ticket_id, action, field_name='', old_value='', new_value=''):
    """记录操作历史"""
    operator = session.get('display_name', '') or session.get('username', '')
    history = TicketHistory(
        ticket_id=ticket_id,
        action=action,
        field_name=field_name,
        old_value=str(old_value)[:500],
        new_value=str(new_value)[:500],
        operator=operator
    )
    db.session.add(history)
    db.session.commit()


def get_stats():
    """获取工单统计数据"""
    total = Ticket.query.count()
    pending = Ticket.query.filter_by(status='待处理').count()
    processing = Ticket.query.filter_by(status='处理中').count()
    completed = Ticket.query.filter_by(status='已完成').count()
    closed = Ticket.query.filter_by(status='已关闭').count()
    onsite = Ticket.query.filter_by(need_onsite=True).count()
    completion_rate = round(completed / total * 100, 1) if total > 0 else 0
    return {
        'total': total,
        'pending': pending,
        'processing': processing,
        'completed': completed,
        'closed': closed,
        'onsite': onsite,
        'completion_rate': completion_rate
    }


# ---------------------------------------------------------------------------
# 认证路由
# ---------------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username, is_active=True).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['display_name'] = user.display_name or user.username
            session['is_admin'] = user.is_admin
            flash(f'登录成功，欢迎 {session["display_name"]}', 'success')
            return redirect(url_for('ticket_list'))
        flash('用户名或密码错误', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# 工单 CRUD
# ---------------------------------------------------------------------------
@app.route('/')
@login_required
def index():
    return redirect(url_for('ticket_list'))


@app.route('/tickets')
@login_required
def ticket_list():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    city_filter = request.args.get('city', '')
    search = request.args.get('search', '').strip()

    query = Ticket.query

    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if priority_filter:
        query = query.filter(Ticket.priority == priority_filter)
    if city_filter:
        query = query.filter(Ticket.city == city_filter)
    if search:
        like = f'%{search}%'
        query = query.filter(
            Ticket.serial_no.like(like) |
            Ticket.user_unit.like(like) |
            Ticket.contact_person.like(like) |
            Ticket.contact_phone.like(like) |
            Ticket.problem_desc.like(like)
        )

    query = query.order_by(Ticket.created_at.desc())
    pagination = query.paginate(page=page, per_page=PAGE_SIZE, error_out=False)
    tickets = pagination.items

    prefectures = get_all_prefectures()
    return render_template('ticket_list.html',
                           tickets=tickets,
                           pagination=pagination,
                           prefectures=prefectures,
                           status_filter=status_filter,
                           priority_filter=priority_filter,
                           city_filter=city_filter,
                           search=search,
                           stats=get_stats())


@app.route('/tickets/create', methods=['GET', 'POST'])
@login_required
def ticket_create():
    if request.method == 'POST':
        try:
            receive_date_str = request.form.get('receive_date', '')
            receive_date = datetime.strptime(receive_date_str, '%Y-%m-%d').date() if receive_date_str else date.today()

            onsite_date_str = request.form.get('onsite_date', '')
            onsite_date = None
            if onsite_date_str:
                onsite_date = datetime.strptime(onsite_date_str, '%Y-%m-%d').date()

            # 多人同时新建时可能撞上同一个序号：重新取号重试，最多 5 次
            ticket = None
            for _ in range(5):
                serial_no = generate_serial_no()
                ticket = Ticket(
                    serial_no=serial_no,
                    receive_date=receive_date,
                    receiver=request.form.get('receiver', ''),
                    city=request.form.get('city', ''),
                    county=request.form.get('county', ''),
                    user_unit=request.form.get('user_unit', ''),
                    contact_person=request.form.get('contact_person', ''),
                    contact_phone=request.form.get('contact_phone', ''),
                    problem_desc=request.form.get('problem_desc', ''),
                    solution_detail=request.form.get('solution_detail', ''),
                    fault_type=request.form.get('fault_type', ''),
                    custom_fault_type=request.form.get('custom_fault_type', ''),
                    need_onsite=request.form.get('need_onsite') == 'on',
                    onsite_person=request.form.get('onsite_person', ''),
                    onsite_date=onsite_date,
                    product_sn=request.form.get('product_sn', ''),
                    remark=request.form.get('remark', ''),
                    priority=request.form.get('priority', '中'),
                    status='待处理',
                    created_by=session.get('username', '')
                )
                db.session.add(ticket)
                try:
                    db.session.commit()
                    break
                except IntegrityError:
                    db.session.rollback()
                    ticket = None

            if ticket is None:
                raise RuntimeError('工单编号生成冲突，请重新提交')

            log_history(ticket.id, 'create', '创建工单', '', ticket.serial_no)
            flash(f'工单 {ticket.serial_no} 创建成功', 'success')
            return redirect(url_for('ticket_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败：{str(e)}', 'danger')

    fault_types = FaultType.query.filter_by(is_active=True).all()
    prefectures = get_all_prefectures()
    return render_template('ticket_create.html',
                           fault_types=fault_types,
                           prefectures=prefectures,
                           today=date.today().strftime('%Y-%m-%d'))


@app.route('/tickets/<int:ticket_id>')
@login_required
def ticket_detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    histories = TicketHistory.query.filter_by(ticket_id=ticket_id)\
        .order_by(TicketHistory.created_at.desc()).all()
    return render_template('ticket_detail.html', ticket=ticket, histories=histories)


@app.route('/tickets/<int:ticket_id>/edit', methods=['GET', 'POST'])
@login_required
def ticket_edit(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if request.method == 'POST':
        try:
            fields = [
                'receive_date', 'receiver', 'city', 'county', 'user_unit',
                'contact_person', 'contact_phone', 'problem_desc', 'solution_detail',
                'fault_type', 'custom_fault_type', 'onsite_person', 'product_sn', 'remark', 'priority'
            ]
            for field in fields:
                old_val = getattr(ticket, field, '')
                new_val = request.form.get(field, '')
                if field == 'receive_date' and new_val:
                    try:
                        new_val = datetime.strptime(new_val, '%Y-%m-%d').date()
                    except:
                        continue
                elif field == 'receive_date' and not new_val:
                    continue
                if str(old_val) != str(new_val):
                    setattr(ticket, field, new_val)
                    log_history(ticket.id, 'edit', field, old_val, new_val)

            # need_onsite
            old_onsite = ticket.need_onsite
            new_onsite = request.form.get('need_onsite') == 'on'
            if old_onsite != new_onsite:
                ticket.need_onsite = new_onsite
                log_history(ticket.id, 'edit', 'need_onsite', str(old_onsite), str(new_onsite))

            onsite_date_str = request.form.get('onsite_date', '')
            if onsite_date_str:
                try:
                    ticket.onsite_date = datetime.strptime(onsite_date_str, '%Y-%m-%d').date()
                except:
                    pass

            db.session.commit()
            flash(f'工单 {ticket.serial_no} 更新成功', 'success')
            return redirect(url_for('ticket_detail', ticket_id=ticket.id))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')

    fault_types = FaultType.query.filter_by(is_active=True).all()
    prefectures = get_all_prefectures()
    return render_template('ticket_edit.html',
                           ticket=ticket,
                           fault_types=fault_types,
                           prefectures=prefectures)


@app.route('/tickets/<int:ticket_id>/complete', methods=['POST'])
@login_required
def ticket_complete(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.status in ('已完成', '已关闭'):
        flash('工单已经完成或关闭', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))

    solution = request.form.get('solution_detail', '')
    complete_date_str = request.form.get('completed_at', '')
    try:
        ticket.status = '已完成'
        ticket.solution_detail = solution
        ticket.completed_by = session.get('username', '')
        if complete_date_str:
            ticket.completed_at = datetime.strptime(complete_date_str, '%Y-%m-%dT%H:%M')
        else:
            ticket.completed_at = datetime.now()
        db.session.commit()
        log_history(ticket.id, 'complete', '完成工单', '', ticket.serial_no)
        flash(f'工单 {ticket.serial_no} 已完成', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'完成失败：{str(e)}', 'danger')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))


@app.route('/tickets/<int:ticket_id>/start', methods=['POST'])
@login_required
def ticket_start(ticket_id):
    """开始处理：待处理 → 处理中（表示已有人接手，避免多人重复处理）"""
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.status != '待处理':
        flash('只有「待处理」的工单可以开始处理', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    ticket.status = '处理中'
    db.session.commit()
    log_history(ticket.id, 'start', '开始处理', '待处理', '处理中')
    flash(f'工单 {ticket.serial_no} 已进入处理中', 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))


@app.route('/tickets/<int:ticket_id>/close', methods=['POST'])
@login_required
def ticket_close(ticket_id):
    """关闭：完结归档，或把重复/无效工单作废"""
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.status == '已关闭':
        flash('工单已经关闭', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    old_status = ticket.status
    ticket.status = '已关闭'
    db.session.commit()
    log_history(ticket.id, 'close', '关闭工单', old_status, '已关闭')
    flash(f'工单 {ticket.serial_no} 已关闭', 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))


@app.route('/tickets/<int:ticket_id>/delete', methods=['POST'])
@login_required
def ticket_delete(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    serial_no = ticket.serial_no
    try:
        # 先留一条删除痕迹再删工单：历史记录不随工单消失，
        # 否则"谁在什么时候删了哪张单"永远查不到。
        log_history(ticket.id, 'delete', '删除工单', serial_no, '')
        db.session.delete(ticket)
        db.session.commit()
        flash(f'工单 {serial_no} 已删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败：{str(e)}', 'danger')
    return redirect(url_for('ticket_list'))


@app.route('/tickets/batch_delete', methods=['POST'])
@login_required
def ticket_batch_delete():
    ids = request.form.getlist('ids')
    if not ids:
        flash('请选择要删除的工单', 'warning')
        return redirect(url_for('ticket_list'))
    try:
        count = 0
        for tid in ids:
            ticket = Ticket.query.get(int(tid))
            if ticket:
                log_history(ticket.id, 'delete', '批量删除', ticket.serial_no, '')
                db.session.delete(ticket)
                count += 1
        db.session.commit()
        flash(f'批量删除成功，共删除 {count} 条工单', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'批量删除失败：{str(e)}', 'danger')
    return redirect(url_for('ticket_list'))


# ---------------------------------------------------------------------------
# 数据大屏
# ---------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', prefectures=get_all_prefectures())


@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    start_date = request.args.get('start', '')
    end_date = request.args.get('end', '')
    city = request.args.get('city', '')
    city = request.args.get('city', '')

    query = Ticket.query
    if start_date:
        try:
            query = query.filter(Ticket.receive_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        except:
            pass
    if end_date:
        try:
            query = query.filter(Ticket.receive_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        except:
            pass
    if city:
        query = query.filter(Ticket.city == city)

    tickets = query.all()

    total = len(tickets)
    completed = sum(1 for t in tickets if t.status == '已完成')
    closed = sum(1 for t in tickets if t.status == '已关闭')
    pending = sum(1 for t in tickets if t.status == '待处理')
    processing = sum(1 for t in tickets if t.status == '处理中')
    onsite = sum(1 for t in tickets if t.need_onsite)
    completion_rate = round((completed + closed) / total * 100, 1) if total > 0 else 0

    # 按城市分布
    city_stats = {}
    for t in tickets:
        city_stats[t.city] = city_stats.get(t.city, 0) + 1
    city_data = [{'name': k, 'value': v} for k, v in sorted(city_stats.items(), key=lambda x: -x[1])]

    # 按故障类型分布
    fault_stats = {}
    for t in tickets:
        ft = t.custom_fault_type or t.fault_type or '未分类'
        fault_stats[ft] = fault_stats.get(ft, 0) + 1
    fault_data = [{'name': k, 'value': v} for k, v in sorted(fault_stats.items(), key=lambda x: -x[1])]

    # 月度趋势
    month_stats = {}
    for t in tickets:
        month_key = t.receive_date.strftime('%Y-%m') if t.receive_date else ''
        if month_key:
            if month_key not in month_stats:
                month_stats[month_key] = {'total': 0, 'completed': 0}
            month_stats[month_key]['total'] += 1
            if t.status == '已完成':
                month_stats[month_key]['completed'] += 1
    month_data = [{'month': k, 'total': v['total'], 'completed': v['completed']}
                  for k, v in sorted(month_stats.items())]

    return jsonify({
        'total': total,
        'pending': pending,
        'processing': processing,
        'completed': completed,
        'closed': closed,
        'onsite': onsite,
        'completion_rate': completion_rate,
        'city_data': city_data,
        'fault_data': fault_data,
        'month_data': month_data
    })


# ---------------------------------------------------------------------------
# 用户管理
# ---------------------------------------------------------------------------
@app.route('/users')
@login_required
@admin_required
def user_list():
    users = User.query.order_by(User.id).all()
    return render_template('user_list.html', users=users)


@app.route('/users/create', methods=['POST'])
@login_required
@admin_required
def user_create():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', 'Abcd12345')
    display_name = request.form.get('display_name', '')
    is_admin = request.form.get('is_admin') == 'on'

    if not username:
        flash('用户名不能为空', 'danger')
        return redirect(url_for('user_list'))

    if User.query.filter_by(username=username).first():
        flash('用户名已存在', 'danger')
        return redirect(url_for('user_list'))

    user = User(username=username, display_name=display_name, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'用户 {username} 创建成功，默认密码：Abcd12345', 'success')
    return redirect(url_for('user_list'))


@app.route('/users/<int:user_id>/reset_pwd', methods=['POST'])
@login_required
@admin_required
def user_reset_pwd(user_id):
    user = User.query.get_or_404(user_id)
    user.set_password('Abcd12345')
    db.session.commit()
    flash(f'用户 {user.username} 密码已重置为 Abcd12345', 'success')
    return redirect(url_for('user_list'))


@app.route('/users/<int:user_id>/toggle_active', methods=['POST'])
@login_required
@admin_required
def user_toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session.get('user_id'):
        flash('不能禁用自己', 'danger')
        return redirect(url_for('user_list'))
    user.is_active = not user.is_active
    db.session.commit()
    status = '启用' if user.is_active else '禁用'
    flash(f'用户 {user.username} 已{status}', 'success')
    return redirect(url_for('user_list'))


@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session.get('user_id'):
        flash('不能删除自己', 'danger')
        return redirect(url_for('user_list'))
    db.session.delete(user)
    db.session.commit()
    flash(f'用户 {user.username} 已删除', 'success')
    return redirect(url_for('user_list'))


# ---------------------------------------------------------------------------
# 故障类型管理
# ---------------------------------------------------------------------------
@app.route('/api/fault_types')
@login_required
def api_fault_types():
    types = FaultType.query.filter_by(is_active=True).all()
    return jsonify([t.to_dict() for t in types])


@app.route('/api/fault_types/create', methods=['POST'])
@login_required
def api_fault_types_create():
    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'error': '名称不能为空'}), 400
    if FaultType.query.filter_by(name=name).first():
        return jsonify({'error': '故障类型已存在'}), 400
    ft = FaultType(name=name)
    db.session.add(ft)
    db.session.commit()
    return jsonify(ft.to_dict())


# ---------------------------------------------------------------------------
# 区域 API
# ---------------------------------------------------------------------------
@app.route('/api/regions/prefectures')
@login_required
def api_prefectures():
    return jsonify(get_all_prefectures())


@app.route('/api/regions/counties/<prefecture>')
@login_required
def api_counties(prefecture):
    return jsonify(get_counties(prefecture))


# ---------------------------------------------------------------------------
# Excel 导入导出
# ---------------------------------------------------------------------------
@app.route('/export')
@login_required
def ticket_export():
    """导出工单为 CSV"""
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    city_filter = request.args.get('city', '')
    search = request.args.get('search', '').strip()

    query = Ticket.query
    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if priority_filter:
        query = query.filter(Ticket.priority == priority_filter)
    if city_filter:
        query = query.filter(Ticket.city == city_filter)
    if search:
        like = f'%{search}%'
        query = query.filter(
            Ticket.serial_no.like(like) |
            Ticket.user_unit.like(like) |
            Ticket.contact_person.like(like)
        )
    query = query.order_by(Ticket.created_at.desc())
    tickets = query.all()

    output = io.StringIO()
    output.write('\ufeff')  # BOM for Excel
    writer = csv.writer(output)
    headers = [
        '工单编号', '接收日期', '接收人', '省份', '州市', '区县',
        '用户单位', '联系人', '联系电话', '问题现象', '处理详情',
        '故障类型', '自定义故障类型', '是否需要上门处理',
        '上门人员', '上门日期', '产品序列号', '备注',
        '优先级', '状态', '创建时间', '完成时间'
    ]
    writer.writerow(headers)
    for t in tickets:
        writer.writerow([
            t.serial_no,
            t.receive_date.strftime('%Y-%m-%d') if t.receive_date else '',
            t.receiver,
            t.province,
            t.city,
            t.county,
            t.user_unit,
            t.contact_person,
            t.contact_phone,
            t.problem_desc,
            t.solution_detail,
            t.fault_type,
            t.custom_fault_type,
            '是' if t.need_onsite else '否',
            t.onsite_person,
            t.onsite_date.strftime('%Y-%m-%d') if t.onsite_date else '',
            t.product_sn,
            t.remark,
            t.priority,
            t.status,
            t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '',
            t.completed_at.strftime('%Y-%m-%d %H:%M') if t.completed_at else ''
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8-sig',
        headers={'Content-Disposition': f'attachment; filename=工单导出_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'}
    )


@app.route('/export/template')
@login_required
def export_template():
    """下载导入模板"""
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    headers = [
        '工单编号', '接收日期', '接收人', '省份', '州市', '区县',
        '用户单位', '联系人', '联系电话', '问题现象', '处理详情',
        '故障类型', '自定义故障类型', '是否需要上门处理',
        '上门人员', '上门日期', '产品序列号', '备注'
    ]
    writer.writerow(headers)
    # 示例行
    writer.writerow([
        '', '2026-04-01', '', '云南省', '昆明市', '五华区',
        '示例科技有限公司', '张三', '13888888888',  # pii-safe 导入模板占位值，全同数字，非真实号码
        '设备无法正常启动，屏幕无显示', '已更换电源模块，设备恢复正常',
        '硬件故障', '', '否', '', '', 'SN12345678', '请优先处理'
    ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8-sig',
        headers={'Content-Disposition': 'attachment; filename=工单导入模板.csv'}
    )


@app.route('/import', methods=['GET', 'POST'])
@login_required
def ticket_import():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('请选择文件', 'danger')
            return redirect(url_for('ticket_import'))

        try:
            content = decode_csv(file.read())
            reader = csv.DictReader(io.StringIO(content))
            success = 0
            errors = []
            for row_num, row in enumerate(reader, start=2):
                try:
                    city = row.get('州市', '').strip()
                    county = row.get('区县', '').strip()

                    receive_date_str = row.get('接收日期', '').strip()
                    receive_date = date.today()
                    if receive_date_str:
                        receive_date = datetime.strptime(receive_date_str[:10], '%Y-%m-%d').date()

                    onsite_date_str = row.get('上门日期', '').strip()
                    onsite_date = None
                    if onsite_date_str:
                        onsite_date = datetime.strptime(onsite_date_str[:10], '%Y-%m-%d').date()

                    user_unit = row.get('用户单位', '').strip()
                    contact_person = row.get('联系人', '').strip()
                    contact_phone = row.get('联系电话', '').strip()
                    problem_desc = row.get('问题现象', '').strip()
                    missing = [n for n, v in (('用户单位', user_unit), ('联系人', contact_person),
                                              ('联系电话', contact_phone), ('问题现象', problem_desc)) if not v]
                    if missing:
                        raise ValueError(f'缺少必填项：{"、".join(missing)}')

                    serial_no = row.get('工单编号', '').strip() or generate_serial_no()
                    # 编号重复不再静默换号（会把用户原来的编号弄丢），直接指出是哪一行
                    if Ticket.query.filter_by(serial_no=serial_no).first():
                        raise ValueError(f'工单编号 {serial_no} 已存在，请检查是否重复导入')

                    custom_ft = row.get('自定义故障类型', '').strip()
                    if custom_ft:
                        if not FaultType.query.filter_by(name=custom_ft).first():
                            db.session.add(FaultType(name=custom_ft))

                    ticket = Ticket(
                        serial_no=serial_no,
                        receive_date=receive_date,
                        receiver=row.get('接收人', '').strip(),
                        city=city,
                        county=county,
                        user_unit=user_unit,
                        contact_person=contact_person,
                        contact_phone=contact_phone,
                        problem_desc=problem_desc,
                        solution_detail=row.get('处理详情', '').strip(),
                        fault_type=row.get('故障类型', '').strip(),
                        custom_fault_type=custom_ft,
                        need_onsite=row.get('是否需要上门处理', '').strip() == '是',
                        onsite_person=row.get('上门人员', '').strip(),
                        onsite_date=onsite_date,
                        product_sn=row.get('产品序列号', '').strip(),
                        remark=row.get('备注', '').strip(),
                        priority='中',
                        status='待处理',
                        created_by=session.get('username', '')
                    )
                    db.session.add(ticket)
                    db.session.commit()
                    log_history(ticket.id, 'import', '导入工单', '', serial_no)
                    success += 1
                except Exception as e:
                    db.session.rollback()
                    errors.append(f'第{row_num}行：{str(e)}')

            msg = f'导入完成，成功 {success} 条'
            if errors:
                msg += f'，失败 {len(errors)} 条\n' + '\n'.join(errors[:5])
            flash(msg, 'success' if not errors else 'warning')
        except Exception as e:
            flash(f'导入失败：文件格式错误 - {str(e)}', 'danger')

        return redirect(url_for('ticket_list'))

    return render_template('import.html')


# ---------------------------------------------------------------------------
# 操作日志
# ---------------------------------------------------------------------------
@app.route('/histories')
@login_required
def ticket_histories():
    page = request.args.get('page', 1, type=int)
    ticket_id = request.args.get('ticket_id', type=int)

    query = TicketHistory.query
    if ticket_id:
        query = query.filter(TicketHistory.ticket_id == ticket_id)

    query = query.order_by(TicketHistory.created_at.desc())
    pagination = query.paginate(page=page, per_page=50, error_out=False)

    return render_template('histories.html',
                           histories=pagination.items,
                           pagination=pagination)


@app.context_processor
def inject_now():
    return {'now': datetime.now}


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.upper() in ('GBK', 'GB2312', 'GB18030'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("[*] 售后工单管理系统启动中...")
    print(f"   数据库: {DB_PATH}")
    print(f"   访问地址: http://localhost:{PORT}")
    print("   默认账号: admin / admin123")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
