from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from app.config import settings


@dataclass(frozen=True)
class DepartmentInfo:
    employee_no: str
    primary_department: str = "未知"
    secondary_department: str = "未知"


def parse_employee_no(administrator: str) -> str:
    match = re.search(r"-(\d+)\s*$", administrator or "")
    return match.group(1) if match else ""


def normalize_department_payload(employee_no: str, payload: dict) -> DepartmentInfo:
    data = payload.get("data", payload)
    return DepartmentInfo(
        employee_no=employee_no,
        primary_department=(
            data.get("primary_department")
            or data.get("first_department")
            or data.get("一级部门")
            or "未知"
        ),
        secondary_department=(
            data.get("secondary_department")
            or data.get("second_department")
            or data.get("二级部门")
            or "未知"
        ),
    )


class FeishuDepartmentClient:
    def __init__(self) -> None:
        self.endpoint = settings.feishu_dept_endpoint
        self.token = settings.feishu_token
        self.timeout = settings.feishu_timeout_seconds
        self._cache: dict[str, DepartmentInfo] = {}

    def get_department(self, employee_no: str) -> DepartmentInfo:
        if not employee_no:
            return DepartmentInfo(employee_no="")
        if employee_no in self._cache:
            return self._cache[employee_no]
        if not self.endpoint:
            info = DepartmentInfo(employee_no=employee_no)
            self._cache[employee_no] = info
            return info

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = requests.get(
            self.endpoint,
            params={"employee_no": employee_no},
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        info = normalize_department_payload(employee_no, response.json())
        self._cache[employee_no] = info
        return info
