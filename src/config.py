from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    robot_ip: str
    robot_port: int = 1448


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / "configs" / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    ip = (os.getenv("ROBOT_IP") or "").strip()
    port = int((os.getenv("ROBOT_PORT") or "1448").strip())
    if not ip:
        raise ValueError("ROBOT_IP is empty. Set it in configs/.env")

    return Settings(robot_ip=ip, robot_port=port)
