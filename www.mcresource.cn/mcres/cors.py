# mcres/cors.py
from flask import request
from .config import CORS_ALLOWED_ORIGINS


def setup_cors(app):
    @app.before_request
    def _handle_preflight():
        if request.method == 'OPTIONS':
            return ('', 204)
        return None

    @app.after_request
    def _apply_cors_headers(response):
        origin = request.headers.get('Origin')
        if origin and origin in CORS_ALLOWED_ORIGINS:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Methods'] = (
                'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            )
            response.headers['Access-Control-Allow-Headers'] = (
                'Content-Type, X-API-Key, X-Requested-With, Authorization, Accept'
            )
            response.headers['Access-Control-Max-Age'] = '86400'
            existing_vary = response.headers.get('Vary')
            response.headers['Vary'] = (
                f'{existing_vary}, Origin' if existing_vary else 'Origin'
            )
        return response