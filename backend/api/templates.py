"""
api/templates.py — 任务模板（机构自定义服务流程）

机构定义"美本申请标准流程"等模板（一组任务），实例化到学生 → 生成 milestones + tasks。
无市场 fork/star（那是 Gobob 平台功能）。
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor, db_transaction
from core.id_gen import new_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateItem(BaseModel):
    title: str
    phase: str | None = None
    assignee_type: str = "student"
    offset_days: int = 0
    sort_order: int = 0


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    items: list[TemplateItem] = []


@router.post("")
def create_template(req: TemplateCreate, user: dict = Depends(auth.require_staff),
                    org_id: str = Depends(get_org_id)):
    tid = new_id()
    with db_transaction() as cur:
        cur.execute(
            "INSERT INTO task_templates (id, org_id, name, description, created_by) VALUES (%s,%s,%s,%s,%s)",
            (tid, org_id, req.name, req.description, user.get("member_id")))
        for it in req.items:
            cur.execute(
                "INSERT INTO task_template_items (id, template_id, title, phase, assignee_type, offset_days, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (new_id(), tid, it.title, it.phase, it.assignee_type, it.offset_days, it.sort_order))
    return {"template_id": tid}


@router.get("")
def list_templates(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute(
            """SELECT t.*, (SELECT COUNT(*) FROM task_template_items i WHERE i.template_id=t.id) AS item_count
               FROM task_templates t WHERE t.org_id=%s AND t.is_active=1 ORDER BY t.created_at DESC""",
            (org_id,))
        rows = cur.fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/{template_id}")
def template_detail(template_id: str, user: dict = Depends(auth.require_staff),
                    org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM task_templates WHERE id=%s AND org_id=%s", (template_id, org_id))
        t = cur.fetchone()
        if not t:
            raise HTTPException(404, "模板不存在")
        cur.execute("SELECT * FROM task_template_items WHERE template_id=%s ORDER BY sort_order",
                    (template_id,))
        items = cur.fetchall()
    out = dict(t)
    out["items"] = [dict(i) for i in items]
    return out


class InstantiateReq(BaseModel):
    student_member_id: str
    start_date: str | None = None  # YYYY-MM-DD，默认今天


@router.post("/{template_id}/instantiate")
def instantiate(template_id: str, req: InstantiateReq,
                user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    """把模板实例化成学生的任务列表。"""
    with db_transaction() as cur:
        cur.execute("SELECT * FROM task_templates WHERE id=%s AND org_id=%s", (template_id, org_id))
        tpl = cur.fetchone()
        if not tpl:
            raise HTTPException(404, "模板不存在")
        cur.execute("SELECT * FROM task_template_items WHERE template_id=%s ORDER BY sort_order",
                    (template_id,))
        items = cur.fetchall()
        base = datetime.strptime(req.start_date, "%Y-%m-%d") if req.start_date else datetime.utcnow()
        created = 0
        for it in items:
            due = (base + timedelta(days=it["offset_days"] or 0)).date()
            cur.execute(
                """INSERT INTO tasks (id, org_id, member_id, title, phase, assignee_type, due_date, sort_order)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (new_id(), org_id, req.student_member_id, it["title"], it["phase"],
                 it["assignee_type"], due, it["sort_order"]))
            created += 1
    return {"created_tasks": created, "template": tpl["name"]}
