from __future__ import annotations

import urllib.parse

from .common import get_json


WEATHER_CODES = {0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴", 45: "雾", 48: "雾凇", 51: "小毛毛雨", 61: "小雨", 63: "中雨", 65: "大雨", 71: "小雪", 80: "阵雨", 95: "雷暴"}


def get_weather(city: str) -> dict:
    query = urllib.parse.urlencode({"name": city, "count": 1, "language": "zh", "format": "json"})
    try:
        geo = get_json(f"https://geocoding-api.open-meteo.com/v1/search?{query}", timeout=8)
    except RuntimeError as primary_error:
        try:
            fallback = get_json(f"https://wttr.in/{urllib.parse.quote(city)}?format=j1", timeout=8)
            current = (fallback.get("current_condition") or [{}])[0]
            area = (fallback.get("nearest_area") or [{}])[0]
            return {
                "ok": True,
                "source": "wttr.in",
                "location": {"name": ((area.get("areaName") or [{}])[0]).get("value", city)},
                "current": {
                    "temperature_2m": current.get("temp_C"),
                    "apparent_temperature": current.get("FeelsLikeC"),
                    "precipitation": current.get("precipMM"),
                    "wind_speed_10m": current.get("windspeedKmph"),
                    "description": ((current.get("weatherDesc") or [{}])[0]).get("value", "未知天气"),
                },
            }
        except RuntimeError as fallback_error:
            raise RuntimeError(f"weather providers unavailable: {primary_error}; fallback: {fallback_error}") from fallback_error
    results = geo.get("results") or []
    if not results:
        return {"ok": False, "error": f"city not found: {city}"}
    place = results[0]
    query = urllib.parse.urlencode({"latitude": place["latitude"], "longitude": place["longitude"], "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m", "timezone": "auto"})
    data = get_json(f"https://api.open-meteo.com/v1/forecast?{query}", timeout=8)
    current = data.get("current", {})
    current["description"] = WEATHER_CODES.get(current.get("weather_code"), "未知天气")
    return {"ok": True, "source": "open-meteo", "location": {"name": place.get("name"), "country": place.get("country"), "timezone": data.get("timezone")}, "current": current, "units": data.get("current_units", {})}
