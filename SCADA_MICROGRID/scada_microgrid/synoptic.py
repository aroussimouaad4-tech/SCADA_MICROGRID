"""SVG synoptic view for the SCADA dashboard."""


def _bar(x: int, y: int, w: int, h: int, fill: str, pct: float) -> str:
    filled_h = h * min(1.0, max(0.0, pct / 100.0))
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#16202a" rx="4"/>'
        f'<rect x="{x}" y="{y + h - filled_h:.0f}" width="{w}" height="{filled_h:.0f}" fill="{fill}" rx="4"/>'
    )


def draw_synoptic(
    p_pv: float = 0.0,
    p_eolien: float = 0.0,
    soc: float = 50.0,
    p_batterie: float = 0.0,
    p_charge: float = 0.0,
    p_reseau: float = 0.0,
    vitesse_vent: float = 0.0,
    taux_er: float = 0.0,
    mode=None,
    etat_batt: str = "IDLE",
) -> str:
    mode_str = str(mode)
    mode_color = "#54d28d" if mode_str == "RUN" else "#ff7b72" if mode_str == "FAULT" else "#9daab6"
    etat_batt_norm = str(etat_batt).strip().upper()
    if etat_batt_norm in {"CHARGE", "CHARGING"}:
        batt_direction = "charge"
    elif etat_batt_norm in {"DECHARGE", "DÉCHARGE", "DISCHARGE", "DISCHARGING"}:
        batt_direction = "discharge"
    else:
        batt_direction = "idle"

    if batt_direction == "idle":
        batt_direction = "charge" if p_batterie > 0 else "discharge" if p_batterie < 0 else "idle"

    batt_color = "#f4b74a" if batt_direction == "charge" else "#54d28d" if batt_direction == "discharge" else "#9daab6"
    batt_label = "Charging" if batt_direction == "charge" else "Discharging" if batt_direction == "discharge" else "Idle"
    batt_flow_label = "Charge" if batt_direction == "charge" else "Discharge" if batt_direction == "discharge" else "Idle"
    grid_color = "#ff7b72" if p_reseau > 0 else "#54d28d"
    grid_label = "Import" if p_reseau > 0 else "Export"
    soc_color = "#54d28d" if soc > 40 else "#f4b74a" if soc > 20 else "#ff7b72"
    net_balance = p_pv + p_eolien - p_charge

    grid_arrow = "url(#arr-red)" if p_reseau > 0 else "url(#arr-green)"
    battery_arrow = "url(#arr-batt-gold)" if batt_direction == "charge" else "url(#arr-batt-green)" if batt_direction == "discharge" else ""
    battery_line = (
        f'<line x1="460" y1="216" x2="460" y2="244" '
        f'stroke="{batt_color}" stroke-width="2.4" stroke-dasharray="3,4" stroke-linecap="round" '
        f'marker-end="{battery_arrow}"/>'
        if batt_direction == "charge"
        else
        f'<line x1="460" y1="244" x2="460" y2="216" '
        f'stroke="{batt_color}" stroke-width="2.4" stroke-dasharray="3,4" stroke-linecap="round" '
        f'marker-end="{battery_arrow}"/>'
        if batt_direction == "discharge"
        else
        f'<line x1="460" y1="216" x2="460" y2="244" '
        f'stroke="{batt_color}" stroke-width="1.5" stroke-dasharray="2,6" stroke-linecap="round"/>'
    )
    grid_line = (
        f'<line x1="658" y1="238" x2="548" y2="168" '
        f'stroke="{grid_color}" stroke-width="3" stroke-dasharray="6,5" '
        f'stroke-linecap="round" marker-end="{grid_arrow}"/>'
        if p_reseau > 0
        else
        f'<line x1="548" y1="168" x2="658" y2="238" '
        f'stroke="{grid_color}" stroke-width="3" stroke-dasharray="6,5" '
        f'stroke-linecap="round" marker-end="{grid_arrow}"/>'
    )

    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 320" width="100%" height="100%">
      <defs>
        <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="#0d1820"/>
          <stop offset="100%" stop-color="#08131b"/>
        </linearGradient>
        <radialGradient id="glow-green" cx="50%" cy="50%" r="65%">
          <stop offset="0%" stop-color="rgba(84,210,141,0.36)"/>
          <stop offset="100%" stop-color="rgba(84,210,141,0)"/>
        </radialGradient>
        <radialGradient id="glow-gold" cx="50%" cy="50%" r="65%">
          <stop offset="0%" stop-color="rgba(244,183,74,0.32)"/>
          <stop offset="100%" stop-color="rgba(244,183,74,0)"/>
        </radialGradient>
        <radialGradient id="glow-blue" cx="50%" cy="50%" r="65%">
          <stop offset="0%" stop-color="rgba(87,183,255,0.28)"/>
          <stop offset="100%" stop-color="rgba(87,183,255,0)"/>
        </radialGradient>
        <marker id="arr-gold" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="#f4b74a"/>
        </marker>
        <marker id="arr-batt-gold" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#f4b74a"/>
        </marker>
        <marker id="arr-blue" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="#57b7ff"/>
        </marker>
        <marker id="arr-green" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="#54d28d"/>
        </marker>
        <marker id="arr-batt-green" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#54d28d"/>
        </marker>
        <marker id="arr-red" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="#ff7b72"/>
        </marker>
      </defs>

      <rect width="920" height="320" fill="url(#bg)" rx="26"/>
      <circle cx="148" cy="82" r="84" fill="url(#glow-gold)"/>
      <circle cx="148" cy="236" r="84" fill="url(#glow-blue)"/>
      <circle cx="720" cy="234" r="96" fill="url(#glow-green)"/>
      <rect x="14" y="14" width="892" height="292" fill="none" stroke="rgba(148, 173, 165, 0.22)" rx="22"/>
      <rect x="24" y="24" width="872" height="272" fill="none" stroke="rgba(255,255,255,0.03)" rx="18"/>

      <text x="28" y="38" fill="#9bc3b5" font-size="11" font-family="Segoe UI, sans-serif" letter-spacing="3">
        LIVE ENERGY MAP
      </text>
      <text x="28" y="58" fill="#eef8f4" font-size="18" font-family="Georgia, serif" font-weight="700">
        Microgrid energy flow
      </text>
      <circle cx="838" cy="34" r="8" fill="{mode_color}"/>
      <text x="854" y="39" fill="{mode_color}" font-size="12" font-family="Consolas, monospace">{mode_str}</text>
      <text x="760" y="58" fill="#88a79e" font-size="11" font-family="Segoe UI, sans-serif">Net balance {net_balance:+.1f} W</text>

      <rect x="28" y="64" width="170" height="88" fill="#101c27" stroke="#f4b74a" stroke-width="1.5" rx="18"/>
      <text x="113" y="88" fill="#f4b74a" font-size="20" font-family="Segoe UI, sans-serif" text-anchor="middle" letter-spacing="2" font-weight="700">SOLAR</text>
      <text x="113" y="110" fill="#f4b74a" font-size="18" font-family="Segoe UI, sans-serif" text-anchor="middle" font-weight="600">Solar PV</text>
      <text x="113" y="130" fill="#f8fbfc" font-size="16" font-family="Consolas, monospace" text-anchor="middle">{p_pv:.1f} W</text>
      <text x="113" y="143" fill="#90a9a0" font-size="12" font-family="Segoe UI, sans-serif" text-anchor="middle">Irradiance driven source</text>

      <rect x="28" y="182" width="170" height="88" fill="#101c27" stroke="#57b7ff" stroke-width="1.5" rx="18"/>
      <text x="113" y="206" fill="#57b7ff" font-size="20" font-family="Segoe UI, sans-serif" text-anchor="middle" letter-spacing="2" font-weight="700">WIND</text>
      <text x="113" y="228" fill="#57b7ff" font-size="18" font-family="Segoe UI, sans-serif" text-anchor="middle" font-weight="600">Wind turbine</text>
      <text x="113" y="248" fill="#f8fbfc" font-size="16" font-family="Consolas, monospace" text-anchor="middle">{p_eolien:.1f} W</text>
      <text x="113" y="261" fill="#90a9a0" font-size="12" font-family="Segoe UI, sans-serif" text-anchor="middle">{vitesse_vent:.1f} m/s wind</text>

      <line x1="198" y1="108" x2="372" y2="142" stroke="#f4b74a" stroke-width="3" stroke-dasharray="6,5" stroke-linecap="round" marker-end="url(#arr-gold)"/>
      <line x1="198" y1="226" x2="372" y2="168" stroke="#57b7ff" stroke-width="3" stroke-dasharray="6,5" stroke-linecap="round" marker-end="url(#arr-blue)"/>

      <rect x="372" y="112" width="176" height="104" fill="#111e29" stroke="#34424d" stroke-width="2" rx="22"/>
      <text x="460" y="136" fill="#8cb1a6" font-size="11" font-family="Segoe UI, sans-serif" text-anchor="middle" letter-spacing="3">POWER HUB</text>
      <text x="460" y="156" fill="#dceee6" font-size="14" font-family="Segoe UI, sans-serif" text-anchor="middle">AC bus</text>
      <text x="460" y="178" fill="#54d28d" font-size="18" font-family="Consolas, monospace" text-anchor="middle">{p_pv + p_eolien:.1f} W RES</text>
      <text x="460" y="198" fill="#f5fbf7" font-size="13" font-family="Segoe UI, sans-serif" text-anchor="middle">Load demand {p_charge:.1f} W</text>
      <text x="460" y="216" fill="#8cb1a6" font-size="13" font-family="Segoe UI, sans-serif" text-anchor="middle">Renewable share {taux_er:.0f}%</text>

      <rect x="372" y="244" width="176" height="58" fill="#111e29" stroke="{soc_color}" stroke-width="1.6" rx="18"/>
      <text x="460" y="264" fill="{soc_color}" font-size="12" font-family="Segoe UI, sans-serif" text-anchor="middle" letter-spacing="2">STORAGE</text>
      {_bar(388, 257, 16, 30, soc_color, soc)}
      <text x="470" y="285" fill="#f5fbf7" font-size="12" font-family="Consolas, monospace" text-anchor="middle">SoC {soc:.0f}% | {batt_label}</text>
      <text x="470" y="299" fill="#88a79e" font-size="11" font-family="Segoe UI, sans-serif" text-anchor="middle">{etat_batt}</text>

      {battery_line}
      <text x="428" y="232" fill="{batt_color}" font-size="10" font-family="Segoe UI, sans-serif" text-anchor="end" font-weight="600">{batt_flow_label}</text>

      <rect x="658" y="96" width="180" height="84" fill="#101c27" stroke="#ff7b72" stroke-width="1.5" rx="18"/>
      <text x="748" y="120" fill="#ff7b72" font-size="20" font-family="Segoe UI, sans-serif" text-anchor="middle" letter-spacing="2" font-weight="700">DEMAND</text>
      <text x="748" y="142" fill="#ff7b72" font-size="18" font-family="Segoe UI, sans-serif" text-anchor="middle" font-weight="600">Facility load</text>
      <text x="748" y="162" fill="#f8fbfc" font-size="16" font-family="Consolas, monospace" text-anchor="middle">{p_charge:.1f} W</text>

      <line x1="548" y1="160" x2="658" y2="138" stroke="#ff7b72" stroke-width="3" stroke-dasharray="6,5" stroke-linecap="round" marker-end="url(#arr-red)"/>

      <rect x="658" y="198" width="180" height="84" fill="#101c27" stroke="{grid_color}" stroke-width="1.5" rx="18"/>
      <text x="748" y="222" fill="{grid_color}" font-size="20" font-family="Segoe UI, sans-serif" text-anchor="middle" letter-spacing="2" font-weight="700">UTILITY</text>
      <text x="748" y="244" fill="{grid_color}" font-size="18" font-family="Segoe UI, sans-serif" text-anchor="middle" font-weight="600">Utility grid</text>
      <text x="748" y="264" fill="#f8fbfc" font-size="16" font-family="Consolas, monospace" text-anchor="middle">{abs(p_reseau):.1f} W</text>
      <text x="748" y="274" fill="{grid_color}" font-size="13" font-family="Segoe UI, sans-serif" text-anchor="middle">{grid_label}</text>

      {grid_line}
    </svg>
    """
