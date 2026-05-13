from __future__ import annotations

from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


db = SQLAlchemy()


class VCenterSnapshot(db.Model):
    __tablename__ = "vcenter_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    vcenter_name: Mapped[str] = mapped_column(String(255), default="")
    vcenter_version: Mapped[str] = mapped_column(String(64), default="")
    cpu_total_cores: Mapped[float] = mapped_column(Float, default=0)
    cpu_used_cores: Mapped[float] = mapped_column(Float, default=0)
    memory_total_gb: Mapped[float] = mapped_column(Float, default=0)
    memory_used_gb: Mapped[float] = mapped_column(Float, default=0)
    vm_count: Mapped[int] = mapped_column(Integer, default=0)


class ClusterResource(db.Model):
    __tablename__ = "cluster_resources"
    __table_args__ = (UniqueConstraint("snapshot_id", "name", name="uq_cluster_snapshot_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    cpu_total_cores: Mapped[float] = mapped_column(Float, default=0)
    cpu_used_cores: Mapped[float] = mapped_column(Float, default=0)
    memory_total_gb: Mapped[float] = mapped_column(Float, default=0)
    memory_used_gb: Mapped[float] = mapped_column(Float, default=0)


class HostResource(db.Model):
    __tablename__ = "host_resources"
    __table_args__ = (UniqueConstraint("snapshot_id", "cluster_name", "name", name="uq_host_snapshot_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, index=True)
    cluster_name: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    cpu_total_cores: Mapped[float] = mapped_column(Float, default=0)
    cpu_used_cores: Mapped[float] = mapped_column(Float, default=0)
    memory_total_gb: Mapped[float] = mapped_column(Float, default=0)
    memory_used_gb: Mapped[float] = mapped_column(Float, default=0)


class DatastoreResource(db.Model):
    __tablename__ = "datastore_resources"
    __table_args__ = (UniqueConstraint("snapshot_id", "name", name="uq_datastore_snapshot_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    capacity_tb: Mapped[float] = mapped_column(Float, default=0)
    used_tb: Mapped[float] = mapped_column(Float, default=0)
    free_tb: Mapped[float] = mapped_column(Float, default=0)


class VirtualMachine(db.Model):
    __tablename__ = "virtual_machines"
    __table_args__ = (UniqueConstraint("snapshot_id", "name", name="uq_vm_snapshot_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    cpu_cores: Mapped[int] = mapped_column(Integer, default=0)
    memory_gb: Mapped[float] = mapped_column(Float, default=0)
    provisioned_disk_gb: Mapped[float] = mapped_column(Float, default=0)
    ip_address: Mapped[str] = mapped_column(String(255), default="")
    os_version: Mapped[str] = mapped_column(String(255), default="未知")
    administrator: Mapped[str] = mapped_column(String(255), default="")
    employee_no: Mapped[str] = mapped_column(String(64), default="", index=True)
    primary_department: Mapped[str] = mapped_column(String(255), default="未知", index=True)
    secondary_department: Mapped[str] = mapped_column(String(255), default="未知", index=True)
    creation_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")


class SyncRun(db.Model):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    message: Mapped[str] = mapped_column(Text, default="")
