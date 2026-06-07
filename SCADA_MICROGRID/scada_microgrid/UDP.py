"""
PLC controller layer for the SCADA dashboard.

The historical module name is kept for compatibility, but the implementation is
now UDP-only and designed to read telemetry sent by MATLAB / Simulink.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from alarms import AlarmLevel, AlarmManager
from config import Config
from historian import Historian
from process import BatterieESS, ChargeReseau, Eolienne, PanneauSolaire, ReseauElectrique


logger = logging.getLogger("SCADAUDP")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class PLCMode:
    STOP = "STOP"
    RUN = "RUN"
    FAULT = "FAULT"


class CommProtocol:
    UDP = "UDP"


@dataclass
class Tag:
    name: str
    value: Any = 0.0
    unit: str = ""
    description: str = ""


class LinkStatus:
    DISCONNECTED = "DISCONNECTED"
    LISTENING = "LISTENING"
    ONLINE = "ONLINE"
    SIMULATION = "SIMULATION"


class BaseBridge:
    protocol_name = "UNKNOWN"

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def publish_cmd(self, cmd: dict) -> None:
        raise NotImplementedError

    def get_latest(self) -> Optional[dict]:
        raise NotImplementedError

    @property
    def connection_status(self) -> str:
        raise NotImplementedError

    @property
    def last_rx_age_s(self) -> Optional[float]:
        raise NotImplementedError

    @property
    def is_remote_online(self) -> bool:
        raise NotImplementedError

    @property
    def display_endpoint(self) -> str:
        raise NotImplementedError


class UDPBridge(BaseBridge):
    protocol_name = CommProtocol.UDP

    def __init__(self, local_host: str, local_port: int):
        self.local_host = local_host
        self.local_port = int(local_port)
        self._last_sender: Optional[tuple[str, int]] = None
        self._last_data: Optional[dict] = None
        self._last_rx_time = 0.0
        self._lock = threading.Lock()
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._bound = False
        self._thread: Optional[threading.Thread] = None
        self._last_status: Optional[str] = None

    def _set_status(self, status: str, message: str) -> None:
        if self._last_status != status:
            self._last_status = status
            logger.info("[UDP STATUS] %s | %s", status, message)

    def _extract_json_object(self, payload: bytes) -> dict:
        text = payload.decode("utf-8", errors="ignore").replace("\x00", "").strip()
        if not text:
            return None  # Return None for empty payloads instead of raising error

        decoder = json.JSONDecoder()

        # First try direct parsing of the payload as-is.
        try:
            parsed, _ = decoder.raw_decode(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Simulink / MATLAB sometimes append extra characters around the JSON.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        return None  # Return None for unparseable payloads instead of raising error

    def _listen_loop(self) -> None:
        assert self._socket is not None
        while self._running:
            try:
                payload, addr = self._socket.recvfrom(Config.udp.BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                data = self._extract_json_object(payload)
                if data is None:
                    continue  # Skip empty or unparseable payloads silently
                
                with self._lock:
                    self._last_data = data
                    self._last_rx_time = time.time()
                    self._last_sender = addr
                self._set_status(LinkStatus.ONLINE, f"source={addr[0]}:{addr[1]}")
                logger.info("[UDP] Data received from %s with keys=%s", addr, list(data.keys()))
            except Exception as exc:
                logger.error("[UDP] Unexpected error from %s: %s", addr, exc)

    def start(self) -> None:
        logger.info("[UDP] Starting UDP bridge on %s:%s", self.local_host, self.local_port)
        self.stop()
        # Wait a bit for the thread to stop
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.local_host, self.local_port))
            self._socket.settimeout(0.5)
            self._running = True
            self._bound = True
            self._thread = threading.Thread(target=self._listen_loop, name="udp-bridge", daemon=True)
            self._thread.start()
            self._set_status(LinkStatus.LISTENING, f"listen={self.local_host}:{self.local_port}")
            logger.info("[UDP] Successfully listening on %s:%s", self.local_host, self.local_port)
        except OSError as exc:
            logger.error("[UDP] Failed to bind to %s:%s: %s", self.local_host, self.local_port, exc)
            self._bound = False
            self._running = False
            if self._socket:
                try:
                    self._socket.close()
                except OSError:
                    pass
            self._socket = None
            self._set_status(LinkStatus.DISCONNECTED, f"bind failed on {self.local_host}:{self.local_port}")
            logger.error("[UDP] Unable to bind %s:%s: %s", self.local_host, self.local_port, exc)

    def stop(self) -> None:
        logger.info("[UDP] Stopping UDP bridge")
        self._running = False
        self._bound = False
        sock = self._socket
        self._socket = None
        if sock:
            try:
                sock.close()
                logger.info("[UDP] Socket closed")
            except OSError as e:
                logger.warning(f"[UDP] Error closing socket: {e}")
        self._thread = None
        self._set_status(LinkStatus.DISCONNECTED, "listener stopped")
        logger.info("[UDP] UDP bridge stopped")

    def reconfigure(self, local_host: str, local_port: int) -> None:
        logger.info(f"[UDP] Reconfiguring from {self.local_host}:{self.local_port} to {local_host}:{local_port}")
        self.local_host = local_host
        self.local_port = int(local_port)
        with self._lock:
            self._last_data = None
            self._last_rx_time = 0.0
            self._last_sender = None
        self.start()

    def publish_cmd(self, cmd: dict) -> None:
        # Current integration is RX-only from Simulink.
        return

    def get_latest(self) -> Optional[dict]:
        with self._lock:
            return self._last_data.copy() if self._last_data else None

    @property
    def is_remote_online(self) -> bool:
        return (time.time() - self._last_rx_time) < Config.udp.TIMEOUT_SEC

    @property
    def connection_status(self) -> str:
        if not self._bound:
            logger.debug(f"[UDP] Status: DISCONNECTED (not bound)")
            self._set_status(LinkStatus.DISCONNECTED, "socket not bound")
            return LinkStatus.DISCONNECTED
        if self.is_remote_online:
            logger.debug(f"[UDP] Status: ONLINE")
            if self._last_sender:
                self._set_status(LinkStatus.ONLINE, f"source={self._last_sender[0]}:{self._last_sender[1]}")
            return LinkStatus.ONLINE
        logger.debug(f"[UDP] Status: LISTENING on {self.local_host}:{self.local_port}")
        self._set_status(LinkStatus.LISTENING, f"waiting on {self.local_host}:{self.local_port}")
        return LinkStatus.LISTENING

    @property
    def last_rx_age_s(self) -> Optional[float]:
        if self._last_rx_time == 0.0:
            return None
        return round(time.time() - self._last_rx_time, 1)

    @property
    def display_endpoint(self) -> str:
        sender = ""
        if self._last_sender:
            sender = f" | last sender {self._last_sender[0]}:{self._last_sender[1]}"
        return f"UDP listen {self.local_host}:{self.local_port}{sender}"


class PLC:
    """Main SCADA controller with optional UDP telemetry input."""

    def __init__(self):
        self.bridge = UDPBridge(Config.udp.LOCAL_HOST, Config.udp.LOCAL_PORT)
        self.bridge.start()

        self.pv = PanneauSolaire()
        self.eolien = Eolienne()
        self.batterie = BatterieESS()
        self.charge = ChargeReseau()
        self.reseau = ReseauElectrique()

        self.hist = Historian()
        self.alarm = AlarmManager()

        self.mode: str = PLCMode.STOP
        self.scan_count = 0
        self.last_scan_duration_ms = 0.0
        self._last_source_logged: Optional[str] = None
        self.simulated_time_h = 0.0

        self.soc_cible = 0.70
        self.mode_ems = "AUTO"
        self.puissance_batt_manuelle = 0.0
        self.pv_cut = False

        self.tags: Dict[str, Tag] = {
            "P_PV": Tag("P_PV", 0.0, "W", "Puissance PV"),
            "PV_CUT": Tag("PV_CUT", False, "", "Commande coupure PV"),
            "IRRADIANCE": Tag("IRRADIANCE", 0.0, "W/m2", "Irradiance solaire"),
            "TEMP_MODULE": Tag("TEMP_MODULE", 25.0, "degC", "Temperature module PV"),
            "P_EOLIEN": Tag("P_EOLIEN", 0.0, "W", "Puissance eolienne"),
            "VITESSE_VENT": Tag("VITESSE_VENT", 5.0, "m/s", "Vitesse vent"),
            "VITESSE_ROTOR": Tag("VITESSE_ROTOR", 0.0, "rpm", "Vitesse rotor"),
            "SOC": Tag("SOC", 60.0, "%", "State of Charge"),
            "P_BATTERIE": Tag("P_BATTERIE", 0.0, "W", "Puissance batterie"),
            "TEMP_BATTERIE": Tag("TEMP_BATTERIE", 22.0, "degC", "Temperature batterie"),
            "CYCLES_BATT": Tag("CYCLES_BATT", 0.0, "cyc", "Cycles equivalents"),
            "ETAT_BATT": Tag("ETAT_BATT", "REPOS", "", "Etat batterie"),
            "P_CHARGE": Tag("P_CHARGE", 60.0, "W", "Puissance charge"),
            "P_RESEAU": Tag("P_RESEAU", 0.0, "W", "Import reseau (+imp/-exp)"),
            "TENSION_RESEAU": Tag("TENSION_RESEAU", 400.0, "V", "Tension reseau"),
            "FREQUENCE_RESEAU": Tag("FREQUENCE_RESEAU", 50.0, "Hz", "Frequence reseau"),
            "TAUX_ER": Tag("TAUX_ER", 0.0, "%", "Taux energies renouvelables"),
            "P_TOTALE_ER": Tag("P_TOTALE_ER", 0.0, "W", "Puissance totale ER"),
            "ENERGIE_PV": Tag("ENERGIE_PV", 0.0, "Wh", "Energie PV produite"),
            "ENERGIE_EOLIEN": Tag("ENERGIE_EOLIEN", 0.0, "Wh", "Energie eolienne produite"),
            "ENERGIE_IMPORTEE": Tag("ENERGIE_IMPORTEE", 0.0, "Wh", "Energie importee reseau"),
            "ENERGIE_EXPORTEE": Tag("ENERGIE_EXPORTEE", 0.0, "Wh", "Energie exportee reseau"),
            "NUAGE_FACTOR": Tag("NUAGE_FACTOR", 1.0, "", "Facteur ombre nuages (0-1)"),
            "UDP_EN_LIGNE": Tag("UDP_EN_LIGNE", False, "", "Source connectee"),
            "SOURCE_DONNEES": Tag("SOURCE_DONNEES", "SIMULATION", "", "Source donnees"),
        }

        self._energie_pv_acc = 0.0
        self._energie_eol_acc = 0.0
        self._energie_imp_acc = 0.0
        self._energie_exp_acc = 0.0

    def set_tag(self, name: str, value: Any) -> None:
        if name in self.tags:
            self.tags[name].value = value

    def get_tag(self, name: str) -> Any:
        return self.tags[name].value if name in self.tags else None

    def set_pv_cut(self, cut: bool) -> None:
        if "PV_CUT" not in self.tags:
            self.tags["PV_CUT"] = Tag("PV_CUT", False, "", "Commande coupure PV")
        self.pv_cut = bool(cut)
        self.set_tag("PV_CUT", self.pv_cut)
        if self.pv_cut:
            self.set_tag("P_PV", 0.0)
            self.set_tag("P_TOTALE_ER", round(float(self.get_tag("P_EOLIEN") or 0.0), 2))

    def start(self) -> None:
        self.mode = PLCMode.RUN

    def stop(self) -> None:
        self.mode = PLCMode.STOP

    def reset_fault(self) -> None:
        if self.mode == PLCMode.FAULT:
            self.alarm.reset_all()
            self.mode = PLCMode.STOP

    def apply_connection_config(self, protocol: str, **kwargs) -> str:
        protocol = (protocol or CommProtocol.UDP).upper()
        if protocol != CommProtocol.UDP:
            raise ValueError(f"Protocole non supporte: {protocol}")

        local_host = str(kwargs.get("local_host", Config.udp.LOCAL_HOST)).strip() or "0.0.0.0"
        local_port = int(kwargs.get("local_port", Config.udp.LOCAL_PORT))
        if not (1 <= local_port <= 65535):
            raise ValueError("Port UDP invalide.")

        self.bridge.reconfigure(local_host, local_port)
        return self.bridge.connection_status

    def apply_udp_config(self, local_host: str, local_port: int) -> str:
        return self.apply_connection_config(CommProtocol.UDP, local_host=local_host, local_port=local_port)

    def _ems_strategy(self, p_pv: float, p_eol: float, p_charge: float) -> float:
        if self.mode_ems != "AUTO":
            return self.puissance_batt_manuelle
        surplus = p_pv + p_eol - p_charge
        if surplus > 0:
            return min(surplus, Config.batterie.PUISSANCE_MAX_CHARGE)
        return max(surplus, -Config.batterie.PUISSANCE_MAX_DECHARGE)

    def _coerce_float(self, data: dict, key: str, default: float) -> float:
        value = data.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _normalize_battery_power_convention(self, p_batt: float) -> tuple[float, str]:
        abs_power = abs(p_batt)
        threshold = 10_000.0 if abs_power >= 1000.0 else 10.0
        if abs_power < 1e-9:
            return 0.0, "REPOS"
        if abs_power > threshold:
            logger.info(
                "[BATTERY SIGN] P_BATTERIE=%.2f interpreted as discharge (abs threshold=%.2f)",
                p_batt,
                threshold,
            )
            return -abs(p_batt), "DECHARGE"
        if abs_power < threshold:
            logger.info(
                "[BATTERY SIGN] P_BATTERIE=%.2f interpreted as charge (abs threshold=%.2f)",
                p_batt,
                threshold,
            )
            return abs_power, "CHARGE"
        return abs(p_batt), "CHARGE"

    def _normalize_external_data(self, payload: dict) -> dict:
        data = {str(key).upper(): value for key, value in payload.items()}

        p_pv = self._coerce_float(data, "P_PV", self.get_tag("P_PV"))
        p_eol = self._coerce_float(data, "P_EOLIEN", self.get_tag("P_EOLIEN"))
        p_charge = self._coerce_float(data, "P_CHARGE", self.get_tag("P_CHARGE"))
        p_batt = self._coerce_float(data, "P_BATTERIE", self.get_tag("P_BATTERIE"))

        soc_raw = self._coerce_float(data, "SOC", self.get_tag("SOC"))
        soc_pct = soc_raw * 100.0 if 0.0 <= soc_raw <= 1.0 else soc_raw
        soc_pct = max(0.0, min(100.0, soc_pct))

        tension = self._coerce_float(data, "TENSION_RESEAU", self.get_tag("TENSION_RESEAU"))
        frequence = self._coerce_float(data, "FREQUENCE_RESEAU", self.get_tag("FREQUENCE_RESEAU"))
        irradiance = self._coerce_float(data, "IRRADIANCE", self.get_tag("IRRADIANCE"))
        vent = self._coerce_float(data, "VITESSE_VENT", self.get_tag("VITESSE_VENT"))
        rotor = self._coerce_float(data, "VITESSE_ROTOR", vent * 8.0)
        temp_batt = self._coerce_float(data, "TEMP_BATTERIE", self.get_tag("TEMP_BATTERIE"))
        temp_module = self._coerce_float(data, "TEMP_MODULE", 25.0 + irradiance * 0.02)
        cycles_batt = self._coerce_float(data, "CYCLES_BATT", self.get_tag("CYCLES_BATT"))
        simulated_time_h = self._coerce_float(
            data,
            "HEURE_SIMULEE",
            self._coerce_float(
                data,
                "SIMULATED_TIME_H",
                self._coerce_float(data, "SIM_TIME_H", self.simulated_time_h),
            ),
        )

        p_reseau = self._coerce_float(data, "P_RESEAU", p_charge + p_batt - p_pv - p_eol)
        taux_er = self._coerce_float(
            data,
            "TAUX_ER",
            min(((p_pv + p_eol) / max(p_charge, 0.1)) * 100.0, 100.0),
        )
        p_batt, etat_batt = self._normalize_battery_power_convention(p_batt)
        p_reseau = p_charge + p_batt - p_pv - p_eol
        taux_er = min(((p_pv + p_eol) / max(p_charge, 0.1)) * 100.0, 100.0)

        return {
            "P_PV": p_pv,
            "P_EOLIEN": p_eol,
            "P_CHARGE": p_charge,
            "P_BATTERIE": p_batt,
            "SOC": soc_pct,
            "TENSION_RESEAU": tension,
            "FREQUENCE_RESEAU": frequence,
            "IRRADIANCE": irradiance,
            "VITESSE_VENT": vent,
            "VITESSE_ROTOR": rotor,
            "TEMP_BATTERIE": temp_batt,
            "TEMP_MODULE": temp_module,
            "CYCLES_BATT": cycles_batt,
            "HEURE_SIMULEE": simulated_time_h % 24.0,
            "P_RESEAU": p_reseau,
            "TAUX_ER": taux_er,
            "ETAT_BATT": etat_batt,
            "P_TOTALE_ER": round(p_pv + p_eol, 2),
            "FAULT": bool(data.get("FAULT", False)),
        }

    def scan(self) -> bool:
        if self.mode != PLCMode.RUN:
            return False

        t_start = time.perf_counter()
        dt = Config.SCAN_TIME

        try:
            remote_data = self.bridge.get_latest()
            remote_ok = self.bridge.is_remote_online and remote_data is not None
            remote_stale = (not remote_ok) and remote_data is not None

            self.set_tag("UDP_EN_LIGNE", remote_ok)
            if remote_ok:
                source_name = "UDP / SIMULINK"
            elif remote_stale:
                source_name = "UDP / LAST FRAME"
            else:
                source_name = "SIMULATION"
            self.set_tag("SOURCE_DONNEES", source_name)
            if self._last_source_logged != source_name:
                self._last_source_logged = source_name
                logger.info("[SCADA SOURCE] %s", source_name)

            if remote_ok or remote_stale:
                values = self._normalize_external_data(remote_data)
                remote_keys = {str(key).upper() for key in remote_data.keys()}

                for key, value in values.items():
                    if key != "FAULT":
                        self.set_tag(key, value)

                p_pv = values["P_PV"]
                p_eol = values["P_EOLIEN"]
                p_charge = values["P_CHARGE"]
                p_batt = values["P_BATTERIE"]
                soc_for_logic = values["SOC"]
                tension = values["TENSION_RESEAU"]
                p_reseau = values["P_RESEAU"]
                taux_er = values["TAUX_ER"]
                irr = values["IRRADIANCE"]
                vent = values["VITESSE_VENT"]
                self.simulated_time_h = float(values["HEURE_SIMULEE"])
                if not {"HEURE_SIMULEE", "SIMULATED_TIME_H", "SIM_TIME_H"} & remote_keys and not remote_stale:
                    self.simulated_time_h = (self.simulated_time_h + dt / 3600.0) % 24.0

                # Keep the internal battery model aligned with remote measurements so
                # alarms and later fallback scans stay coherent.
                self.batterie.soc = max(Config.batterie.SOC_MIN, min(Config.batterie.SOC_MAX, soc_for_logic / 100.0))
                self.batterie.puissance = p_batt
                self.batterie.temperature = float(values["TEMP_BATTERIE"])
                self.batterie.cycles = float(values["CYCLES_BATT"])
                self.batterie.etat = str(values["ETAT_BATT"])

                if remote_ok and values["FAULT"]:
                    self.mode = PLCMode.FAULT
            else:
                nuage = float(self.get_tag("NUAGE_FACTOR"))
                pv_r = self.pv.step(dt=dt, nuage_factor=nuage)
                eol_r = self.eolien.step(dt=dt)
                chg_r = self.charge.step(dt=dt)

                p_pv = pv_r["puissance_pv"]
                p_eol = eol_r["puissance_eolien"]
                p_charge = chg_r["puissance_charge"]

                if self.pv_cut:
                    p_pv = 0.0

                p_batt_cmd = self._ems_strategy(p_pv, p_eol, p_charge)
                batt_r = self.batterie.charger(p_batt_cmd, dt=dt)
                res_r = self.reseau.equilibrer(p_pv, p_eol, batt_r["puissance_batterie"], p_charge)

                p_batt = batt_r["puissance_batterie"]
                soc_for_logic = batt_r["soc"]
                tension = res_r["tension_reseau"]
                p_reseau = res_r["puissance_reseau"]
                taux_er = res_r["taux_renouvelable"]
                irr = pv_r["irradiance"]
                vent = eol_r["vitesse_vent"]
                self.simulated_time_h = self.pv.heure_simulee

                self.set_tag("P_PV", p_pv)
                self.set_tag("IRRADIANCE", irr)
                self.set_tag("TEMP_MODULE", pv_r["temperature_module"])
                self.set_tag("P_EOLIEN", p_eol)
                self.set_tag("VITESSE_VENT", vent)
                self.set_tag("VITESSE_ROTOR", eol_r["vitesse_rotor"])
                self.set_tag("SOC", batt_r["soc"])
                self.set_tag("P_BATTERIE", p_batt)
                self.set_tag("TEMP_BATTERIE", batt_r["temperature_batterie"])
                self.set_tag("CYCLES_BATT", batt_r["cycles_batterie"])
                self.set_tag("ETAT_BATT", batt_r["etat_batterie"])
                self.set_tag("P_CHARGE", p_charge)
                self.set_tag("P_RESEAU", p_reseau)
                self.set_tag("TENSION_RESEAU", tension)
                self.set_tag("FREQUENCE_RESEAU", res_r["frequence_reseau"])
                self.set_tag("TAUX_ER", taux_er)
                self.set_tag("P_TOTALE_ER", round(p_pv + p_eol, 2))

            if self.pv_cut:
                p_pv = 0.0
                p_reseau = p_charge + p_batt - p_pv - p_eol
                taux_er = min(((p_pv + p_eol) / max(p_charge, 0.1)) * 100.0, 100.0)
                self.set_tag("P_PV", p_pv)
                self.set_tag("P_RESEAU", p_reseau)
                self.set_tag("TAUX_ER", taux_er)
                self.set_tag("P_TOTALE_ER", round(p_pv + p_eol, 2))
                self.set_tag("PV_CUT", True)
            else:
                self.set_tag("PV_CUT", False)

            if not remote_stale:
                self._energie_pv_acc += p_pv * dt / 3600.0
                self._energie_eol_acc += p_eol * dt / 3600.0
                if p_reseau > 0:
                    self._energie_imp_acc += p_reseau * dt / 3600.0
                else:
                    self._energie_exp_acc += (-p_reseau) * dt / 3600.0

            self.set_tag("ENERGIE_PV", round(self._energie_pv_acc, 2))
            self.set_tag("ENERGIE_EOLIEN", round(self._energie_eol_acc, 2))
            self.set_tag("ENERGIE_IMPORTEE", round(self._energie_imp_acc, 2))
            self.set_tag("ENERGIE_EXPORTEE", round(self._energie_exp_acc, 2))

            self.alarm.check(
                {
                    "SOC": soc_for_logic,
                    "TEMP_BATTERIE": float(self.get_tag("TEMP_BATTERIE")),
                    "TENSION_RESEAU": tension,
                    "FREQUENCE_RESEAU": float(self.get_tag("FREQUENCE_RESEAU")),
                    "PUISSANCE_RESEAU": p_reseau,
                    "VITESSE_VENT": vent,
                }
            )

            crit = [event for event in self.alarm.active if event.level == AlarmLevel.CRITICAL and not event.acked]
            if crit:
                self.mode = PLCMode.FAULT

            if not remote_stale:
                self.hist.log(
                    {
                        "puissance_pv": p_pv,
                        "puissance_eolien": p_eol,
                        "puissance_batterie": p_batt,
                        "puissance_charge": p_charge,
                        "puissance_reseau": p_reseau,
                        "soc": soc_for_logic,
                        "irradiance": irr,
                        "vitesse_vent": vent,
                        "temperature_batterie": float(self.get_tag("TEMP_BATTERIE")),
                        "tension_reseau": tension,
                        "frequence_reseau": float(self.get_tag("FREQUENCE_RESEAU")),
                        "taux_renouvelable": taux_er,
                    }
                )

            self.scan_count += 1
            self.last_scan_duration_ms = (time.perf_counter() - t_start) * 1000.0
            return True
        except Exception as exc:
            logger.error("[SCAN] Exception: %s", exc)
            self.mode = PLCMode.FAULT
            return False

    @property
    def snapshot(self) -> dict:
        snap = {
            key: (round(tag.value, 3) if isinstance(tag.value, float) else tag.value)
            for key, tag in self.tags.items()
        }
        snap["HEURE_SIMULEE"] = round(self.simulated_time_h, 3)
        return snap
