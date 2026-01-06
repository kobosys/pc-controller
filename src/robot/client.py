from __future__ import annotations

import requests
from typing import Any, Dict, Optional


class RobotClient:
    def __init__(self, ip: str, port: int = 1448, timeout_sec: float = 3.0):
        self.base_url = f"http://{ip}:{port}"
        self.timeout_sec = timeout_sec

    # ---- Basic ----
    def power_status(self) -> Dict[str, Any]:
        url = f"{self.base_url}/api/core/system/v1/power/status"
        r = requests.get(url, timeout=self.timeout_sec)
        r.raise_for_status()
        return r.json()

    def get_pois(self) -> Dict[str, Any]:
        """우선 multi-floor POI를 시도하고, 실패하면 core artifact POI로 fallback"""
        # 1) multi-floor
        url1 = f"{self.base_url}/api/multi-floor/map/v1/pois"
        r1 = requests.get(url1, timeout=self.timeout_sec)
        if r1.status_code == 200:
            return r1.json()

        # 2) core artifact
        url2 = f"{self.base_url}/api/core/artifact/v1/pois"
        r2 = requests.get(url2, timeout=self.timeout_sec)
        r2.raise_for_status()
        return r2.json()

    # ---- Motion (Action) ----
    def create_move_to_poi_action(
        self,
        poi_name: str,
        mode: int = 0,
        with_yaw: bool = False,
        yaw_rad: float = 0.0,
        precise: bool = False,
        acceptable_precision_m: Optional[float] = None,
        fail_retry_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        POI로 이동 액션 생성 (MultiFloorMoveAction 권장)
        POST /api/core/motion/v1/actions
        """
        url = f"{self.base_url}/api/core/motion/v1/actions"

        flags = []
        if with_yaw:
            flags.append("with_yaw")
        if precise:
            flags.append("precise")

        move_options: Dict[str, Any] = {"mode": mode, "flags": flags}
        if with_yaw:
            move_options["yaw"] = float(yaw_rad)
        if acceptable_precision_m is not None:
            move_options["acceptable_precision"] = float(acceptable_precision_m)
        if fail_retry_count is not None:
            move_options["fail_retry_count"] = int(fail_retry_count)

        payload = {
            "action_name": "slamtec.agent.actions.MultiFloorMoveAction",
            "options": {
                "target": {"poi_name": poi_name},
                "move_options": move_options,
            },
        }

        r = requests.post(url, json=payload, timeout=self.timeout_sec)
        r.raise_for_status()
        return r.json()

    def get_action(self, action_id: int) -> Dict[str, Any]:
        url = f"{self.base_url}/api/core/motion/v1/actions/{action_id}"
        r = requests.get(url, timeout=self.timeout_sec)
        r.raise_for_status()
        return r.json()

    def cancel_current_action(self) -> None:
        """
        즉시 정지(현재 액션 취소)
        DELETE /api/core/motion/v1/actions/:current
        """
        url = f"{self.base_url}/api/core/motion/v1/actions/:current"
        r = requests.delete(url, timeout=self.timeout_sec)
        # 취소는 204일 수도 있고 200일 수도 있음 → 둘 다 OK
        if r.status_code not in (200, 204):
            r.raise_for_status()
