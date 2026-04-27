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


def _check_auth() -> bool:
    expected_pw = current_app.config.get("OWNTRACKS_PASSWORD")
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

    expected_user = current_app.config["OWNTRACKS_USERNAME"]
    return hmac.compare_digest(user, expected_user) and hmac.compare_digest(
        password, expected_pw
    )


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
    if not _check_auth():
        resp = jsonify(error="unauthorized")
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = 'Basic realm="owntracks"'
        return resp

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


@bp.get("/")
def map_page() -> Response:
    return render_template("map.html")


@bp.get("/healthz")
def healthz() -> Response:
    return jsonify(ok=True)
