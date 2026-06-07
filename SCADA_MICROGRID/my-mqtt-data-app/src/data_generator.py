import random
import threading
import time
from typing import Callable

from src.config import Config


class LocalDataGenerator:
    def __init__(self, publish_callback: Callable[[str, dict], None], interval_sec: int = Config.DATA_GENERATION_INTERVAL):
        self.publish_callback = publish_callback
        self.interval_sec = interval_sec
        self._running = False
        self._thread = None

    def _generate_payload(self) -> dict:
        return {
            "timestamp": int(time.time()),
            "pv_power_kw": round(random.uniform(0.0, 5.0), 2),
            "wind_power_kw": round(random.uniform(0.0, 4.0), 2),
            "battery_soc_pct": round(random.uniform(20.0, 90.0), 1),
            "grid_load_kw": round(random.uniform(0.5, 6.0), 2),
        }

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)

    def _run(self):
        while self._running:
            payload = self._generate_payload()
            self.publish_callback(Config.MQTT_TOPIC_DATA, payload)
            time.sleep(self.interval_sec)