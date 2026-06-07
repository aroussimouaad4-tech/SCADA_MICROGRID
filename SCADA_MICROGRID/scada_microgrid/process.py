"""
Modèles physiques Microgrid Énergies Renouvelables
- Panneau PV (irradiance, température, ombre)
- Éolienne (courbe de puissance, turbulences)
- Batterie BESS (SoC, thermique, dégradation)
- Charge réseau (profil journalier)
- Réseau (tension, fréquence)
"""

import math
import numpy as np
from config import Config

np.random.seed(42)


class PanneauSolaire:
    """Modèle photovoltaïque avec irradiance simulée et effets thermiques."""

    def __init__(self):
        self.puissance = 0.0
        self.irradiance = 0.0          # W/m²
        self.temperature_module = 25.0  # °C
        self.tension_dc = 0.0
        self.degradation = 0.0          # 0→1
        self.heures_service = 0.0

        self._temps = 0.0              # secondes simulées

        # Bruit
        self.noise_irr = 10.0
        self.noise_temp = 0.5

    def _profil_irradiance(self, t_sec: float) -> float:
        """Profil sinusoïdal journalier (pic à midi)."""
        heure = (t_sec / 3600.0) % 24.0
        if heure < 6.0 or heure > 20.0:
            return 0.0
        # Profil en cloche entre 6h et 20h
        angle = math.pi * (heure - 6.0) / 14.0
        ghi_max = 900.0  # W/m² pic
        return ghi_max * math.sin(angle) ** 1.2

    def step(self, dt: float = 1.0, nuage_factor: float = 1.0) -> dict:
        self._temps += dt
        self.heures_service += dt / 3600.0

        # Irradiance
        irr_base = self._profil_irradiance(self._temps) * nuage_factor
        self.irradiance = max(0.0, irr_base + np.random.normal(0, self.noise_irr))
        self.irradiance = min(self.irradiance, 1200.0)

        # Température module : NOCT model
        temp_amb = 20.0 + 8.0 * math.sin(2 * math.pi * (self._temps / 3600 - 14) / 24)
        noct = 45.0
        self.temperature_module = temp_amb + (noct - 20.0) * self.irradiance / 800.0
        self.temperature_module += np.random.normal(0, self.noise_temp)

        # Puissance PV : modèle simplifié
        eff_temp = 1.0 + Config.solaire.TEMP_COEFF * (
            self.temperature_module - Config.solaire.TEMP_REF
        )
        eff_deg = 1.0 - 0.20 * self.degradation  # dégradation max 20%
        puissance_brute = (
            self.irradiance
            * Config.solaire.SURFACE_TOTALE
            * Config.solaire.RENDEMENT_PANNEAUX
            * eff_temp * eff_deg
            / 10000.0  # → kW
        )
        self.puissance = max(0.0, min(puissance_brute, Config.solaire.PUISSANCE_CRETE))

        # Tension DC (simplifiée)
        self.tension_dc = 600.0 * (0.7 + 0.3 * self.irradiance / 1000.0)

        # Dégradation lente
        self.degradation = min(1.0, self.degradation + 1e-9 * dt)

        return {
            "puissance_pv": round(self.puissance, 2),
            "irradiance": round(self.irradiance, 1),
            "temperature_module": round(self.temperature_module, 1),
            "tension_dc": round(self.tension_dc, 1),
        }

    @property
    def heure_simulee(self) -> float:
        return (self._temps / 3600.0) % 24.0


class Eolienne:
    """Modèle d'éolienne avec courbe de puissance et turbulences."""

    def __init__(self):
        self.puissance = 0.0
        self.vitesse_vent = 5.0        # m/s
        self.vitesse_rotor = 0.0       # tr/min
        self.angle_pale = 0.0          # degrés
        self.vibration = 0.1
        self.usure = 0.0
        self.heures_service = 0.0

        self._vent_base = 7.0           # vent moyen simulé
        self._turbulence = 1.5          # écart-type turbulence

    def _courbe_puissance(self, v: float) -> float:
        """Courbe de puissance normalisée (cubique entre v_d et v_n)."""
        v_d = Config.eolien.VITESSE_DEMARRAGE
        v_n = Config.eolien.VITESSE_NOMINALE
        v_c = Config.eolien.VITESSE_COUPURE
        p_n = Config.eolien.PUISSANCE_NOMINALE

        if v < v_d or v >= v_c:
            return 0.0
        if v >= v_n:
            return p_n
        # Interpolation cubique
        ratio = (v - v_d) / (v_n - v_d)
        return p_n * ratio ** 3

    def step(self, dt: float = 1.0) -> dict:
        self.heures_service += dt / 3600.0

        # Simulation vent (AR(1) + turbulences)
        self.vitesse_vent = max(
            0.0,
            0.98 * self.vitesse_vent + 0.02 * self._vent_base
            + np.random.normal(0, self._turbulence * math.sqrt(dt))
        )

        # Puissance
        puissance_cible = self._courbe_puissance(self.vitesse_vent)
        # Inertie mécanique
        self.puissance += 0.05 * (puissance_cible - self.puissance)
        self.puissance = max(0.0, self.puissance)

        # Vitesse rotor (proportionnelle au vent)
        self.vitesse_rotor = max(0.0, self.vitesse_vent * 8.0)  # tr/min simplifié

        # Vibrations
        vib_base = 0.1 + 2.0 * (self.puissance / Config.eolien.PUISSANCE_NOMINALE)
        self.vibration = vib_base + 3.0 * self.usure ** 2 + abs(np.random.normal(0, 0.05))

        # Usure
        charge = self.puissance / Config.eolien.PUISSANCE_NOMINALE
        self.usure = min(1.0, self.usure + 8e-8 * charge * dt)

        return {
            "puissance_eolien": round(self.puissance, 2),
            "vitesse_vent": round(self.vitesse_vent, 1),
            "vitesse_rotor": round(self.vitesse_rotor, 1),
            "vibration_eolien": round(self.vibration, 2),
            "usure_eolien": round(self.usure * 100, 2),
        }

    @property
    def etat_sante(self) -> str:
        if self.usure < 0.30: return "BON"
        if self.usure < 0.60: return "SURVEILLER"
        if self.usure < 0.85: return "DÉGRADÉ"
        return "CRITIQUE"


class BatterieESS:
    """Batterie de stockage BESS — modèle SoC, thermique, dégradation."""

    def __init__(self):
        self.soc = Config.batterie.SOC_INIT          # State of Charge 0→1
        self.puissance = 0.0                          # kW (+ = charge, - = décharge)
        self.tension = 750.0                          # V DC bus
        self.temperature = Config.batterie.TEMP_NOMINALE
        self.cycles = 0.0                             # cycles équivalents
        self.degradation = 0.0                        # 0→1
        self.etat = "REPOS"                           # CHARGE / DECHARGE / REPOS

        self._tau_thermique = 200.0                   # secondes
        self._delta_soc_cycle = 0.0                   # pour compter les demi-cycles

    def charger(self, puissance_kw: float, dt: float = 1.0) -> dict:
        """Applique une puissance de charge (+) ou décharge (-)."""
        # Limites
        p_cmd = max(
            -Config.batterie.PUISSANCE_MAX_DECHARGE,
            min(Config.batterie.PUISSANCE_MAX_CHARGE, puissance_kw)
        )

        self.puissance = p_cmd

        # Mise à jour SoC
        rend = Config.batterie.RENDEMENT_CHARGE if p_cmd >= 0 else Config.batterie.RENDEMENT_DECHARGE
        delta_kwh = p_cmd * rend * dt / 3600.0
        delta_soc = delta_kwh / Config.batterie.CAPACITE_WH

        # Autodécharge
        self.soc -= Config.batterie.TAUX_AUTODECHARGEMENT * dt

        self.soc = max(Config.batterie.SOC_MIN,
                       min(Config.batterie.SOC_MAX, self.soc + delta_soc))

        # Cycles (demi-cycle = ΔSoC cumulé)
        self._delta_soc_cycle += abs(delta_soc)
        if self._delta_soc_cycle >= 1.0:
            self.cycles += self._delta_soc_cycle
            self._delta_soc_cycle = 0.0

        # Dégradation (linéaire + cycles)
        self.degradation = min(1.0, self.degradation + 2e-7 * abs(p_cmd) * dt + 1e-6 * abs(delta_soc))

        # Thermique
        temp_amb = 22.0
        dissipation = 0.05 * p_cmd ** 2 / (Config.batterie.PUISSANCE_MAX_CHARGE + 1)
        temp_cible = temp_amb + 20.0 * abs(p_cmd / Config.batterie.PUISSANCE_MAX_CHARGE) + dissipation
        alpha = dt / self._tau_thermique
        self.temperature += alpha * (temp_cible - self.temperature)
        self.temperature += np.random.normal(0, 0.2)

        # Tension (modèle linéaire SoC)
        self.tension = 700.0 + 100.0 * self.soc

        # État
        if p_cmd > 1.0:
            self.etat = "CHARGE"
        elif p_cmd < -1.0:
            self.etat = "DÉCHARGE"
        else:
            self.etat = "REPOS"

        capacite_restante = Config.batterie.CAPACITE_WH * (1.0 - 0.20 * self.degradation)
        energie_disponible = capacite_restante * (self.soc - Config.batterie.SOC_MIN)

        return {
            "soc": round(self.soc * 100, 1),
            "puissance_batterie": round(self.puissance, 2),
            "tension_batterie": round(self.tension, 1),
            "temperature_batterie": round(self.temperature, 1),
            "cycles_batterie": round(self.cycles, 1),
            "degradation_batterie": round(self.degradation * 100, 2),
            "energie_disponible": round(energie_disponible, 1),
            "etat_batterie": self.etat,
        }

    @property
    def soc_pct(self) -> float:
        return self.soc * 100.0


class ChargeReseau:
    """Profil de charge réseau avec variation journalière."""

    def __init__(self):
        self.puissance = Config.charge.PUISSANCE_BASE
        self._temps = 0.0

    def step(self, dt: float = 1.0) -> dict:
        self._temps += dt
        heure = (self._temps / 3600.0) % 24.0

        # Profil journalier typique
        if 0 <= heure < 6:
            facteur = 0.4   # nuit
        elif 6 <= heure < 9:
            facteur = 0.7   # matin
        elif 9 <= heure < 12:
            facteur = 0.85
        elif 12 <= heure < 14:
            facteur = 0.9   # midi
        elif 14 <= heure < 18:
            facteur = 0.85
        elif 18 <= heure < 21:
            facteur = 1.0   # soirée (crête)
        else:
            facteur = 0.6

        bruit = np.random.normal(0, 3.0)
        self.puissance = max(
            0.0,
            Config.charge.PUISSANCE_CRETE * facteur + bruit
        )
        return {"puissance_charge": round(self.puissance, 1)}


class ReseauElectrique:
    """Modèle réseau : tension, fréquence, import/export."""

    def __init__(self):
        self.tension = Config.reseau.TENSION_NOMINALE
        self.frequence = Config.reseau.FREQUENCE_NOMINALE
        self.puissance_echange = 0.0    # kW (+ = import, - = export)

    def equilibrer(self, p_pv: float, p_eol: float, p_batt: float, p_charge: float) -> dict:
        """
        Calcule l'échange réseau pour équilibrer le microgrid.
        p_batt : positif = batterie charge (consomme), négatif = décharge (fourni)
        """
        # Bilan : génération - consommation - charge batterie
        p_gen = p_pv + p_eol
        p_batt_inject = -p_batt  # si batterie décharge, elle injecte
        bilan = p_gen + p_batt_inject - p_charge

        # Échange réseau = déficit ou surplus
        self.puissance_echange = -bilan   # import si négatif, export si positif
        self.puissance_echange = max(
            -Config.reseau.PUISSANCE_MAX_EXPORT,
            min(Config.reseau.PUISSANCE_MAX_IMPORT, self.puissance_echange)
        )

        # Tension/fréquence : légères variations selon charge
        desequilibre = self.puissance_echange / Config.reseau.PUISSANCE_MAX_IMPORT
        self.tension = Config.reseau.TENSION_NOMINALE * (1.0 - 0.03 * desequilibre)
        self.tension += np.random.normal(0, 0.5)
        self.frequence = Config.reseau.FREQUENCE_NOMINALE - 0.1 * desequilibre
        self.frequence += np.random.normal(0, 0.02)

        taux_renouvelable = (p_gen / max(p_charge, 0.1)) * 100.0

        return {
            "puissance_reseau": round(self.puissance_echange, 1),
            "tension_reseau": round(self.tension, 1),
            "frequence_reseau": round(self.frequence, 2),
            "taux_renouvelable": round(min(taux_renouvelable, 100.0), 1),
        }
