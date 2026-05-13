# vCenter 资源与虚拟机看板

一个基于 Flask + MySQL + ECharts 的 vCenter 7.0.3 内部资源看板。系统每天从 vCenter 采集资源、虚拟机、自定义属性，并通过飞书接口补充管理员一级/二级部门信息，存入 MySQL 后在 HTML 页面展示，详情页支持 Excel 导出。

## 功能

- vCenter CPU/内存总量与已使用量概览。
- 集群 CPU/内存总量与已使用量，点击集群进入 ESXi 主机明细。
- 展示超过 1TB 的 datastore/卷总空间与已使用空间。
- 虚拟机总数、按操作系统、近 5 年、近 6 个月、一级部门、二级部门聚合展示。
- 图表点击跳转虚拟机明细，支持导出 Excel。
- 每日自动同步，也支持手动触发同步接口。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 修改 .env 中 MySQL、vCenter、飞书配置
flask --app app run --host 0.0.0.0 --port 8000
```

访问 `http://127.0.0.1:8000`。

## MySQL 初始化

应用启动时会通过 SQLAlchemy 自动创建需要的表。请先创建数据库与账号，例如：

```sql
CREATE DATABASE vcenter_dashboard DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'vcenter_dashboard'@'%' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON vcenter_dashboard.* TO 'vcenter_dashboard'@'%';
FLUSH PRIVILEGES;
```

默认 MySQL 地址为 `10.32.225.19:3306`，可在 `.env` 中修改。

## vCenter 自定义属性

系统会读取每台虚拟机的自定义属性：

- `Administrator`：管理员，格式如 `王斌斌-112456`。
- `Creation Data`：创建日期，格式 `YYYY-MM-DD`。
- `Description`：描述，长文本。

## 飞书部门接口约定

`FEISHU_DEPT_ENDPOINT` 应支持 GET 请求，查询参数为 `employee_no`。示例响应兼容以下字段：

```json
{
  "primary_department": "研发中心",
  "secondary_department": "云平台部"
}
```

如果你们现有飞书接口字段不同，可修改 `app/feishu.py` 的 `normalize_department_payload` 函数。

## 手动同步

```bash
curl -X POST http://127.0.0.1:8000/api/sync
```

## 单次采集脚本

```bash
python scripts/sync_once.py
```
