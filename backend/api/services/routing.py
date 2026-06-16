"""Routing and geocoding via Nominatim + OSRM.

External calls per request: 2 geocode + 1 route = 3 total.
"""

import logging

import requests
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

METERS_TO_MILES = 0.000621371
OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"
_GEOCODE_TIMEOUT = 10
_OSRM_TIMEOUT = 30
_MAX_GEOCODE_RETRIES = 2

_http = requests.Session()
_geocoder = Nominatim(user_agent="fuel_route_optimizer/1.0", timeout=_GEOCODE_TIMEOUT)


def geocode_location(location: str) -> tuple[float, float]:
    """Convert a location string to (lat, lon). Raises ValueError on failure."""
    query = f"{location}, USA"
    last_exc: Exception | None = None

    for attempt in range(_MAX_GEOCODE_RETRIES):
        try:
            result = _geocoder.geocode(query)
            if result is None:
                raise ValueError(f"Could not geocode location: {location}")
            return (result.latitude, result.longitude)
        except GeocoderTimedOut as exc:
            last_exc = exc
            logger.warning("Geocode timeout (attempt %d/%d) for '%s'", attempt + 1, _MAX_GEOCODE_RETRIES, location)

    raise ValueError(f"Could not geocode '{location}' after {_MAX_GEOCODE_RETRIES} attempts: {last_exc}")


def _parse_osrm_steps(steps_raw: list[dict]) -> list[dict]:
    """Normalize OSRM steps into {name, distance_miles, duration_seconds, start_location, end_location}."""
    steps = []
    for idx, step in enumerate(steps_raw):
        loc = step['maneuver']['location']
        start_lat, start_lon = loc[1], loc[0]

        if idx + 1 < len(steps_raw):
            next_loc = steps_raw[idx + 1]['maneuver']['location']
            end_lat, end_lon = next_loc[1], next_loc[0]
        else:
            end_lat, end_lon = start_lat, start_lon

        steps.append({
            'name': step.get('name', ''),
            'distance_miles': step['distance'] * METERS_TO_MILES,
            'duration_seconds': step['duration'],
            'start_location': {'lat': start_lat, 'lon': start_lon},
            'end_location': {'lat': end_lat, 'lon': end_lon},
        })
    return steps


def get_osrm_route(start_coords: tuple[float, float], end_coords: tuple[float, float]) -> dict:
    """Fetch driving route from OSRM. Exactly one external API call."""
    coords_str = f"{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}"
    url = f"{OSRM_BASE_URL}/{coords_str}"
    params = {'overview': 'full', 'geometries': 'polyline', 'steps': 'true'}

    try:
        response = _http.get(url, params=params, timeout=_OSRM_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("OSRM request failed: %s", exc)
        raise

    data = response.json()

    if data.get('code') != 'Ok' or not data.get('routes'):
        raise ValueError(f"OSRM could not find a route: {data.get('code', 'Unknown error')}")

    route = data['routes'][0]

    return {
        'distance_miles': round(route['distance'] * METERS_TO_MILES, 2),
        'duration_seconds': route['duration'],
        'polyline': route['geometry'],
        'legs': [
            {
                'distance_miles': leg['distance'] * METERS_TO_MILES,
                'steps': _parse_osrm_steps(leg['steps']),
            }
            for leg in route['legs']
        ],
    }
