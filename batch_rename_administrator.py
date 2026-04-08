#!/usr/bin/env python3
"""批量连接 Windows 服务器并将内置 Administrator 重命名为 invadmin。

依赖：
    pip install pywinrm

示例：
    python batch_rename_administrator.py \
        --targets servers.txt \
        --username domain\\opsuser \
        --password 'P@ssw0rd!' \
        --transport ntlm

目标文件每行一个主机名或 IP，支持以下格式：
    10.0.0.10
    server01.example.com
    https://server02.example.com:5986
"""

from __future__ import annotations

import argparse
import getpass
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import urlparse

DEFAULT_NEW_NAME = "invadmin"
BUILTIN_ADMIN_SID_SUFFIX = "-500"


@dataclass
class TargetResult:
    target: str
    ok: bool
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量连接 Windows 服务器，将内置 Administrator 重命名为 invadmin。"
    )
    parser.add_argument(
        "--targets",
        required=True,
        help="目标文件路径，每行一个主机名/IP/WinRM URL。",
    )
    parser.add_argument(
        "--username",
        required=True,
        help="远程连接用户名，例如 domain\\admin 或 .\\localadmin。",
    )
    parser.add_argument(
        "--password",
        help="远程连接密码；不传则交互式输入。",
    )
    parser.add_argument(
        "--new-name",
        default=DEFAULT_NEW_NAME,
        help=f"新的管理员账户名，默认 {DEFAULT_NEW_NAME}。",
    )
    parser.add_argument(
        "--transport",
        default="ntlm",
        choices=["basic", "ntlm", "kerberos", "credssp"],
        help="WinRM 认证方式，默认 ntlm。",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="WinRM 端口；未指定时 HTTP 默认 5985，HTTPS 默认 5986。",
    )
    parser.add_argument(
        "--https",
        action="store_true",
        help="未在 targets 中显式写协议时，使用 HTTPS 连接。",
    )
    parser.add_argument(
        "--skip-cert-validation",
        action="store_true",
        help="HTTPS 下跳过证书校验。仅建议内网临时使用。",
    )
    parser.add_argument(
        "--operation-timeout",
        type=int,
        default=30,
        help="单台主机 WinRM 操作超时时间（秒），默认 30。",
    )
    parser.add_argument(
        "--read-timeout",
        type=int,
        default=45,
        help="单台主机 WinRM 读取超时时间（秒），默认 45。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只检查并输出将要执行的动作，不实际重命名。",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="并发处理的线程数，默认 5。",
    )
    return parser.parse_args()


def load_targets(path: str) -> List[str]:
    file_path = Path(path)
    if not file_path.is_file():
        raise SystemExit(f"targets 文件不存在: {file_path}")

    targets: List[str] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        targets.append(line)

    if not targets:
        raise SystemExit("targets 文件为空，至少需要一个目标。")
    return targets


def build_endpoint(target: str, use_https: bool, port: int | None) -> str:
    if target.startswith("http://") or target.startswith("https://"):
        parsed = urlparse(target)
        if not parsed.hostname:
            raise ValueError(f"无效的目标地址: {target}")
        endpoint_port = parsed.port or (5986 if parsed.scheme == "https" else 5985)
        path = parsed.path if parsed.path else "/wsman"
        return f"{parsed.scheme}://{parsed.hostname}:{endpoint_port}{path}"

    scheme = "https" if use_https else "http"
    endpoint_port = port or (5986 if scheme == "https" else 5985)
    return f"{scheme}://{target}:{endpoint_port}/wsman"


PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$newName = '{new_name}'
$dryRun = [System.Convert]::ToBoolean('{dry_run}')

$admin = Get-CimInstance Win32_UserAccount -Filter "LocalAccount=True" |
    Where-Object {{ $_.SID -like '*{sid_suffix}' }} |
    Select-Object -First 1

if (-not $admin) {{
    throw '未找到内置管理员账户（SID 结尾不是 -500）。'
}}

$currentName = $admin.Name

if ($currentName -ieq $newName) {{
    Write-Output "ALREADY_RENAMED:$currentName"
    exit 0
}}

if (Get-LocalUser -Name $newName -ErrorAction SilentlyContinue) {{
    throw "目标名称 $newName 已存在，无法重命名。"
}}

if ($dryRun) {{
    Write-Output "DRY_RUN:$currentName->$newName"
    exit 0
}}

Rename-LocalUser -Name $currentName -NewName $newName
$renamed = Get-CimInstance Win32_UserAccount -Filter "LocalAccount=True" |
    Where-Object {{ $_.SID -eq $admin.SID }} |
    Select-Object -First 1

if (-not $renamed) {{
    throw '重命名后未能重新查询到账户。'
}}

Write-Output "RENAMED:$currentName->$($renamed.Name)"
""".strip()


def import_winrm_module():
    try:
        import winrm
    except ImportError as exc:  # pragma: no cover - import guard for user guidance
        raise SystemExit(
            "缺少依赖 pywinrm，请先执行: pip install pywinrm"
        ) from exc
    return winrm


def run_for_target(
    target: str,
    *,
    username: str,
    password: str,
    transport: str,
    use_https: bool,
    port: int | None,
    skip_cert_validation: bool,
    operation_timeout: int,
    read_timeout: int,
    new_name: str,
    dry_run: bool,
) -> TargetResult:
    try:
        winrm = import_winrm_module()
        endpoint = build_endpoint(target, use_https=use_https, port=port)
        session = winrm.Session(
            target=endpoint,
            auth=(username, password),
            transport=transport,
            server_cert_validation="ignore" if skip_cert_validation else "validate",
            operation_timeout_sec=operation_timeout,
            read_timeout_sec=read_timeout,
        )
        script = PS_SCRIPT.format(
            new_name=new_name.replace("'", "''"),
            dry_run=str(dry_run),
            sid_suffix=BUILTIN_ADMIN_SID_SUFFIX,
        )
        result = session.run_ps(script)
    except Exception as exc:
        return TargetResult(target=target, ok=False, message=f"连接或执行失败: {exc}")

    stdout = result.std_out.decode("utf-8", errors="ignore").strip()
    stderr = result.std_err.decode("utf-8", errors="ignore").strip()

    if result.status_code == 0:
        return TargetResult(target=target, ok=True, message=stdout or "执行成功")

    error_message = stderr or stdout or f"远程命令失败，退出码 {result.status_code}"
    return TargetResult(target=target, ok=False, message=error_message)



def main() -> int:
    args = parse_args()
    password = args.password or getpass.getpass("请输入远程连接密码: ")
    targets = load_targets(args.targets)

    results: List[TargetResult] = []
    max_workers = max(1, args.workers)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for target in targets:
            print(f"正在提交任务 {target} ...")
            future = executor.submit(
                run_for_target,
                target,
                username=args.username,
                password=password,
                transport=args.transport,
                use_https=args.https,
                port=args.port,
                skip_cert_validation=args.skip_cert_validation,
                operation_timeout=args.operation_timeout,
                read_timeout=args.read_timeout,
                new_name=args.new_name,
                dry_run=args.dry_run,
            )
            future_map[future] = target

        for future in as_completed(future_map):
            result = future.result()
            print(f"处理完成 {result.target}: {result.message}")
            results.append(result)

    results.sort(key=lambda item: item.target)

    failed = 0
    print("\n执行结果汇总")
    print("=" * 72)
    for item in results:
        status = "SUCCESS" if item.ok else "FAILED"
        print(f"[{status:<7}] {item.target} -> {item.message}")
        if not item.ok:
            failed += 1
    print("=" * 72)
    print(f"总计: {len(results)}，成功: {len(results) - failed}，失败: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
