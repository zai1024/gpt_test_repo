from __future__ import annotations

import ssl
from dataclasses import dataclass, field
from datetime import datetime

from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim

from app.config import settings
from app.feishu import FeishuDepartmentClient, parse_employee_no

BYTES_IN_GB = 1024**3
BYTES_IN_TB = 1024**4
MHZ_IN_CORE = 1000


@dataclass
class VMRecord:
    name: str
    cpu_cores: int
    memory_gb: float
    provisioned_disk_gb: float
    ip_address: str
    os_version: str
    administrator: str
    employee_no: str
    primary_department: str
    secondary_department: str
    creation_date: datetime.date | None
    description: str


@dataclass
class ResourceRecord:
    name: str
    cpu_total_cores: float
    cpu_used_cores: float
    memory_total_gb: float
    memory_used_gb: float


@dataclass
class DatastoreRecord:
    name: str
    capacity_tb: float
    used_tb: float
    free_tb: float


@dataclass
class InventorySnapshot:
    vcenter_name: str
    vcenter_version: str
    cpu_total_cores: float
    cpu_used_cores: float
    memory_total_gb: float
    memory_used_gb: float
    clusters: list[ResourceRecord] = field(default_factory=list)
    hosts: dict[str, list[ResourceRecord]] = field(default_factory=dict)
    datastores: list[DatastoreRecord] = field(default_factory=list)
    vms: list[VMRecord] = field(default_factory=list)


def _ssl_context() -> ssl.SSLContext | None:
    if not settings.vcenter_disable_ssl_verify:
        return None
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _container_view(content, vim_type):
    return content.viewManager.CreateContainerView(content.rootFolder, vim_type, True)


def _custom_attributes(vm: vim.VirtualMachine) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for value in vm.summary.customValue or []:
        field_name = None
        for field in vm.availableField or []:
            if field.key == value.key:
                field_name = field.name
                break
        if field_name:
            attrs[field_name] = str(value.value or "")
    return attrs


def _parse_date(value: str):
    if not value:
        return None
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def _vm_provisioned_gb(vm: vim.VirtualMachine) -> float:
    committed = getattr(vm.summary.storage, "committed", 0) or 0
    uncommitted = getattr(vm.summary.storage, "uncommitted", 0) or 0
    return round((committed + uncommitted) / BYTES_IN_GB, 2)


def _host_resource(host: vim.HostSystem) -> ResourceRecord:
    hardware = host.summary.hardware
    quick = host.summary.quickStats
    cpu_total_mhz = (hardware.numCpuCores or 0) * (hardware.cpuMhz or 0)
    cpu_used_mhz = quick.overallCpuUsage or 0
    memory_total_bytes = hardware.memorySize or 0
    memory_used_mb = quick.overallMemoryUsage or 0
    return ResourceRecord(
        name=host.name,
        cpu_total_cores=round(cpu_total_mhz / MHZ_IN_CORE, 2),
        cpu_used_cores=round(cpu_used_mhz / MHZ_IN_CORE, 2),
        memory_total_gb=round(memory_total_bytes / BYTES_IN_GB, 2),
        memory_used_gb=round(memory_used_mb / 1024, 2),
    )


def _cluster_resource(cluster: vim.ClusterComputeResource) -> ResourceRecord:
    hosts = [_host_resource(host) for host in cluster.host or []]
    return ResourceRecord(
        name=cluster.name,
        cpu_total_cores=round(sum(host.cpu_total_cores for host in hosts), 2),
        cpu_used_cores=round(sum(host.cpu_used_cores for host in hosts), 2),
        memory_total_gb=round(sum(host.memory_total_gb for host in hosts), 2),
        memory_used_gb=round(sum(host.memory_used_gb for host in hosts), 2),
    )


def collect_inventory() -> InventorySnapshot:
    service_instance = SmartConnect(
        host=settings.vcenter_host,
        user=settings.vcenter_user,
        pwd=settings.vcenter_password,
        port=settings.vcenter_port,
        sslContext=_ssl_context(),
    )
    content = service_instance.RetrieveContent()
    dept_client = FeishuDepartmentClient()

    cluster_view = _container_view(content, [vim.ClusterComputeResource])
    vm_view = _container_view(content, [vim.VirtualMachine])
    datastore_view = _container_view(content, [vim.Datastore])

    try:
        clusters = [_cluster_resource(cluster) for cluster in cluster_view.view]
        hosts_by_cluster = {
            cluster.name: [_host_resource(host) for host in cluster.host or []]
            for cluster in cluster_view.view
        }

        datastores: list[DatastoreRecord] = []
        for datastore in datastore_view.view:
            summary = datastore.summary
            capacity = summary.capacity or 0
            free = summary.freeSpace or 0
            if capacity >= BYTES_IN_TB:
                datastores.append(
                    DatastoreRecord(
                        name=summary.name,
                        capacity_tb=round(capacity / BYTES_IN_TB, 2),
                        used_tb=round((capacity - free) / BYTES_IN_TB, 2),
                        free_tb=round(free / BYTES_IN_TB, 2),
                    )
                )

        vms: list[VMRecord] = []
        for vm in vm_view.view:
            summary = vm.summary
            attrs = _custom_attributes(vm)
            administrator = attrs.get("Administrator", "")
            employee_no = parse_employee_no(administrator)
            dept = dept_client.get_department(employee_no)
            guest = summary.guest
            config = summary.config
            vms.append(
                VMRecord(
                    name=summary.config.name,
                    cpu_cores=config.numCpu or 0,
                    memory_gb=round((config.memorySizeMB or 0) / 1024, 2),
                    provisioned_disk_gb=_vm_provisioned_gb(vm),
                    ip_address=guest.ipAddress or "",
                    os_version=config.guestFullName or guest.guestFullName or "未知",
                    administrator=administrator,
                    employee_no=employee_no,
                    primary_department=dept.primary_department,
                    secondary_department=dept.secondary_department,
                    creation_date=_parse_date(attrs.get("Creation Data", "")),
                    description=attrs.get("Description", ""),
                )
            )

        return InventorySnapshot(
            vcenter_name=content.about.name or settings.vcenter_host,
            vcenter_version=content.about.version or "7.0.3",
            cpu_total_cores=round(sum(item.cpu_total_cores for item in clusters), 2),
            cpu_used_cores=round(sum(item.cpu_used_cores for item in clusters), 2),
            memory_total_gb=round(sum(item.memory_total_gb for item in clusters), 2),
            memory_used_gb=round(sum(item.memory_used_gb for item in clusters), 2),
            clusters=clusters,
            hosts=hosts_by_cluster,
            datastores=datastores,
            vms=vms,
        )
    finally:
        cluster_view.Destroy()
        vm_view.Destroy()
        datastore_view.Destroy()
        Disconnect(service_instance)
