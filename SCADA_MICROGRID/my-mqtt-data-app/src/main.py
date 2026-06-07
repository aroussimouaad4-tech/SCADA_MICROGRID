import logging
import time

from src.config import Config
from src.data_generator import LocalDataGenerator
from src.mqtt_bridge import MQTTBridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def main():
    bridge = MQTTBridge(Config.MQTT_BROKER, Config.MQTT_PORT)
    bridge.start()

    generator = LocalDataGenerator(bridge.publish)
    generator.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        generator.stop()
        bridge.stop()

if __name__ == "__main__":
    main()