from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
from sqlalchemy import func, or_

from app.models import (
    ClusterResource,
    DatastoreResource,
    HostResource,
    SyncRun,
    VCenterSnapshot,
    VirtualMachine,
    db,
)
from app.vcenter import InventorySnapshot, collect_inventory

VM_COLUMNS = [
    ("虚拟机名", "name"),
    ("CPU核数", "cpu_cores"),
    ("内存大小(GB)", "memory_gb"),
    ("已置备磁盘空间(GB)", "provisioned_disk_gb"),
    ("IP地址", "ip_address"),
    ("操作系统版本", "os_version"),
    ("管理员", "administrator"),
    ("一级部门", "primary_department"),
    ("二级部门", "secondary_department"),
    ("创建日期", "creation_date"),
    ("描述", "description"),
]


def latest_snapshot() -> VCenterSnapshot | None:
    return VCenterSnapshot.query.order_by(VCenterSnapshot.captured_at.desc()).first()


def save_inventory(inventory: InventorySnapshot) -> VCenterSnapshot:
    snapshot = VCenterSnapshot(
        vcenter_name=inventory.vcenter_name,
        vcenter_version=inventory.vcenter_version,
        cpu_total_cores=inventory.cpu_total_cores,
        cpu_used_cores=inventory.cpu_used_cores,
        memory_total_gb=inventory.memory_total_gb,
        memory_used_gb=inventory.memory_used_gb,
        vm_count=len(inventory.vms),
    )
    db.session.add(snapshot)
    db.session.flush()

    for cluster in inventory.clusters:
        db.session.add(ClusterResource(snapshot_id=snapshot.id, **cluster.__dict__))
    for cluster_name, hosts in inventory.hosts.items():
        for host in hosts:
            db.session.add(HostResource(snapshot_id=snapshot.id, cluster_name=cluster_name, **host.__dict__))
    for datastore in inventory.datastores:
        db.session.add(DatastoreResource(snapshot_id=snapshot.id, **datastore.__dict__))
    for vm in inventory.vms:
        db.session.add(VirtualMachine(snapshot_id=snapshot.id, **vm.__dict__))

    db.session.commit()
    return snapshot


def sync_from_vcenter() -> SyncRun:
    run = SyncRun(status="running")
    db.session.add(run)
    db.session.commit()
    try:
        inventory = collect_inventory()
        snapshot = save_inventory(inventory)
        run.status = "success"
        run.message = f"同步完成，snapshot_id={snapshot.id}，虚拟机数量={snapshot.vm_count}。"
    except Exception as exc:
        db.session.rollback()
        run = db.session.get(SyncRun, run.id) or SyncRun(status="failed")
        run.status = "failed"
        run.message = str(exc)
    run.finished_at = datetime.utcnow()
    db.session.add(run)
    db.session.commit()
    return run


def _vm_base_query(snapshot_id: int | None = None):
    snapshot = latest_snapshot() if snapshot_id is None else db.session.get(VCenterSnapshot, snapshot_id)
    if snapshot is None:
        return None, VirtualMachine.query.filter(False)
    return snapshot, VirtualMachine.query.filter(VirtualMachine.snapshot_id == snapshot.id)


def vm_query_from_filters(filters: dict):
    snapshot_id = int(filters.get("snapshot_id") or 0) or None
    snapshot, query = _vm_base_query(snapshot_id)
    group = filters.get("group")
    value = filters.get("value", "")
    if group == "os":
        query = query.filter(VirtualMachine.os_version == value)
    elif group == "year":
        year = int(value)
        query = query.filter(
            VirtualMachine.creation_date >= date(year, 1, 1),
            VirtualMachine.creation_date <= date(year, 12, 31),
        )
    elif group == "month":
        year, month = [int(part) for part in value.split("-")]
        start = date(year, month, 1)
        end = date(year + (month // 12), (month % 12) + 1, 1) - timedelta(days=1)
        query = query.filter(VirtualMachine.creation_date >= start, VirtualMachine.creation_date <= end)
    elif group == "primary_department":
        query = query.filter(VirtualMachine.primary_department == value)
    elif group == "secondary_department":
        query = query.filter(VirtualMachine.secondary_department == value)
    keyword = filters.get("keyword")
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                VirtualMachine.name.like(like),
                VirtualMachine.ip_address.like(like),
                VirtualMachine.administrator.like(like),
                VirtualMachine.description.like(like),
            )
        )
    return snapshot, query.order_by(VirtualMachine.name.asc())


def aggregate_dashboard(snapshot_id: int | None = None) -> dict:
    snapshot = latest_snapshot() if snapshot_id is None else db.session.get(VCenterSnapshot, snapshot_id)
    if snapshot is None:
        return {"snapshot": None}

    vm_q = VirtualMachine.query.filter(VirtualMachine.snapshot_id == snapshot.id)
    now = date.today()
    five_years = [now.year - offset for offset in range(4, -1, -1)]
    months = []
    cursor = date(now.year, now.month, 1)
    for _ in range(6):
        months.append(cursor)
        cursor = date(cursor.year - 1, 12, 1) if cursor.month == 1 else date(cursor.year, cursor.month - 1, 1)
    months = list(reversed(months))

    def pack_rows(rows, name_key="name"):
        return [
            {
                name_key: row[0] or "未知",
                "vm_count": int(row[1] or 0),
                "cpu_cores": int(row[2] or 0),
                "memory_gb": round(float(row[3] or 0), 2),
            }
            for row in rows
        ]

    os_rows = (
        db.session.query(
            VirtualMachine.os_version,
            func.count(VirtualMachine.id),
            func.sum(VirtualMachine.cpu_cores),
            func.sum(VirtualMachine.memory_gb),
        )
        .filter(VirtualMachine.snapshot_id == snapshot.id)
        .group_by(VirtualMachine.os_version)
        .order_by(func.count(VirtualMachine.id).desc())
        .all()
    )
    primary_rows = (
        db.session.query(
            VirtualMachine.primary_department,
            func.count(VirtualMachine.id),
            func.sum(VirtualMachine.cpu_cores),
            func.sum(VirtualMachine.memory_gb),
        )
        .filter(VirtualMachine.snapshot_id == snapshot.id)
        .group_by(VirtualMachine.primary_department)
        .order_by(func.count(VirtualMachine.id).desc())
        .all()
    )
    secondary_rows = (
        db.session.query(
            VirtualMachine.secondary_department,
            func.count(VirtualMachine.id),
            func.sum(VirtualMachine.cpu_cores),
            func.sum(VirtualMachine.memory_gb),
        )
        .filter(VirtualMachine.snapshot_id == snapshot.id)
        .group_by(VirtualMachine.secondary_department)
        .order_by(func.count(VirtualMachine.id).desc())
        .all()
    )

    yearly = []
    for year in five_years:
        rows = vm_q.filter(
            VirtualMachine.creation_date >= date(year, 1, 1),
            VirtualMachine.creation_date <= date(year, 12, 31),
        )
        yearly.append(
            {
                "name": str(year),
                "vm_count": rows.count(),
                "cpu_cores": int(rows.with_entities(func.sum(VirtualMachine.cpu_cores)).scalar() or 0),
                "memory_gb": round(float(rows.with_entities(func.sum(VirtualMachine.memory_gb)).scalar() or 0), 2),
            }
        )

    monthly = []
    for month_start in months:
        next_month = date(month_start.year + (month_start.month // 12), (month_start.month % 12) + 1, 1)
        rows = vm_q.filter(
            VirtualMachine.creation_date >= month_start,
            VirtualMachine.creation_date < next_month,
        )
        monthly.append(
            {
                "name": month_start.strftime("%Y-%m"),
                "vm_count": rows.count(),
                "cpu_cores": int(rows.with_entities(func.sum(VirtualMachine.cpu_cores)).scalar() or 0),
                "memory_gb": round(float(rows.with_entities(func.sum(VirtualMachine.memory_gb)).scalar() or 0), 2),
            }
        )

    return {
        "snapshot": snapshot,
        "clusters": ClusterResource.query.filter_by(snapshot_id=snapshot.id).order_by(ClusterResource.name).all(),
        "datastores": DatastoreResource.query.filter_by(snapshot_id=snapshot.id).order_by(DatastoreResource.used_tb.desc()).all(),
        "os_groups": pack_rows(os_rows),
        "yearly": yearly,
        "monthly": monthly,
        "primary_departments": pack_rows(primary_rows),
        "secondary_departments": pack_rows(secondary_rows),
        "last_sync": SyncRun.query.order_by(SyncRun.started_at.desc()).first(),
    }


def vm_rows_for_export(query) -> BytesIO:
    data = []
    for vm in query.all():
        data.append({title: getattr(vm, attr) for title, attr in VM_COLUMNS})
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(data).to_excel(writer, index=False, sheet_name="虚拟机明细")
    output.seek(0)
    return output
