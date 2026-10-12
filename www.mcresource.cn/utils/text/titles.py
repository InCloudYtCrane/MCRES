# utils/titles.py
import json

def parse_titles(raw_titles):
    if raw_titles is None:
        return {"list": [], "selected": -1}
    try:
        data = json.loads(raw_titles)
        if not isinstance(data, dict):
            return {"list": [], "selected": -1}
        if "list" not in data or not isinstance(data["list"], list):
            data["list"] = []
        if "selected" not in data or not isinstance(data["selected"], int):
            data["selected"] = -1
        return data
    except (json.JSONDecodeError, TypeError):
        return {"list": [], "selected": -1}

def get_selected_title(raw_titles):
    data = parse_titles(raw_titles)
    idx = data.get("selected", -1)
    if idx >= 0 and idx < len(data.get("list", [])):
        return data["list"][idx]
    return None