import logging

from flask import Blueprint, jsonify, render_template, request

import services.detalle_agente as detalle_service

logger = logging.getLogger(__name__)
detalle_agente_bp = Blueprint("detalle_agente", __name__)


def _filters_from_request() -> dict:
    return {
        "supervisor": request.args.get("supervisor", ""),
        "campana":    request.args.get("campana", ""),
    }


def _err(exc: Exception, code: int = 500):
    logger.error("%s", exc, exc_info=True)
    return jsonify({"error": str(exc)}), code


# ── Vistas ───────────────────────────────────────────────────────────────────

@detalle_agente_bp.route("/detalle-agente")
def detalle_agente_page():
    return render_template("detalle_agente.html")


# ── API REST ─────────────────────────────────────────────────────────────────

@detalle_agente_bp.route("/api/detalle-agente")
def detalle_agente_report():
    try:
        return jsonify(detalle_service.get_full_report(_filters_from_request()))
    except Exception as exc:
        return _err(exc)


@detalle_agente_bp.route("/api/detalle-agente/filters")
def detalle_agente_filters():
    try:
        return jsonify(detalle_service.get_filter_options())
    except Exception as exc:
        return _err(exc)
