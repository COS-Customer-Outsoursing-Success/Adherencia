import logging

from flask import Blueprint, jsonify, render_template, request

import services.excesos as excesos_service

logger = logging.getLogger(__name__)
excesos_bp = Blueprint("excesos", __name__)


def _filters_from_request() -> dict:
    return {
        "supervisor":      request.args.get("supervisor", ""),
        "campana":         request.args.get("campana", ""),
        "solo_con_exceso": request.args.get("solo_con_exceso", "") == "1",
    }


def _err(exc: Exception, code: int = 500):
    logger.error("%s", exc, exc_info=True)
    return jsonify({"error": str(exc)}), code


# ── Vistas ───────────────────────────────────────────────────────────────────

@excesos_bp.route("/excesos")
def excesos_page():
    return render_template("excesos.html")


# ── API REST ─────────────────────────────────────────────────────────────────

@excesos_bp.route("/api/excesos")
def excesos_report():
    try:
        return jsonify(excesos_service.get_full_report(_filters_from_request()))
    except Exception as exc:
        return _err(exc)


@excesos_bp.route("/api/excesos/filters")
def excesos_filters():
    try:
        return jsonify(excesos_service.get_filter_options())
    except Exception as exc:
        return _err(exc)
