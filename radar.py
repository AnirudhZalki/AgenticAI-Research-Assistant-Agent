"""
Continuous Funding/Journal Radar (proposal: "runs continuously in the background, independent of any single paper")

RadarMonitor re-checks deadlines on a timer in a daemon thread, keeps a timestamped digest, flags NEW alerts since
the last check and URGENT ones (<= urgent_days). Sources: the governed connector only.
"""

import threading
import time
from typing import Any, Dict, List

from specialist_agents import FundingRadarAgent


class RadarMonitor:
    def __init__(self, connector, topic: str, deadline: str = "", interval_s: float = 3600.0, urgent_days: int = 14):
        self.connector, self.topic, self.deadline = connector, topic, deadline
        self.interval_s, self.urgent_days = interval_s, urgent_days
        self.digest: List[Dict[str, Any]] = []         # one record per check
        self.known: set = set()
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def check_now(self) -> Dict[str, Any]:
        ctx = FundingRadarAgent().step({"topic": self.topic, "deadline": self.deadline}, self.connector)
        alerts = ctx["radar_deadlines"]
        ids = {a["id"] for a in alerts}
        with self._lock:
            new = sorted(ids - self.known)
            self.known |= ids
            urgent = [a["id"] for a in alerts if a["status"] == "UPCOMING" and a["days_remaining"] is not None
                      and a["days_remaining"] <= self.urgent_days]
            rec = {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "alerts": len(alerts), "new": new,
                   "urgent": urgent, "items": alerts}
            self.digest.append(rec)
        return rec

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.check_now()
            except Exception as exc:                      # a failing check must never kill the monitor
                with self._lock:
                    self.digest.append({"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "alerts": 0, "new": [],
                                        "urgent": [], "items": [], "error": str(exc)})
            self._stop.wait(self.interval_s)

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="RadarMonitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())
