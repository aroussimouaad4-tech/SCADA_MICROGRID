"""
Analytiques — SCADA Microgrid ER
KPIs énergétiques, autosuffisance, prédiction batterie
"""

import numpy as np
import pandas as pd
from config import Config

DRIFT_THRESHOLD_PERCENT = 10.0


def compute_energy_kpi(df: pd.DataFrame, energie_imp: float, energie_exp: float) -> dict:
    """KPIs énergétiques microgrid sur les données de session."""
    if df.empty:
        return {}

    dt_h = Config.SCAN_TIME / 3600.0
    n = len(df)

    e_pv   = df["puissance_pv"].sum()   * dt_h if "puissance_pv"   in df.columns else 0
    e_eol  = df["puissance_eolien"].sum()* dt_h if "puissance_eolien" in df.columns else 0
    e_chg  = df["puissance_charge"].sum()* dt_h if "puissance_charge" in df.columns else 0

    e_gen  = e_pv + e_eol
    taux_autosuffisance = (1.0 - energie_imp / max(e_chg, 0.01)) * 100.0
    taux_autosuffisance = max(0.0, min(100.0, taux_autosuffisance))

    taux_er_moy = df["taux_renouvelable"].mean() if "taux_renouvelable" in df.columns else 0.0
    soc_moy     = df["soc"].mean()                if "soc" in df.columns else 0.0
    soc_min     = df["soc"].min()                 if "soc" in df.columns else 0.0

    return {
        "Énergie PV (Wh)":             round(e_pv, 2),
        "Énergie Éolien (Wh)":         round(e_eol, 2),
        "Énergie totale ER (Wh)":       round(e_gen, 2),
        "Énergie importée (Wh)":        round(energie_imp, 2),
        "Énergie exportée (Wh)":        round(energie_exp, 2),
        "Taux autosuffisance (%)":        round(taux_autosuffisance, 1),
        "Taux ER moyen (%)":             round(taux_er_moy, 1),
        "SoC batterie moyen (%)":        round(soc_moy, 1),
        "SoC min observé (%)":           round(soc_min, 1),
        "Points enregistrés":            n,
    }


def predict_battery(df: pd.DataFrame) -> dict:
    """Prédiction de l'état SOC et durée de vie batterie."""
    if len(df) < 20 or "soc" not in df.columns:
        return {"statut": "Données insuffisantes", "heures_autonomie": None}

    soc = df["soc"].dropna().values
    x = np.arange(len(soc))

    try:
        coeffs = np.polyfit(x, soc, 1)
        slope_par_scan = coeffs[0]
    except (np.linalg.LinAlgError, ValueError):
        return {"statut": "Calcul impossible", "heures_autonomie": None}

    soc_actuel = soc[-1]
    soc_min_pct = Config.batterie.SOC_MIN * 100.0
    slope_par_h = slope_par_scan * 3600.0 / Config.SCAN_TIME

    if slope_par_scan >= 0:
        statut = "🟢 Batterie en charge / stable"
        heures = None
    else:
        points_restants = (soc_actuel - soc_min_pct) / abs(slope_par_scan)
        heures = round(points_restants * Config.SCAN_TIME / 3600.0, 1)
        if heures < 1:
            statut = "🔴 Batterie critique — < 1h d'autonomie"
        elif heures < 4:
            statut = "🟡 Batterie faible — autonomie limitée"
        else:
            statut = "🟢 Autonomie suffisante"

    return {
        "statut": statut,
        "heures_autonomie": heures,
        "soc_actuel": round(soc_actuel, 1),
        "tendance_par_h": round(slope_par_h, 2),
        "soc_min_seuil": round(soc_min_pct, 1),
    }


def detect_solar_drift(df: pd.DataFrame, window: int = 50) -> dict:
    """Détecte une dérive de production PV (panneaux encrassés, dégradation)."""
    if len(df) < window * 2 or "puissance_pv" not in df.columns:
        return {"derive_detectee": False, "message": "Données insuffisantes"}

    # Comparer la production PV récente vs historique normalisée par l'irradiance
    if "irradiance" in df.columns:
        irr = df["irradiance"].replace(0, np.nan)
        perf = (df["puissance_pv"] / irr).dropna()
    else:
        perf = df["puissance_pv"]

    if len(perf) < window * 2:
        return {"derive_detectee": False, "message": "Données insuffisantes"}

    recent   = perf.tail(window).mean()
    historic = perf.head(len(perf) - window).mean()
    drift_pct = (recent - historic) / (historic + 1e-9) * 100.0

    return {
        "derive_detectee": abs(drift_pct) > DRIFT_THRESHOLD_PERCENT,
        "drift_%":         round(drift_pct, 1),
        "message": (
            f"⚠️ Dérive PV de {drift_pct:+.1f}% (encrassement / dégradation ?)"
            if abs(drift_pct) > DRIFT_THRESHOLD_PERCENT
            else "✅ Performance PV nominale"
        ),
    }
