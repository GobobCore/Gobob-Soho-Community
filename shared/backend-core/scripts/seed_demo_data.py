#!/usr/bin/env python3
"""
seed_demo_data.py - Gobob SOHO 社区版 dev 演示站测试数据灌入
=====================================================

在 gobob_soho_community 库灌入一个完整业务闭环的测试数据:
用户(顾问/学生/家长) + 流程(线索->签约->服务->交付->沟通->通知)

用法:
  python3 seed_demo_data.py                 # 灌入 demo 数据(默认追加)
  python3 seed_demo_data.py --reset         # 先清 demo 数据再灌
  python3 seed_demo_data.py --reset --all  # 全清, 只保留 admin

数据前提:
  * 已在 gobob_soho_community 跑 schema.sql + seed.sql
  * 至少有 1 个 org (systemd 启 backend 时自动 bootstrap)
  * 至少有 admin 账号 (bootstrap 自动建)

设计: 测试数据加 tag demo 便于 reset 清理.
"""

import argparse
import os
import sys
import uuid
from datetime import date, datetime, timedelta

import pymysql

DEFAULT_DB = dict(
    host=os.environ.get('SOHO_MYSQL_HOST', '127.0.0.1'),
    port=int(os.environ.get('SOHO_MYSQL_PORT', '3306')),
    user=os.environ.get('SOHO_MYSQL_USER', 'root'),
    password=os.environ.get('SOHO_MYSQL_PASS', 'Abccd27366'),
    database=os.environ.get('SOHO_MYSQL_DB', 'gobob_soho_community'),
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=False,
)

DEMO_PASSWORD_HASH = 'pbkdf2_sha256$100000$demo$'  # 演示用, 后端认证需替换


def nid(prefix=''):
    return prefix + uuid.uuid4().hex[:16 - len(prefix)]


def dt(days_ago=0):
    return (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')


def d(days_ago=0):
    return (date.today() - timedelta(days=days_ago)).isoformat()


def get_org_admin(conn):
    cur = conn.cursor()
    cur.execute('SELECT id FROM orgs LIMIT 1')
    org_row = cur.fetchone()
    cur.execute('SELECT id FROM accounts WHERE username = %s', ('admin',))
    admin_row = cur.fetchone()
    if not org_row or not admin_row:
        print('! org/admin 不存在. 请先启动 backend 让 bootstrap 建好')
        sys.exit(1)
    return org_row['id'], admin_row['id']


def reset_demo(conn):
    cur = conn.cursor()
    # 反向依赖顺序删
    for sql in [
        "DELETE FROM notifications WHERE type='system' AND title LIKE '新线索分配'",
        "DELETE FROM notifications WHERE type='system' AND title LIKE '流失线索%'",
        "DELETE FROM notifications WHERE title LIKE '系统通知'",
        "DELETE FROM notifications WHERE title LIKE '合同签订%' OR title LIKE '签约提醒%' OR title LIKE '文书已接收%' OR title LIKE '顾问更换%' OR title LIKE '任务即将到期%'",
        'DELETE FROM messages WHERE conversation_id IS NOT NULL',
        "DELETE FROM deliverables WHERE file_url LIKE '%demo%'",
        "DELETE FROM tasks WHERE phase IN ('selection','exam','writing','interview','visa','preparation')",
        "DELETE FROM milestones WHERE title IN ('选校定位','标准化考试','文书写作','面试准备','签证申请','入学准备')",
        "DELETE FROM service_assignments WHERE handover_note IS NOT NULL OR started_at > DATE_SUB(NOW(), INTERVAL 90 DAY)",
        "DELETE FROM contract_payments WHERE pay_method='transfer'",
        "DELETE FROM contracts WHERE contract_no LIKE 'CT-%'",
        "DELETE FROM leads WHERE JSON_CONTAINS(tags, '\"demo\"')",
        "DELETE FROM applications WHERE school_name IN ('Massachusetts Institute of Technology','Stanford University','Harvard University','Carnegie Mellon University')",
        "DELETE FROM member_relationships WHERE rel_type='parent_of'",
    ]:
        try:
            cur.execute(sql)
        except Exception as e:
            print('  warn reset: ' + sql[:60] + '... -> ' + str(e))
    # demo 用户
    cur.execute(
        'DELETE FROM accounts WHERE username IN (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        ('li_teacher', 'wang_teacher', 'zhang_teacher',
         'alice_li', 'bob_wang', 'carol_zhang', 'david_liu',
         'alice_mom', 'bob_dad'),
    )
    cur.execute(
        'DELETE FROM members WHERE name IN (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        ('李明华', '王晓燕', '张佳琪',
         '李美华', '王子昂', '张思琪', '刘奕辰',
         '李母', '王父',
         '虚拟学生-A', '虚拟学生-B', '虚拟学生-C'),
    )
    conn.commit()
    print('  OK reset')


def seed_users(conn, org_id):
    cur = conn.cursor()
    advisors_data = [
        ('li_teacher', '李明华', '顾问总监', '升学规划'),
        ('wang_teacher', '王晓燕', '高级顾问', '美本申请'),
        ('zhang_teacher', '张佳琪', '顾问', '英联邦申请'),
    ]
    advisor_ids = []
    for username, name, title, specialty in advisors_data:
        cur.execute('SELECT id FROM accounts WHERE username=%s', (username,))
        existing = cur.fetchone()
        if existing:
            acc_id = existing['id']
        else:
            acc_id = nid()
            cur.execute(
                'INSERT INTO accounts (id, username, password_hash, org_id) VALUES (%s, %s, %s, %s)',
                (acc_id, username, DEMO_PASSWORD_HASH + uuid.uuid4().hex[:32], org_id),
            )
        cur.execute('SELECT id FROM members WHERE name=%s AND role=%s AND org_id=%s',
                    (name, 'advisor', org_id))
        existing = cur.fetchone()
        if existing:
            member_id = existing['id']
        else:
            member_id = nid()
            cur.execute(
                'INSERT INTO members (id, org_id, account_id, name, role, phone, email, wechat, title, specialty, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)',
                (member_id, org_id, acc_id, name, 'advisor',
                 '13900000' + uuid.uuid4().hex[:4],
                 username + '@demo.com',
                 'wx_' + username,
                 title, specialty),
            )
        advisor_ids.append(member_id)

    students_data = [
        ('alice_li', '李美华', 'alice.li@demo.com', '13800001001', '北京四中', 3.85, '美本 Top30'),
        ('bob_wang', '王子昂', 'bob.wang@demo.com', '13800001002', '上海中学', 3.72, '英本 G5'),
        ('carol_zhang', '张思琪', 'carol.zhang@demo.com', '13800001003', '深圳外国语', 3.91, '美本 Top10'),
        ('david_liu', '刘奕辰', 'david.liu@demo.com', '13800001004', '南京外国语', 3.55, '美研 Top30'),
    ]
    student_ids = []
    for username, name, email, phone, school, gpa, target in students_data:
        cur.execute('SELECT id FROM accounts WHERE username=%s', (username,))
        existing = cur.fetchone()
        if existing:
            acc_id = existing['id']
        else:
            acc_id = nid()
            cur.execute(
                'INSERT INTO accounts (id, username, password_hash, org_id) VALUES (%s, %s, %s, %s)',
                (acc_id, username, DEMO_PASSWORD_HASH + uuid.uuid4().hex[:32], org_id),
            )
        cur.execute('SELECT id FROM members WHERE name=%s AND role=%s AND org_id=%s',
                    (name, 'student', org_id))
        existing = cur.fetchone()
        if existing:
            member_id = existing['id']
        else:
            member_id = nid()
            cur.execute(
                'INSERT INTO members (id, org_id, account_id, name, role, phone, email, wechat, title, specialty, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)',
                (member_id, org_id, acc_id, name, 'student', phone, email,
                 'wx_' + username,
                 school + ' 应届',
                 'GPA ' + str(gpa) + ', ' + target),
            )
        student_ids.append(member_id)

    parents_data = [
        ('alice_mom', '李母', 'alice.li.parent@demo.com', '13900002001', student_ids[0]),
        ('bob_dad', '王父', 'bob.wang.parent@demo.com', '13900002002', student_ids[1]),
    ]
    parent_ids = []
    for username, name, email, phone, student_id in parents_data:
        cur.execute('SELECT id FROM accounts WHERE username=%s', (username,))
        existing = cur.fetchone()
        if existing:
            acc_id = existing['id']
        else:
            acc_id = nid()
            cur.execute(
                'INSERT INTO accounts (id, username, password_hash, org_id) VALUES (%s, %s, %s, %s)',
                (acc_id, username, DEMO_PASSWORD_HASH + uuid.uuid4().hex[:32], org_id),
            )
        cur.execute('SELECT id FROM members WHERE name=%s AND role=%s AND org_id=%s',
                    (name, 'parent', org_id))
        existing = cur.fetchone()
        if existing:
            member_id = existing['id']
        else:
            member_id = nid()
            cur.execute(
                'INSERT INTO members (id, org_id, account_id, name, role, phone, email, wechat, title, specialty, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)',
                (member_id, org_id, acc_id, name, 'parent', phone, email,
                 'wx_' + username,
                 '家长', ''),
            )
        parent_ids.append(member_id)

        cur.execute('SELECT 1 FROM member_relationships WHERE from_member_id=%s AND to_member_id=%s',
                    (member_id, student_id))
        if not cur.fetchone():
            cur.execute(
                'INSERT INTO member_relationships (id, org_id, from_member_id, to_member_id, rel_type) VALUES (%s, %s, %s, %s, %s)',
                (nid(), org_id, member_id, student_id, 'parent_of'),
            )

    # 3 个虚拟学生
    virtual_names = ['虚拟学生-A', '虚拟学生-B', '虚拟学生-C']
    virtual_ids = []
    for vs_name in virtual_names:
        cur.execute('SELECT id FROM members WHERE name=%s AND is_virtual=1 AND org_id=%s',
                    (vs_name, org_id))
        existing = cur.fetchone()
        if existing:
            virtual_ids.append(existing['id'])
        else:
            member_id = nid()
            cur.execute(
                'INSERT INTO members (id, org_id, account_id, name, role, is_virtual, is_active) VALUES (%s, %s, NULL, %s, %s, 1, 1)',
                (member_id, org_id, vs_name, 'student'),
            )
            virtual_ids.append(member_id)

    conn.commit()
    print('  OK 3 advisors + 4 students + 2 parents + 3 virtual students')
    return advisor_ids, student_ids, parent_ids, virtual_ids


def seed_leads(conn, org_id, advisor_ids, student_ids):
    cur = conn.cursor()

    insert_real_lead = (
        'INSERT INTO leads '
        '(lead_id, org_id, student_name, student_email, student_phone, current_school, '
        'gpa, gpa_scale, target_countries, target_degrees, target_year, source, '
        'status, member_id, assigned_advisor_id, contacted_at, created_at, updated_at, tags) '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
    )

    real_leads = [
        (student_ids[0], advisor_ids[1], 'converted', 60, '智能评估'),
        (student_ids[1], advisor_ids[2], 'converted', 45, '讲座'),
        (student_ids[2], advisor_ids[1], 'contacted', 3, '智能评估'),
        (student_ids[3], advisor_ids[0], 'new', 1, '转介绍'),
    ]
    lead_ids = []
    for student_id, advisor_id, status, days_ago, source in real_leads:
        cur.execute('SELECT name, email FROM members WHERE id=%s', (student_id,))
        s = cur.fetchone()
        lead_id = nid('ld')
        cur.execute(insert_real_lead, (
            lead_id, org_id, s['name'], s['email'], '13800001001', '北京四中',
            3.85, '4.0', '["US"]', '["bachelor"]', 2027, source, status,
            student_id, advisor_id,
            dt(days_ago) if days_ago > 0 else None,
            dt(days_ago), dt(days_ago),
            '["demo"]',
        ))
        lead_ids.append(lead_id)

    insert_virtual_lead = (
        'INSERT INTO leads '
        '(lead_id, org_id, student_name, student_email, student_phone, student_grade, '
        'current_school, gpa, gpa_scale, target_countries, target_degrees, target_year, '
        'source, status, assigned_advisor_id, contacted_at, last_contact_at, '
        'converted_at, created_at, updated_at, tags) '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
    )

    virtual_lead_specs = [
        ('李一帆', '高三', '人大附中', 3.92, ['US', 'UK'], '智能评估', 'contacted', 0, 7),
        ('陈思琪', '高二', '华东师大二附中', 3.78, ['US'], '转介绍', 'contacted', 1, 5),
        ('张子墨', '高三', '成都七中', 3.65, ['UK', 'CA'], '讲座', 'new', 2, 2),
        ('王浩然', '高三', '衡水中学', 3.95, ['US'], '智能评估', 'lost', 0, 30),
        ('赵雨萱', '高二', '湖南师大附中', 3.42, ['AU'], '广告', 'lost', 1, 20),
        ('刘心怡', '高三', '西安交通大学附中', 3.88, ['US'], '智能评估', 'recycled', 2, 14),
        ('周博文', '高三', '哈尔滨三中', 3.71, ['US', 'UK'], '转介绍', 'converted', 1, 50),
    ]
    for (name, grade, school, gpa, countries, source, status, advisor_idx, days_ago) in virtual_lead_specs:
        lead_id = nid('ld')
        cur.execute(insert_virtual_lead, (
            lead_id, org_id, name, uuid.uuid4().hex[:6] + '@demo.com',
            '138' + uuid.uuid4().hex[:8], grade, school, gpa, '4.0',
            '["' + '","'.join(countries) + '"]', '["bachelor"]', 2027,
            source, status, advisor_ids[advisor_idx],
            dt(days_ago) if days_ago >= 0 else None,
            dt(max(days_ago - 1, 0)) if status in ('contacted', 'converted') else None,
            dt(days_ago) if status == 'converted' else None,
            dt(days_ago), dt(days_ago),
            '["demo"]',
        ))
        lead_ids.append(lead_id)

    conn.commit()
    print('  OK 10 leads (4 real + 6 virtual, all statuses)')
    return lead_ids


def seed_contracts(conn, org_id, student_ids, lead_ids, advisor_ids):
    cur = conn.cursor()
    cur.execute("SELECT code FROM service_modules ORDER BY sort_order LIMIT 3")
    rows = cur.fetchall()
    mod_codes = [r['code'] for r in rows[:3]] or ['mod_selection', 'mod_application', 'mod_visa']

    contracts = [
        (student_ids[0], lead_ids[0], advisor_ids[1], 'active', 55,
         [mod_codes[0], mod_codes[1]], 58000),
        (student_ids[1], lead_ids[1], advisor_ids[2], 'active', 40,
         [mod_codes[0], mod_codes[1], mod_codes[2]], 82000),
        (student_ids[2], None, advisor_ids[1], 'active', 5,
         [mod_codes[0]], 28000),
        (student_ids[3], None, advisor_ids[0], 'active', 1,
         [mod_codes[0]], 18000),
    ]
    for student_id, lead_id, advisor_id, status, days_ago, mods, amount in contracts:
        contract_id = nid('ct')
        cur.execute(
            'INSERT INTO contracts (id, org_id, contract_no, student_member_id, lead_id, modules, '
            'total_amount, signed_date, service_start, service_end, status, created_by, created_at, updated_at) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (contract_id, org_id, 'CT-' + uuid.uuid4().hex[:8].upper(),
             student_id, lead_id, str(mods).replace("'", '"'),
             amount, d(days_ago), d(days_ago - 5),
             d(days_ago + 180), status, advisor_id, dt(days_ago), dt(days_ago)),
        )
        cur.execute(
            'INSERT INTO contract_payments (id, org_id, contract_id, amount, paid_at, pay_method, created_at) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (nid('pay'), org_id, contract_id, amount // 2,
             d(days_ago - 3), 'transfer', dt(days_ago - 3)),
        )

    conn.commit()
    print('  OK 4 contracts + 4 payments')


def seed_assignments(conn, org_id, student_ids, advisor_ids):
    cur = conn.cursor()
    phases = ['selection', 'exam', 'writing', 'interview', 'visa']
    for i, student_id in enumerate(student_ids[:4]):
        cur.execute(
            'INSERT INTO service_assignments (id, org_id, student_member_id, advisor_member_id, phase, status, started_at) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (nid(), org_id, student_id, advisor_ids[i % 3], 'selection', 'active', dt(50)),
        )
        if i == 1:
            # bob 从王老师换到张老师
            cur.execute(
                'INSERT INTO service_assignments (id, org_id, student_member_id, advisor_member_id, phase, status, '
                'transferred_to, handover_note, started_at, completed_at) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                (nid(), org_id, student_id, advisor_ids[0], 'exam', 'transferred',
                 advisor_ids[2], '学生目标转向英联邦, 张老师更擅长', dt(40), dt(35)),
            )
        for phase in phases[1:]:
            cur.execute(
                'INSERT INTO service_assignments (id, org_id, student_member_id, advisor_member_id, phase, status, started_at) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (nid(), org_id, student_id, advisor_ids[i % 3], phase, 'active', dt(30)),
            )
    conn.commit()
    print('  OK 4 students * 5 phases (含 1 个 handover 演示)')


def seed_milestones_tasks(conn, org_id, student_ids):
    """milestones 和 tasks 都是 tasks 表, 用 category 区分.

    milestones 用 phase 当 category 标记 (每个学生 6 个里程碑任务).
    普通 tasks 15 个不同状态.
    """
    cur = conn.cursor()
    milestone_specs = [
        ('选校定位', 'selection', 30),
        ('标准化考试', 'exam', 60),
        ('文书写作', 'writing', 90),
        ('面试准备', 'interview', 120),
        ('签证申请', 'visa', 170),
        ('入学准备', 'preparation', 200),
    ]
    for student_id in student_ids[:4]:
        for sort, (title, phase, days_to_complete) in enumerate(milestone_specs):
            cur.execute(
                'INSERT INTO tasks (id, org_id, member_id, milestone_id, title, description, phase, '
                'assignee_type, due_date, status, sort_order, completed_at, created_at, updated_at) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                (nid('ms'), org_id, student_id, 'milestone_' + phase,
                 title, '这是 ' + title + ' 里程碑的样例描述 (demo)',
                 phase, 'advisor',
                 d(days_to_complete), 'pending', sort,
                 None, dt(60), dt(60)),
            )

    task_specs = [
        ('整理高中成绩单和活动列表', 'selection', 'done', 50, 'student'),
        ('初步选校 10 所', 'selection', 'doing', 3, 'advisor'),
        ('最终选校 6 所 + 安全学校', 'selection', 'todo', 0, 'advisor'),
        ('TOEFL 报名 + 第 1 次考试', 'exam', 'done', 40, 'student'),
        ('IELTS 报名 + 准备', 'exam', 'doing', 2, 'student'),
        ('TOEFL 二刷目标 100+', 'exam', 'todo', 0, 'student'),
        ('写主文书初稿 650 字', 'writing', 'done', 30, 'student'),
        ('顾问审稿 + 修改', 'writing', 'doing', 5, 'advisor'),
        ('Why School 文书 5 所', 'writing', 'todo', 0, 'student'),
        ('准备 Common 面试问题', 'interview', 'todo', 0, 'student'),
        ('校友面试官 1v1 模拟', 'interview', 'todo', 0, 'advisor'),
        ('I-20 表格填写 + 签字', 'visa', 'todo', 0, 'student'),
        ('SEVIS 费缴纳', 'visa', 'todo', 0, 'student'),
        ('DS-160 表格填写', 'visa', 'todo', 0, 'student'),
        ('大使馆面签预约', 'visa', 'todo', 0, 'student'),
    ]
    for i, (title, phase, status, days_offset, assignee) in enumerate(task_specs):
        student_idx = i % 3
        student_id = student_ids[student_idx]
        cur.execute(
            'INSERT INTO tasks (id, org_id, member_id, title, phase, assignee_type, due_date, status, sort_order, completed_at, created_at, updated_at) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (nid(), org_id, student_id, title, phase, assignee,
             d(days_offset) if days_offset >= 0 else d(0),
             status, i,
             dt(days_offset) if status == 'done' else None,
             dt(60), dt(60)),
        )
    conn.commit()
    print('  OK 6 milestones + 15 tasks (per student)')


def seed_deliverables(conn, org_id, student_ids, advisor_ids):
    cur = conn.cursor()
    docs = [
        ('主文书初稿 v1', 'main_essay_v1.txt', 'draft'),
        ('主文书 v2 (顾问反馈)', 'main_essay_v2.txt', 'revised'),
        ('Why MIT 文书', 'why_mit.txt', 'in_review'),
        ('Why Stanford 文书', 'why_stanford.txt', 'accepted'),
    ]
    for i, (title, filename, status) in enumerate(docs):
        student_id = student_ids[i % 4]
        advisor_id = advisor_ids[i % 3]
        submitted_at = dt(20) if status == 'accepted' else dt(5) if status == 'in_review' else dt(2)
        cur.execute(
            'INSERT INTO deliverables (id, org_id, student_member_id, advisor_member_id, '
            'title, module_code, status, file_url, content, submitted_at, created_at, updated_at) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (nid(), org_id, student_id, advisor_id,
             title, 'mod_writing', status,
             '/uploads/demo/' + filename,
             '# ' + title + '\n\n这是 demo 样例内容 (省略).',
             submitted_at, dt(20), dt(2)),
        )
    conn.commit()
    print('  OK 4 deliverables (draft/revised/in_review/accepted)')


def seed_messages(conn, org_id, student_ids, advisor_ids, parent_ids):
    cur = conn.cursor()
    messages = [
        (student_ids[0], advisor_ids[1], '王老师, 主文书 v2 您看完后能给我一些建议吗?'),
        (advisor_ids[1], student_ids[0], 'alice, 我看完了. 整体故事很棒, 但开头可以更抓人.'),
        (student_ids[1], advisor_ids[2], '张老师, 面试时间能约下周二吗?'),
        (advisor_ids[2], student_ids[1], 'bob, 周二下午 3 点 OK.'),
        (parent_ids[0], advisor_ids[1], '王老师您好, alice 最近压力大, 想了解下进度.'),
        (advisor_ids[1], parent_ids[0], '李母您好, alice 进度领先, 选校已定 6 所.'),
    ]
    for sender_id, receiver_id, content in messages:
        cur.execute(
            'INSERT INTO messages (id, org_id, conversation_id, sender_member_id, receiver_member_id, content, is_read, created_at) '
            'VALUES (%s, %s, %s, %s, %s, %s, 1, %s)',
            (nid(), org_id, nid('c'), sender_id, receiver_id, content, dt(3)),
        )
    conn.commit()
    print('  OK 6 messages (student<->advisor + parent<->advisor)')


def seed_applications(conn, org_id, student_ids):
    cur = conn.cursor()
    schools = [
        ('Massachusetts Institute of Technology', 'Computer Science', 60),
        ('Stanford University', 'Computer Science', 70),
        ('Harvard University', 'Computer Science', 80),
        ('Carnegie Mellon University', 'Computer Science', 90),
    ]
    for i, (school, program, days_to_deadline) in enumerate(schools):
        student_id = student_ids[i % 4]
        cur.execute(
            'INSERT INTO applications (id, org_id, member_id, school_name, program_name, degree, status, deadline) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
            (nid(), org_id, student_id, school, program, 'bachelor', 'preparing',
             d(days_to_deadline)),
        )
    conn.commit()
    print('  OK 4 applications (MIT/Stanford/Harvard/CMU)')


def seed_notifications(conn, org_id, student_ids, advisor_ids):
    cur = conn.cursor()
    notifs = [
        ('新线索分配', '您有一条新线索待跟进: 张子墨 (智能评估来源)', student_ids[2]),
        ('任务即将到期', '您有一个任务 \"最终选校 6 所\" 将于 3 天后到期', student_ids[2]),
        ('合同签订成功', 'alice_li 已签订 美本全套申请 服务 (¥58,000)', student_ids[0]),
        ('签约提醒', 'david_liu 服务包 (¥18,000) 服务期到 2027-04-01', student_ids[3]),
        ('文书已接收', 'alice_li 提交了 主文书 v2 等待审阅', advisor_ids[1]),
        ('顾问更换', 'bob 的 exam 阶段顾问已更换为张老师', student_ids[1]),
        ('流失线索提醒', '赵雨萱 (广告来源) 14 天未跟进, 进入流失池', advisor_ids[0]),
        ('系统通知', 'Gobob Data API Key 配额剩余 8000 次, 请关注用量', advisor_ids[0]),
    ]
    for title, content, member_id in notifs:
        cur.execute(
            'INSERT INTO notifications (id, org_id, member_id, title, content, type, is_read, created_at) '
            'VALUES (%s, %s, %s, %s, %s, %s, 0, %s)',
            (nid(), org_id, member_id, title, content, 'system', dt(1)),
        )
    conn.commit()
    print('  OK 8 notifications')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reset', action='store_true', help='清掉原 demo 数据再灌')
    parser.add_argument('--all', action='store_true', help='(跟 --reset 一起) 全库清空, 只留 admin')
    args = parser.parse_args()

    conn = pymysql.connect(**DEFAULT_DB)
    org_id, admin_id = get_org_admin(conn)
    print('=== Gobob SOHO Community Demo Data ===')
    print('  DB: ' + DEFAULT_DB['database'])
    print('  org: ' + org_id)
    print('  admin: ' + admin_id)
    print()

    if args.reset:
        print('[1/2] Reset old demo data...')
        reset_demo(conn)

    cur = conn.cursor()
    cur.execute('SELECT 1 FROM members WHERE name IN (%s,%s,%s) LIMIT 1', ('李明华', '王晓燕', '张佳琪'))
    if cur.fetchone() and not args.reset:
        print('! Demo 数据已存在. 用 --reset 重置后重跑')
        sys.exit(0)

    print('[2/2] Seeding demo data...')
    advisor_ids, student_ids, parent_ids, virtual_ids = seed_users(conn, org_id)
    lead_ids = seed_leads(conn, org_id, advisor_ids, student_ids)
    seed_contracts(conn, org_id, student_ids, lead_ids, advisor_ids)
    seed_assignments(conn, org_id, student_ids, advisor_ids)
    seed_milestones_tasks(conn, org_id, student_ids)
    seed_deliverables(conn, org_id, student_ids, advisor_ids)
    seed_messages(conn, org_id, student_ids, advisor_ids, parent_ids)
    seed_applications(conn, org_id, student_ids)
    seed_notifications(conn, org_id, student_ids, advisor_ids)

    print()
    print('=== 完成 ===')
    print('浏览器访问 http://localhost:19013 登录 admin/Admin#2026x 查看')


if __name__ == '__main__':
    main()