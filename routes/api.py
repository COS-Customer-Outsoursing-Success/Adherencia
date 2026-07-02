import logging

from flask import Blueprint, jsonify, render_template, request

from database import check_connection
from services.attendance import (
    get_filter_options,
    get_full_dashboard,
    get_kpis,
    get_raw_data,
    get_supervisor_summary,
    get_timeline,
)

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _filters_from_request() -> dict:
    return {
        "supervisor":   request.args.get("supervisor", ""),
        "campana":      request.args.get("campana", ""),
        "estado":       request.args.get("estado", ""),
        "hora_inicio":  request.args.get("hora_inicio", ""),
        "hora_fin":     request.args.get("hora_fin", ""),
    }


def _err(exc: Exception, code: int = 500):
    logger.error("%s", exc, exc_info=True)
    return jsonify({"error": str(exc)}), code


# ── Vistas ───────────────────────────────────────────────────────────────────

@api_bp.route("/")
def index():
    return render_template("index.html")


# ── API REST ─────────────────────────────────────────────────────────────────

@api_bp.route("/api/health")
def health():
    result = check_connection()
    code = 200 if result["ok"] else 503
    return jsonify(result), code


@api_bp.route("/api/dashboard")
def dashboard():
    try:
        return jsonify(get_full_dashboard(_filters_from_request()))
    except Exception as exc:
        return _err(exc)


@api_bp.route("/api/kpis")
def kpis():
    try:
        data = get_raw_data(_filters_from_request())
        return jsonify(get_kpis(data))
    except Exception as exc:
        return _err(exc)


@api_bp.route("/api/supervisors")
def supervisors():
    try:
        data = get_raw_data(_filters_from_request())
        return jsonify(get_supervisor_summary(data))
    except Exception as exc:
        return _err(exc)


@api_bp.route("/api/attendance")
def attendance():
    try:
        return jsonify(get_raw_data(_filters_from_request()))
    except Exception as exc:
        return _err(exc)


@api_bp.route("/api/timeline")
def timeline():
    try:
        data = get_raw_data(_filters_from_request())
        return jsonify(get_timeline(data))
    except Exception as exc:
        return _err(exc)


@api_bp.route("/api/filters")
def filters():
    try:
        return jsonify(get_filter_options())
    except Exception as exc:
        return _err(exc)
