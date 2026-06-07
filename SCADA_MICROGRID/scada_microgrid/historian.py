"""
Historien de données — SCADA Microgrid ER
"""

import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from config import Config


class Historian:
    def __init__(self, db_path: str = Config.DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS process_data (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts                  TEXT NOT NULL,
                    puissance_pv        REAL,
                    puissance_eolien    REAL,
                    puissance_batterie  REAL,
                    puissance_charge    REAL,
                    puissance_reseau    REAL,
                    soc                 REAL,
                    irradiance          REAL,
                    vitesse_vent        REAL,
                    temperature_batterie REAL,
                    tension_reseau      REAL,
                    frequence_reseau    REAL,
                    taux_renouvelable   REAL
                );
                CREATE INDEX IF NOT EXISTS idx_ts ON process_data(ts);

                CREATE TABLE IF NOT EXISTS alarms_log (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts      TEXT NOT NULL,
                    tag     TEXT,
                    message TEXT,
                    level   TEXT,
                    value   REAL,
                    acked   INTEGER DEFAULT 0,
                    rtn     INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_alarms_ts ON alarms_log(ts);
            """)

    def log(self, data: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO process_data
                   (ts, puissance_pv, puissance_eolien, puissance_batterie,
                    puissance_charge, puissance_reseau, soc, irradiance,
                    vitesse_vent, temperature_batterie, tension_reseau,
                    frequence_reseau, taux_renouvelable)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now().isoformat(timespec="milliseconds"),
                    data.get("puissance_pv"),
                    data.get("puissance_eolien"),
                    data.get("puissance_batterie"),
                    data.get("puissance_charge"),
                    data.get("puissance_reseau"),
                    data.get("soc"),
                    data.get("irradiance"),
                    data.get("vitesse_vent"),
                    data.get("temperature_batterie"),
                    data.get("tension_reseau"),
                    data.get("frequence_reseau"),
                    data.get("taux_renouvelable"),
                ),
            )
        self._auto_cleanup()

    @staticmethod
    def _prepare_trend_df(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.copy()
        df["ts"] = pd.to_datetime(df["ts"], format="ISO8601", errors="coerce")
        df = df.dropna(subset=["ts"])
        df = df.sort_values(["ts", "id"]).reset_index(drop=True)

        numeric_cols = [
            col for col in df.select_dtypes(include="number").columns
            if col != "id"
        ]
        if not numeric_cols:
            return df.drop_duplicates(subset=["ts"], keep="last").reset_index(drop=True)

        # Collapse points that share the same timestamp so Plotly does not draw
        # vertical jumps between multiple values located on the exact same x-position.
        aggregated = (
            df.groupby("ts", as_index=False)[numeric_cols]
            .mean()
            .sort_values("ts")
            .reset_index(drop=True)
        )
        return aggregated

    def _auto_cleanup(self):
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM process_data").fetchone()[0]
            if count > Config.DB_MAX_ROWS:
                excess = count - Config.DB_MAX_ROWS
                conn.execute(
                    f"DELETE FROM process_data WHERE id IN "
                    f"(SELECT id FROM process_data ORDER BY id ASC LIMIT {excess})"
                )

    def get_last_n(self, n: int = 300) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql(
                f"SELECT * FROM process_data ORDER BY id DESC LIMIT {n}", conn
            )
        if df.empty:
            return df
        df = df.iloc[::-1].reset_index(drop=True)
        return self._prepare_trend_df(df)

    def get_range(self, minutes: int = 60) -> pd.DataFrame:
        since = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql(
                "SELECT * FROM process_data WHERE ts >= ? ORDER BY ts",
                conn, params=(since,),
            )
        if df.empty:
            return df
        return self._prepare_trend_df(df)

    def get_all(self) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql("SELECT * FROM process_data ORDER BY id ASC", conn)

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM process_data").fetchone()[0]
