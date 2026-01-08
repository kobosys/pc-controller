# src/robot/client.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import requests


class RobotClient:
    def __init__(self, ip: str, port: int = 1448, timeout_sec: float = 2.0):
        self.ip = ip
        self.port = port
        self.base = f"http://{ip}:{port}"
        self.timeout_sec = timeout_sec

    def _req(self, method: str, path: str, json: Optional[dict] = None) -> Any:
        url = self.base + path
        r = requests.request(method, url, json=json, timeout=self.timeout_sec)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "")
        if "application/json" in ct:
            return r.json()
        return r.text

    # --------- main.py가 쓰는 것들 ----------
    def power_status(self) -> Dict[str, Any]:
        return self._req("GET", "/api/core/system/v1/power/status")

    def get_action(self, action_id: int) -> Dict[str, Any]:
        return self._req("GET", f"/api/core/motion/v1/actions/{action_id}")

    def cancel_current_action(self) -> None:
        self._req("DELETE", "/api/core/motion/v1/actions/:current")

    # --------- 해결법 1의 핵심: core POI → pose ----------
    def list_core_pois(self) -> List[Dict[str, Any]]:
        # 네가 올린 JSON 형태( id / metadata.display_name / pose )가 여기서 나옵니다.
        return self._req("GET", "/api/core/artifact/v1/pois")

    def resolve_poi_pose_by_name(self, poi_name: str) -> Tuple[float, float, float]:
        pois = self.list_core_pois()
        for p in pois:
            md = p.get("metadata") or {}
            if md.get("display_name") == poi_name:
                pose = p.get("pose") or {}
                return float(pose["x"]), float(pose["y"]), float(pose.get("yaw", 0.0))

        names = [((pp.get("metadata") or {}).get("display_name")) for pp in pois]
        raise ValueError(f"POI '{poi_name}' not found in core POIs. Available: {names}")

    def create_move_to_pose_action(
        self,
        x: float,
        y: float,
        yaw: Optional[float] = None,
        precise: bool = True,
    ) -> Dict[str, Any]:
        flags: List[str] = []
        if precise:
            flags.append("precise")
        if yaw is not None:
            flags.append("with_yaw")

        body = {
            "action_name": "slamtec.agent.actions.MoveToAction",
            "options": {
                "target": {"x": x, "y": y},
                "move_options": {
                    "mode": 0,
                    "flags": flags,
                    "yaw": float(yaw) if yaw is not None else 0.0,
                    "acceptable_precision": 0.0,
                    "fail_retry_count": 0,
                },
            },
        }
        return self._req("POST", "/api/core/motion/v1/actions", json=body)

    def create_move_to_poi_action(
        self,
        poi_name: str,
        precise: bool = True,
        use_poi_yaw: bool = True,
    ) -> Dict[str, Any]:
        # ✅ 이름으로 “찾기”는 core POI에서 하고,
        # ✅ 실제 “이동”은 좌표(MoveToAction)로 합니다.
        x, y, poi_yaw = self.resolve_poi_pose_by_name(poi_name)
        yaw = poi_yaw if use_poi_yaw else None
        return self.create_move_to_pose_action(x=x, y=y, yaw=yaw, precise=precise)
