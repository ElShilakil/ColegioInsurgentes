from flask import Blueprint, request, jsonify
from extensions import db
from models import SchoolCycle, Trimester
from datetime import date

calendar_api_bp = Blueprint('calendar_api', __name__, url_prefix='/api')

@calendar_api_bp.route('/trimesters/active', methods=['GET'])
def get_active_trimester():
    """Retorna el trimestre marcado manualmente como activo."""
    trimester = Trimester.query.filter_by(is_active=True).first()
    
    if not trimester:
        return jsonify({
            "status": "error",
            "message": "No hay un trimestre marcado como activo."
        }), 404

    return jsonify(trimester.to_dict()), 200
