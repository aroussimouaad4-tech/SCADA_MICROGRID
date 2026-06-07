"""
Centralized configuration for the SCADA microgrid dashboard.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SolaireConfig:
    PUISSANCE_CRETE: float = 100.0
    SURFACE_TOTALE: float = 500.0
    RENDEMENT_PANNEAUX: float = 0.20
    TEMP_COEFF: float = -0.0035
    TEMP_REF: float = 25.0


@dataclass(frozen=True)
class EolienConfig:
    PUISSANCE_NOMINALE: float = 50.0
    VITESSE_DEMARRAGE: float = 3.0
    VITESSE_NOMINALE: float = 12.0
    VITESSE_COUPURE: float = 25.0
    RAYON_ROTOR: float = 10.0
    RENDEMENT: float = 0.40


@dataclass(frozen=True)
class BatterieConfig:
    CAPACITE_WH: float = 200.0
    PUISSANCE_MAX_CHARGE: float = 50.0
    PUISSANCE_MAX_DECHARGE: float = 80.0
    SOC_MIN: float = 0.15
    SOC_MAX: float = 0.95
    SOC_INIT: float = 0.60
    RENDEMENT_CHARGE: float = 0.96
    RENDEMENT_DECHARGE: float = 0.96
    TAUX_AUTODECHARGEMENT: float = 1e-5
    TEMP_NOMINALE: float = 25.0


@dataclass(frozen=True)
class ChargeConfig:
    PUISSANCE_BASE: float = 60.0
    PUISSANCE_CRETE: float = 140.0
    FACTEUR_PUISSANCE: float = 0.95


@dataclass(frozen=True)
class ReseauConfig:
    TENSION_NOMINALE: float = 400.0
    FREQUENCE_NOMINALE: float = 50.0
    PUISSANCE_MAX_IMPORT: float = 100.0
    PUISSANCE_MAX_EXPORT: float = 80.0


@dataclass(frozen=True)
class AlarmConfig:
    SOC_BAS: float = 0.20
    SOC_TRES_BAS: float = 0.15
    SOC_PLEIN: float = 0.93
    TEMP_BATTERIE_HAUTE: float = 45.0
    TEMP_BATTERIE_CRITIQUE: float = 55.0
    TENSION_BASSE: float = 380.0
    TENSION_HAUTE: float = 420.0
    FREQUENCE_BASSE: float = 49.5
    FREQUENCE_HAUTE: float = 50.5
    PUISSANCE_IMPORT_MAX: float = 90.0
    VENT_TEMPETE: float = 22.0


@dataclass(frozen=True)
class HistorianConfig:
    DB_PATH: str = "historian_mg.db"
    DB_MAX_ROWS: int = 100_000


@dataclass
class UDPConfig:
    LOCAL_HOST: str = "127.0.0.1"
    LOCAL_PORT: int = 5005
    BUFFER_SIZE: int = 8192
    TIMEOUT_SEC: float = 5.0


@dataclass
class CommConfig:
    PROTOCOL: str = "UDP"


class Config:
    solaire = SolaireConfig()
    eolien = EolienConfig()
    batterie = BatterieConfig()
    charge = ChargeConfig()
    reseau = ReseauConfig()
    alarms = AlarmConfig()
    historian = HistorianConfig()
    udp = UDPConfig()
    comm = CommConfig()

    SCAN_TIME: int = 1
    HEURES_MAINTENANCE: int = 8760

    PUISSANCE_SOLAIRE_MAX = solaire.PUISSANCE_CRETE
    PUISSANCE_EOLIEN_MAX = eolien.PUISSANCE_NOMINALE
    CAPACITE_BATTERIE = batterie.CAPACITE_WH
    SOC_MIN = batterie.SOC_MIN
    SOC_MAX = batterie.SOC_MAX
    ALARM_SOC_BAS = alarms.SOC_BAS
    ALARM_TEMP_BATTERIE = alarms.TEMP_BATTERIE_HAUTE
    DB_PATH = historian.DB_PATH
    DB_MAX_ROWS = historian.DB_MAX_ROWS
