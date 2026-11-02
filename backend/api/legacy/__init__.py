"""Rutas antiguas que consume el frontend. Errores con formato {"error": "..."}."""

from flask import jsonify, request


# Security (OWASP API4): a client can never request more items than this at once.
MAX_PAGE_SIZE = 100


def paginate(items):
    """
    Applies ?limit=&offset= with a hard cap of MAX_PAGE_SIZE. The total is returned
    in the X-Total-Count header so the JSON body stays a plain list. It cuts the
    response, not the query: the repository still loads the matching rows.
    """
    limit = min(max(request.args.get('limit', MAX_PAGE_SIZE, type=int), 1), MAX_PAGE_SIZE)
    offset = max(request.args.get('offset', 0, type=int), 0)
    response = jsonify(items[offset:offset + limit])
    response.headers['X-Total-Count'] = str(len(items))
    return response


def json_body():
    return request.get_json(silent=True) or {}


def missing_field(data, required, allow_falsy=False):
    """
    Devuelve la respuesta 400 del primer campo obligatorio ausente, o None.
    allow_falsy=True acepta 0/False (solo rechaza None y '').
    """
    for field in required:
        value = data.get(field)
        empty = value in (None, '') if allow_falsy else not value
        if field not in data or empty:
            return jsonify({'error': f'El campo {field} es obligatorio'}), 400
    return None
