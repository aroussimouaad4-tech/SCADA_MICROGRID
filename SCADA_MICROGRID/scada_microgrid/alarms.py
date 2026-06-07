from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from enum import Enum
import operator
from collections import deque
from config import Config
class AlarmLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ALARM = "ALARM"
    CRITICAL = "CRITICAL"


class Operator(str, Enum):
    GT = ">"
    LT = "<"
    GE = ">="
    LE = "<="
    EQ = "=="


LEVELS: Dict[AlarmLevel, int] = {
    AlarmLevel.INFO: 0,
    AlarmLevel.WARNING: 1,
    AlarmLevel.ALARM: 2,
    AlarmLevel.CRITICAL: 3,
}

COLORS: Dict[AlarmLevel, str] = {
    AlarmLevel.INFO: "🔵",
    AlarmLevel.WARNING: "🟡",
    AlarmLevel.ALARM: "🔴",
    AlarmLevel.CRITICAL: "💀",
}

OPS = {
    Operator.GT: operator.gt,
    Operator.LT: operator.lt,
    Operator.GE: operator.ge,
    Operator.LE: operator.le,
    Operator.EQ: operator.eq,
}


@dataclass(frozen=True)
class AlarmRule:
    tag: str
    tag_name: str
    message: str
    threshold: float
    operator: Operator
    level: AlarmLevel


@dataclass
class AlarmEvent:
    tag: str
    message: str
    level: AlarmLevel
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    acked: bool = False
    rtn: bool = False
    ack_time: Optional[datetime] = None

    @property
    def age_seconds(self) -> float:
        return (datetime.now() - self.timestamp).total_seconds()

    def ack(self):
        self.acked = True
        self.ack_time = datetime.now()

    def __str__(self):
        icon = COLORS.get(self.level, "⚪")
        ack_str = " [ACK]" if self.acked else " [NON ACK]"
        rtn_str = " ✅RTN" if self.rtn else ""
        return (
            f"{icon} [{self.timestamp.strftime('%H:%M:%S')}] "
            f"[{self.level}] {self.message} "
            f"(val={self.value}){ack_str}{rtn_str}"
        )


class AlarmManager:
    def __init__(self):
        self.active: List[AlarmEvent] = []
        self._history: deque = deque(maxlen=500)
        self._active_tags: Set[str] = set()

        self._rules: List[AlarmRule] = [
            # Batterie
            AlarmRule("SOC_BAS",      "SOC",              "Batterie SOC bas",
                      Config.alarms.SOC_BAS * 100,      Operator.LT, AlarmLevel.WARNING),
            AlarmRule("SOC_CRITIQUE", "SOC",              "Batterie SOC critique",
                      Config.alarms.SOC_TRES_BAS * 100, Operator.LT, AlarmLevel.CRITICAL),
            AlarmRule("SOC_PLEIN",    "SOC",              "Batterie presque pleine",
                      Config.alarms.SOC_PLEIN * 100,    Operator.GT, AlarmLevel.INFO),
            AlarmRule("TEMP_BATT_H",  "TEMP_BATTERIE",    "Température batterie haute",
                      Config.alarms.TEMP_BATTERIE_HAUTE,    Operator.GT, AlarmLevel.ALARM),
            AlarmRule("TEMP_BATT_C",  "TEMP_BATTERIE",    "Température batterie CRITIQUE",
                      Config.alarms.TEMP_BATTERIE_CRITIQUE, Operator.GT, AlarmLevel.CRITICAL),
            # Réseau
            AlarmRule("TENSION_BASSE","TENSION_RESEAU",   "Tension réseau basse",
                      Config.alarms.TENSION_BASSE,       Operator.LT, AlarmLevel.ALARM),
            AlarmRule("TENSION_HAUTE","TENSION_RESEAU",   "Tension réseau haute",
                      Config.alarms.TENSION_HAUTE,       Operator.GT, AlarmLevel.ALARM),
            AlarmRule("FREQ_BASSE",   "FREQUENCE_RESEAU", "Fréquence réseau basse",
                      Config.alarms.FREQUENCE_BASSE,     Operator.LT, AlarmLevel.WARNING),
            AlarmRule("FREQ_HAUTE",   "FREQUENCE_RESEAU", "Fréquence réseau haute",
                      Config.alarms.FREQUENCE_HAUTE,     Operator.GT, AlarmLevel.WARNING),
            # Import réseau
            AlarmRule("IMPORT_ELEVE", "PUISSANCE_RESEAU", "Import réseau élevé",
                      Config.alarms.PUISSANCE_IMPORT_MAX, Operator.GT, AlarmLevel.WARNING),
            # Éolienne
            AlarmRule("VENT_TEMPETE", "VITESSE_VENT",     "Vent de tempête — éolienne arrêtée",
                      Config.alarms.VENT_TEMPETE,         Operator.GT, AlarmLevel.ALARM),
        ]

    def _raise(self, tag, message, level, value):
        if tag in self._active_tags:
            return
        evt = AlarmEvent(tag=tag, message=message, level=level, value=round(value, 2))
        self.active.append(evt)
        self._history.append(evt)
        self._active_tags.add(tag)

    def _clear(self, tag):
        if tag not in self._active_tags:
            return
        for evt in self.active:
            if evt.tag == tag:
                evt.rtn = True
                break
        self.active = [e for e in self.active if e.tag != tag]
        self._active_tags.discard(tag)

    def check(self, measurements: Dict[str, float]):
        for rule in self._rules:
            value = measurements.get(rule.tag_name)
            if value is None:
                continue
            op = OPS[rule.operator]
            if op(value, rule.threshold):
                self._raise(rule.tag, f"{rule.message} ({value:.2f})", rule.level, value)
            else:
                self._clear(rule.tag)

    def ack_all(self):
        for evt in self.active:
            evt.ack()

    def ack_by_tag(self, tag):
        for evt in self.active:
            if evt.tag == tag:
                evt.ack()

    def reset_all(self):
        self.active.clear()
        self._active_tags.clear()

    @property
    def history(self):
        return list(self._history)

    @property
    def unacked_count(self):
        return sum(1 for e in self.active if not e.acked)

    @property
    def highest_level(self):
        if not self.active:
            return None
        return max(self.active, key=lambda e: LEVELS[e.level]).level

    @property
    def summary(self):
        counts = {lvl.value: 0 for lvl in AlarmLevel}
        for evt in self.active:
            counts[evt.level.value] += 1
        return counts
