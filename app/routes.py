import base64
import hmac
import json
import time
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from .db import get_db

bp = Blueprint("main", __name__)


def _parse_ts(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _check_basic_auth(expected_user: str, expected_pw: str | None) -> bool:
    if not expected_pw:
        return False

    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False

    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
        user, _, password = decoded.partition(":")
    except (ValueError, UnicodeDecodeError):
        return False

    return hmac.compare_digest(user, expected_user) and hmac.compare_digest(
        password, expected_pw
    )


def _unauthorized(realm: str) -> Response:
    resp = jsonify(error="unauthorized")
    resp.status_code = 401
    resp.headers["WWW-Authenticate"] = f'Basic realm="{realm}"'
    return resp


def _require_viewer() -> Response | None:
    cfg = current_app.config
    if _check_basic_auth(cfg["VIEWER_USERNAME"], cfg.get("VIEWER_PASSWORD")):
        return None
    return _unauthorized("timeline")


def _require_api_token() -> Response | None:
    expected = current_app.config.get("API_TOKEN")
    if not expected:
        resp = jsonify(error="unauthorized")
        resp.status_code = 401
        return resp

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        resp = jsonify(error="unauthorized")
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = 'Bearer realm="timeline-api"'
        return resp

    if not hmac.compare_digest(header[7:], expected):
        resp = jsonify(error="unauthorized")
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = 'Bearer realm="timeline-api"'
        return resp

    return None


def _store_location(payload: dict) -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO locations
            (tst, tid, lat, lon, acc, alt, vel, cog, batt, bs, conn, trigger,
             raw, received_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("tst"),
            payload.get("tid"),
            payload.get("lat"),
            payload.get("lon"),
            payload.get("acc"),
            payload.get("alt"),
            payload.get("vel"),
            payload.get("cog"),
            payload.get("batt"),
            payload.get("bs"),
            payload.get("conn"),
            payload.get("t"),
            json.dumps(payload, separators=(",", ":")),
            int(time.time()),
        ),
    )
    db.commit()


@bp.post("/pub")
def pub() -> Response:
    cfg = current_app.config
    if not _check_basic_auth(cfg["OWNTRACKS_USERNAME"], cfg.get("OWNTRACKS_PASSWORD")):
        return _unauthorized("owntracks")

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="invalid payload"), 400

    if payload.get("_type") == "location":
        if payload.get("lat") is None or payload.get("lon") is None:
            return jsonify(error="missing lat/lon"), 400
        _store_location(payload)

    return jsonify([])


@bp.get("/api/points")
def points() -> Response:
    if (deny := _require_viewer()) is not None:
        return deny

    frm = _parse_ts(request.args.get("from"))
    to = _parse_ts(request.args.get("to"))

    sql = "SELECT tst, tid, lat, lon, acc, alt, vel, cog, batt FROM locations"
    clauses: list[str] = []
    params: list[int] = []
    if frm is not None:
        clauses.append("tst >= ?")
        params.append(frm)
    if to is not None:
        clauses.append("tst <= ?")
        params.append(to)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY tst ASC"

    rows = get_db().execute(sql, params).fetchall()

    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["lon"], row["lat"]],
            },
            "properties": {
                "tst": row["tst"],
                "tid": row["tid"],
                "acc": row["acc"],
                "alt": row["alt"],
                "vel": row["vel"],
                "cog": row["cog"],
                "batt": row["batt"],
            },
        }
        for row in rows
    ]

    return jsonify({"type": "FeatureCollection", "features": features})


@bp.get("/api/latest")
def latest() -> Response:
    if (deny := _require_viewer()) is not None:
        return deny

    rows = get_db().execute(
        """
        SELECT tst, tid, lat, lon, acc, alt, vel, cog, batt
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY tid ORDER BY tst DESC, rowid DESC
            ) AS rn
            FROM locations
            WHERE tid IS NOT NULL
        )
        WHERE rn = 1
        """
    ).fetchall()

    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["lon"], row["lat"]],
            },
            "properties": {
                "tst": row["tst"],
                "tid": row["tid"],
                "acc": row["acc"],
                "alt": row["alt"],
                "vel": row["vel"],
                "cog": row["cog"],
                "batt": row["batt"],
            },
        }
        for row in rows
    ]

    return jsonify({"type": "FeatureCollection", "features": features})


@bp.get("/api/v1/locations")
def api_locations() -> Response:
    if (deny := _require_api_token()) is not None:
        return deny

    tid = request.args.get("tid")
    if not tid:
        return jsonify(error="missing tid"), 400

    frm = _parse_ts(request.args.get("from"))
    to = _parse_ts(request.args.get("to"))

    cfg = current_app.config
    max_limit = cfg["API_MAX_LIMIT"]
    default_limit = cfg["API_DEFAULT_LIMIT"]
    limit_arg = request.args.get("limit")
    if limit_arg is None:
        limit = default_limit
    else:
        try:
            limit = int(limit_arg)
        except ValueError:
            return jsonify(error="invalid limit"), 400
        if limit < 1:
            return jsonify(error="invalid limit"), 400
        limit = min(limit, max_limit)

    sql = "SELECT tst, lat, lon FROM locations WHERE tid = ?"
    params: list = [tid]
    if frm is not None:
        sql += " AND tst >= ?"
        params.append(frm)
    if to is not None:
        sql += " AND tst <= ?"
        params.append(to)
    sql += " ORDER BY tst ASC LIMIT ?"
    params.append(limit)

    rows = get_db().execute(sql, params).fetchall()

    return jsonify(
        [
            {"tst": row["tst"], "lat": row["lat"], "lon": row["lon"]}
            for row in rows
        ]
    )


@bp.get("/")
def map_page() -> Response:
    if (deny := _require_viewer()) is not None:
        return deny
    return render_template("map.html")


@bp.get("/healthz")
def healthz() -> Response:
    return jsonify(ok=True)
