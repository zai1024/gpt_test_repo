from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    secret_key: str = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    mysql_host: str = os.getenv("MYSQL_HOST", "10.32.225.19")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "vcenter_dashboard")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "vcenter_dashboard")
    vcenter_host: str = os.getenv("VCENTER_HOST", "")
    vcenter_user: str = os.getenv("VCENTER_USER", "")
    vcenter_password: str = os.getenv("VCENTER_PASSWORD", "")
    vcenter_port: int = int(os.getenv("VCENTER_PORT", "443"))
    vcenter_disable_ssl_verify: bool = env_bool("VCENTER_DISABLE_SSL_VERIFY", True)
    feishu_dept_endpoint: str = os.getenv("FEISHU_DEPT_ENDPOINT", "")
    feishu_token: str = os.getenv("FEISHU_TOKEN", "")
    feishu_timeout_seconds: int = int(os.getenv("FEISHU_TIMEOUT_SECONDS", "8"))
    enable_scheduler: bool = env_bool("ENABLE_SCHEDULER", False)
    sync_cron_hour: int = int(os.getenv("SYNC_CRON_HOUR", "2"))
    sync_cron_minute: int = int(os.getenv("SYNC_CRON_MINUTE", "15"))

    @property
    def sqlalchemy_database_uri(self) -> str:
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{user}:{password}@{self.mysql_host}:"
            f"{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


settings = Settings()
