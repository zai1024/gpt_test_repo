from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, send_file, url_for

from app.models import HostResource, VirtualMachine
from app.services import aggregate_dashboard, sync_from_vcenter, vm_query_from_filters, vm_rows_for_export

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    data = aggregate_dashboard()
    return render_template("index.html", data=data)


@bp.get("/api/dashboard")
def dashboard_api():
    data = aggregate_dashboard()
    snapshot = data.get("snapshot")
    if snapshot is None:
        return jsonify({"snapshot": None})
    return jsonify(
        {
            "snapshot": {
                "id": snapshot.id,
                "captured_at": snapshot.captured_at.isoformat(),
                "vcenter_name": snapshot.vcenter_name,
                "vcenter_version": snapshot.vcenter_version,
                "cpu_total_cores": snapshot.cpu_total_cores,
                "cpu_used_cores": snapshot.cpu_used_cores,
                "memory_total_gb": snapshot.memory_total_gb,
                "memory_used_gb": snapshot.memory_used_gb,
                "vm_count": snapshot.vm_count,
            },
            "clusters": [row_to_dict(item) for item in data["clusters"]],
            "datastores": [row_to_dict(item) for item in data["datastores"]],
            "os_groups": data["os_groups"],
            "yearly": data["yearly"],
            "monthly": data["monthly"],
            "primary_departments": data["primary_departments"],
            "secondary_departments": data["secondary_departments"],
        }
    )


@bp.post("/api/sync")
def sync_api():
    run = sync_from_vcenter()
    status_code = 200 if run.status == "success" else 500
    return jsonify({"status": run.status, "message": run.message}), status_code


@bp.get("/clusters/<path:cluster_name>")
def cluster_detail(cluster_name: str):
    data = aggregate_dashboard()
    snapshot = data.get("snapshot")
    hosts = []
    if snapshot:
        hosts = HostResource.query.filter_by(snapshot_id=snapshot.id, cluster_name=cluster_name).order_by(HostResource.name).all()
    host_data = [row_to_dict(host) for host in hosts]
    return render_template("cluster.html", snapshot=snapshot, cluster_name=cluster_name, hosts=hosts, host_data=host_data)


@bp.get("/vms")
def vm_detail():
    snapshot, query = vm_query_from_filters(request.args)
    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    return render_template("vms.html", snapshot=snapshot, pagination=pagination, args=request.args)


@bp.get("/vms/export")
def vm_export():
    snapshot, query = vm_query_from_filters(request.args)
    if snapshot is None:
        return redirect(url_for("main.index"))
    output = vm_rows_for_export(query)
    filename = f"vcenter-vms-snapshot-{snapshot.id}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def row_to_dict(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}
