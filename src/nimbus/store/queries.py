import sqlite3
import time

from .schema import Observation


def insert_observation(conn: sqlite3.Connection, obs: Observation) -> None:
    conn.execute(
        """
        INSERT INTO observations (ts, radio, mac_hash, rssi, channel, frame_type, extra_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (obs.ts, obs.radio, obs.mac_hash, obs.rssi, obs.channel, obs.frame_type, obs.extra_json),
    )
    conn.commit()


def upsert_device(
    conn: sqlite3.Connection,
    obs: Observation,
    vendor_oui: str | None,
    inferred_class: str,
) -> None:
    conn.execute(
        """
        INSERT INTO devices (mac_hash, first_seen, last_seen, observation_n, vendor_oui, inferred_class)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(mac_hash) DO UPDATE SET
            last_seen      = excluded.last_seen,
            observation_n  = observation_n + 1,
            vendor_oui     = COALESCE(excluded.vendor_oui, vendor_oui),
            inferred_class = CASE WHEN excluded.inferred_class != 'unknown'
                             THEN excluded.inferred_class ELSE inferred_class END
        """,
        (obs.mac_hash, obs.ts, obs.ts, vendor_oui, inferred_class),
    )
    conn.commit()


def get_present_devices(
    conn: sqlite3.Connection,
    since_ts: int,
    min_observations: int,
) -> list[dict]:  # type: ignore[type-arg]
    cur = conn.execute(
        """
        SELECT
            o.mac_hash,
            d.vendor_oui,
            d.inferred_class,
            MIN(o.rssi)   AS rssi_min,
            MAX(o.rssi)   AS rssi_max,
            CAST(AVG(o.rssi) AS INTEGER) AS rssi_avg,
            MIN(o.ts)     AS first_seen,
            MAX(o.ts)     AS last_seen,
            l.name        AS label,
            COUNT(o.id)   AS obs_count
        FROM observations o
        JOIN devices d ON d.mac_hash = o.mac_hash
        LEFT JOIN labels l ON l.mac_hash = o.mac_hash
        WHERE o.ts >= ?
        GROUP BY o.mac_hash
        HAVING obs_count >= ?
        ORDER BY last_seen DESC
        """,
        (since_ts, min_observations),
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_device(conn: sqlite3.Connection, mac_hash: str) -> dict | None:  # type: ignore[type-arg]
    cur = conn.execute(
        """
        SELECT d.mac_hash, d.vendor_oui, d.inferred_class,
               d.first_seen, d.last_seen, d.observation_n,
               l.name AS label
        FROM devices d
        LEFT JOIN labels l ON l.mac_hash = d.mac_hash
        WHERE d.mac_hash = ?
        """,
        (mac_hash,),
    )
    cols = [c[0] for c in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else None


def get_observations_for_device(
    conn: sqlite3.Connection,
    mac_hash: str,
    since_ts: int,
) -> list[dict]:  # type: ignore[type-arg]
    cur = conn.execute(
        """
        SELECT ts, radio, rssi, channel, frame_type, extra_json
        FROM observations
        WHERE mac_hash = ? AND ts >= ?
        ORDER BY ts ASC
        """,
        (mac_hash, since_ts),
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_presence_timeline(
    conn: sqlite3.Connection,
    mac_hash: str,
    since_ts: int,
    bucket_seconds: int,
) -> list[dict]:  # type: ignore[type-arg]
    cur = conn.execute(
        """
        SELECT
            (ts / ?) * ?  AS bucket_start,
            COUNT(*)      AS observation_count
        FROM observations
        WHERE mac_hash = ? AND ts >= ?
        GROUP BY bucket_start
        ORDER BY bucket_start ASC
        """,
        (bucket_seconds, bucket_seconds, mac_hash, since_ts),
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_regulars(
    conn: sqlite3.Connection,
    since_ts: int,
    min_days_seen: int,
) -> list[dict]:  # type: ignore[type-arg]
    cur = conn.execute(
        """
        SELECT
            o.mac_hash,
            d.vendor_oui,
            d.inferred_class,
            COUNT(DISTINCT DATE(o.ts, 'unixepoch')) AS days_seen,
            l.name AS label
        FROM observations o
        JOIN devices d ON d.mac_hash = o.mac_hash
        LEFT JOIN labels l ON l.mac_hash = o.mac_hash
        WHERE o.ts >= ?
        GROUP BY o.mac_hash
        HAVING days_seen >= ?
        ORDER BY days_seen DESC
        """,
        (since_ts, min_days_seen),
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_label(conn: sqlite3.Connection, mac_hash: str) -> str | None:
    row = conn.execute(
        "SELECT name FROM labels WHERE mac_hash = ?", (mac_hash,)
    ).fetchone()
    return row[0] if row else None


def set_label(conn: sqlite3.Connection, mac_hash: str, name: str) -> None:
    conn.execute(
        """
        INSERT INTO labels (mac_hash, name, set_at) VALUES (?, ?, ?)
        ON CONFLICT(mac_hash) DO UPDATE SET name = excluded.name, set_at = excluded.set_at
        """,
        (mac_hash, name, int(time.time())),
    )
    conn.commit()


def get_stats(conn: sqlite3.Connection) -> dict:  # type: ignore[type-arg]
    page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]

    obs_row = conn.execute(
        "SELECT MIN(ts), COUNT(*) FROM observations"
    ).fetchone()
    oldest_ts, total_obs = obs_row

    hour_ago = int(time.time()) - 3600
    unique_last_hour = conn.execute(
        "SELECT COUNT(DISTINCT mac_hash) FROM observations WHERE ts >= ?",
        (hour_ago,),
    ).fetchone()[0]

    return {
        "database_size_bytes": page_count * page_size,
        "oldest_ts": oldest_ts,
        "total_observations": total_obs,
        "unique_devices_last_hour": unique_last_hour,
    }