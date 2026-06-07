import os

class Config:
    MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
    MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
    MQTT_TOPIC_DATA = os.environ.get("MQTT_TOPIC_DATA", "microgrid/data")
    MQTT_TOPIC_CMD = os.environ.get("MQTT_TOPIC_CMD", "microgrid/cmd")
    MQTT_KEEPALIVE = int(os.environ.get("MQTT_KEEPALIVE", "60"))
    DATA_GENERATION_INTERVAL = int(os.environ.get("DATA_GENERATION_INTERVAL", "2"))