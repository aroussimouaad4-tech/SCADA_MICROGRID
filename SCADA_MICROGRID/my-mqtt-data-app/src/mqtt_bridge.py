import json
import logging
import threading
import time

import paho.mqtt.client as mqtt

from src.config import Config

logger = logging.getLogger("mqtt_bridge")


class MQTTBridge:
    def __init__(self, broker: str, port: int):
        self.broker = broker
        self.port = port
        self._client = None
        self._connected = False
        self._lock = threading.Lock()
        self._last_data = None
        self._last_rx_time = 0.0
        self._topic_data = Config.MQTT_TOPIC_DATA
        self._topic_cmd = Config.MQTT_TOPIC_CMD

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            client.subscribe(self._topic_cmd)
            logger.info(f"[MQTT] Connected to {self.broker}:{self.port}")
        else:
            self._connected = False
            logger.error(f"[MQTT] Connection failed rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        logger.warning(f"[MQTT] Disconnected rc={rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            with self._lock:
                self._last_data = payload
                self._last_rx_time = time.time()
            logger.info(f"[MQTT] Received on {msg.topic}: {payload}")
        except Exception as exc:
            logger.error(f"[MQTT] Invalid message: {exc}")

    def start(self):
        try:
            self._client = mqtt.Client()
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message
            self._client.connect(self.broker, self.port, keepalive=Config.MQTT_KEEPALIVE)
            self._client.loop_start()
        except Exception as exc:
            logger.error(f"[MQTT] Cannot start MQTT client: {exc}")
            self._client = None
            self._connected = False

    def stop(self):
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._connected = False

    def publish(self, topic: str, payload: dict):
        if self._client and self._connected:
            try:
                self._client.publish(topic, json.dumps(payload))
            except Exception as exc:
                logger.error(f"[MQTT] Publish failed: {exc}")
        else:
            logger.warning("[MQTT] Not connected, cannot publish")

    def publish_cmd(self, cmd: dict):
        self.publish(self._topic_cmd, cmd)

    def get_latest(self):
        with self._lock:
            return None if self._last_data is None else self._last_data.copy()