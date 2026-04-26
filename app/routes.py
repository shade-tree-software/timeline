import base64
import hmac
import json
import time

from flask import Blueprint, Response, current_app, jsonify, request

from .db import get_db

bp = Blueprint("main", __name__)


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


@bp.get("/healthz")
def healthz() -> Response:
    return jsonify(ok=True)
