from __future__ import annotations

import msvcrt
import time
import threading
from typing import Any, Dict, List

import requests

from config import load_settings
from robot.client import RobotClient


# ------------------------
# Action 상태 판정
# ------------------------
def is_action_finished(a: dict) -> bool:
    # stage가 비어 있거나 None인 펌웨어가 있음 → state.status로 판단
    state = a.get("state") or {}
    status = state.get("status", None)
    result = state.get("result", None)

    # 실패는 즉시 종료(상위에서 예외 처리)
    if isinstance(result, int) and result != 0:
        return True

    # Slamware에서 status=4가 완료/종료로 반복되는 케이스 대응
    if status == 4:
        return True

    # stage가 정상적으로 오는 경우도 함께 지원
    stage = a.get("stage") or ""
    if stage.upper() in {"FINISHED", "SUCCEEDED", "COMPLETED", "STOPPED"}:
        return True

    return False


def is_action_success(action: Dict[str, Any]) -> bool:
    state = action.get("state") or {}
    return state.get("result") == 0 and not state.get("reason")


# ------------------------
# 단일 POI 이동 + Watchdog
# ------------------------
def move_to_poi_with_watchdog(
    robot: RobotClient,
    poi_name: str,
    pause_event: threading.Event,
    poll_interval_sec: float = 0.3,
    comm_fail_limit: int = 2,
    max_wait_sec: float = 180.0,
) -> None:
    print(f"[MOVE] -> {poi_name}")
    action = robot.create_move_to_poi_action(
        poi_name=poi_name,
        precise=True,
    )

    action_id = int(action.get("action_id"))
    start = time.time()
    comm_fail = 0

    while True:
        # pause 요청 감지
        if not pause_event.is_set():
            print("[PAUSE] cancel current action")
            try:
                robot.cancel_current_action()
            except Exception:
                pass
            raise RuntimeError("Paused by user")

        # timeout 보호
        if time.time() - start > max_wait_sec:
            robot.cancel_current_action()
            raise TimeoutError(f"Timeout moving to {poi_name}")

        try:
            a = robot.get_action(action_id)
            comm_fail = 0
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            comm_fail += 1
            if comm_fail >= comm_fail_limit:
                try:
                    robot.cancel_current_action()
                except Exception:
                    pass
                raise ConnectionError("Communication unstable")
            time.sleep(poll_interval_sec)
            continue

        print(f"[poll] stage={a.get('stage')} state={a.get('state')}")

        if is_action_finished(a):
            if is_action_success(a):
                print(f"[DONE] {poi_name}")
                return
            else:
                raise RuntimeError(f"Move failed: {a.get('state')}")

        time.sleep(poll_interval_sec)


# ------------------------
# 키보드 명령 스레드
# ------------------------
def command_listener(
    pause_event: threading.Event,
    stop_event: threading.Event,
):
    print("\n[COMMAND]")
    print("  p : pause")
    print("  r : resume")
    print("  q : quit\n")

    while not stop_event.is_set():
        if msvcrt.kbhit():
            ch = msvcrt.getch().decode("utf-8").lower()

            if ch == "p":
                print("\n[CMD] PAUSE")
                pause_event.clear()

            elif ch == "r":
                print("\n[CMD] RESUME")
                pause_event.set()

            elif ch == "q":
                print("\n[CMD] QUIT")
                stop_event.set()
                pause_event.clear()
                return

        time.sleep(0.05)


# ------------------------
# POI 무한 루프
# ------------------------
def loop_between_pois(
    robot: RobotClient,
    pois: List[str],
    pause_event: threading.Event,
    stop_event: threading.Event,
):
    idx = 0
    print(f"[LOOP] {pois}")

    while not stop_event.is_set():
        pause_event.wait()  # resume 될 때까지 대기

        target = pois[idx]
        try:
            move_to_poi_with_watchdog(robot, target, pause_event)
        except RuntimeError as e:
            if "Paused" in str(e):
                continue
            raise

        idx = (idx + 1) % len(pois)


def main() -> None:
    s = load_settings()
    robot = RobotClient(s.robot_ip, s.robot_port, timeout_sec=2.0)

    print("[INIT]", robot.power_status())

    # ✅ POI 3개로
    pois = ["POI1", "POI2", "POI3"]

    # ✅ 시작할 때 POI가 실제로 존재하는지 + 좌표 출력 (현장 디버깅용)
    for name in pois:
        x, y, yaw = robot.resolve_poi_pose_by_name(name)
        print(f"[POI] {name} -> x={x}, y={y}, yaw={yaw}")

    pause_event = threading.Event()
    pause_event.set()  # 시작은 RUN
    stop_event = threading.Event()

    t_cmd = threading.Thread(
        target=command_listener,
        args=(pause_event, stop_event),
        daemon=True,
    )
    t_cmd.start()

    try:
        loop_between_pois(robot, pois, pause_event, stop_event)
    finally:
        print("[EXIT] program terminated")


if __name__ == "__main__":
    main()
