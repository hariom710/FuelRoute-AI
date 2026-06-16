"""Fuel-stop optimization along a computed driving route.

Divides the total distance into segments of at most MAX_RANGE_MILES,
picks the cheapest station in each segment's state, and computes cost.
"""

import logging
from typing import Any

from . import fuel_loader

logger = logging.getLogger(__name__)

# Vehicle assumptions (from assignment spec)
MAX_RANGE_MILES = 500.0
FUEL_EFFICIENCY_MPG = 10.0
MAX_GALLONS_PER_TANK = MAX_RANGE_MILES / FUEL_EFFICIENCY_MPG

# US state bounding boxes: {state: (min_lat, max_lat, min_lon, max_lon)}
# Enables O(1) reverse-geocode-to-state lookup without external APIs.
STATE_BOUNDARIES: dict[str, tuple[float, float, float, float]] = {
    'AL': (30.2, 35.0, -88.5, -84.9),
    'AK': (51.2, 71.4, -170.0, -130.0),
    'AZ': (31.3, 37.0, -114.8, -109.0),
    'AR': (33.0, 36.5, -94.6, -89.6),
    'CA': (32.5, 42.0, -124.4, -114.1),
    'CO': (37.0, 41.0, -109.1, -102.0),
    'CT': (40.9, 42.1, -73.7, -71.8),
    'DE': (38.4, 39.8, -75.8, -74.9),
    'FL': (24.4, 31.0, -87.6, -80.0),
    'GA': (30.3, 35.0, -85.6, -80.8),
    'HI': (18.9, 28.4, -160.2, -154.8),
    'ID': (42.0, 49.0, -117.2, -111.0),
    'IL': (36.9, 42.5, -91.5, -87.0),
    'IN': (37.8, 41.8, -88.1, -84.8),
    'IA': (40.4, 43.5, -96.6, -90.1),
    'KS': (37.0, 40.0, -102.0, -94.6),
    'KY': (36.5, 39.1, -89.5, -82.0),
    'LA': (28.9, 33.0, -94.0, -88.8),
    'ME': (43.1, 47.5, -71.1, -66.9),
    'MD': (37.9, 39.7, -79.5, -74.9),
    'MA': (41.2, 42.9, -73.5, -69.9),
    'MI': (41.7, 48.3, -90.4, -82.1),
    'MN': (43.5, 49.4, -97.2, -89.5),
    'MS': (30.2, 35.0, -91.6, -88.1),
    'MO': (36.0, 40.6, -95.8, -89.1),
    'MT': (44.3, 49.0, -116.1, -104.0),
    'NE': (40.0, 43.0, -104.1, -95.3),
    'NV': (35.0, 42.0, -120.0, -114.0),
    'NH': (42.7, 45.3, -72.6, -71.0),
    'NJ': (38.9, 41.4, -75.6, -73.9),
    'NM': (31.3, 37.0, -109.0, -103.0),
    'NY': (40.5, 45.0, -79.8, -71.9),
    'NC': (33.8, 36.6, -84.3, -75.5),
    'ND': (45.9, 49.0, -104.1, -96.6),
    'OH': (38.4, 42.0, -84.8, -80.5),
    'OK': (33.6, 37.0, -103.0, -94.4),
    'OR': (42.0, 46.3, -124.6, -116.5),
    'PA': (39.7, 42.3, -80.5, -74.7),
    'RI': (41.1, 42.0, -71.9, -71.1),
    'SC': (32.0, 35.2, -83.4, -78.5),
    'SD': (42.5, 49.0, -104.1, -96.4),
    'TN': (34.9, 36.7, -90.3, -81.6),
    'TX': (25.8, 36.5, -106.6, -93.5),
    'UT': (37.0, 42.0, -114.1, -109.0),
    'VT': (42.7, 45.0, -73.4, -71.5),
    'VA': (36.5, 39.5, -83.7, -75.2),
    'WA': (45.5, 49.0, -124.8, -116.9),
    'WV': (37.2, 40.6, -82.6, -77.7),
    'WI': (42.5, 47.1, -92.9, -86.8),
    'WY': (41.0, 45.0, -111.1, -104.1),
}


def _lat_lon_to_state(lat: float, lon: float) -> str | None:
    """Determine which US state contains (lat, lon) via bounding boxes."""
    best_state: str | None = None
    best_dist = float('inf')

    for state, (min_lat, max_lat, min_lon, max_lon) in STATE_BOUNDARIES.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            dist = abs(lat - (min_lat + max_lat) * 0.5) + abs(lon - (min_lon + max_lon) * 0.5)
            if dist < best_dist:
                best_dist = dist
                best_state = state

    return best_state


def _get_point_at_distance(legs: list[dict], target_distance: float) -> tuple[float, float]:
    """Interpolate (lat, lon) at *target_distance* miles along the route."""
    remaining = target_distance

    for leg in legs:
        for step in leg.get('steps', []):
            step_dist = step.get('distance_miles', 0.0)
            if remaining <= step_dist and step_dist > 0.0:
                frac = remaining / step_dist
                s, e = step['start_location'], step['end_location']
                return (
                    s['lat'] + frac * (e['lat'] - s['lat']),
                    s['lon'] + frac * (e['lon'] - s['lon']),
                )
            remaining -= step_dist

    # Fallback: end of route.
    try:
        last = legs[-1]['steps'][-1]['end_location']
        return (last['lat'], last['lon'])
    except (IndexError, KeyError):
        raise ValueError("Route contains no steps")


def optimize_fuel_stops(
    total_distance_miles: float,
    legs: list[dict[str, Any]],
    _start_location: str = "",
    _end_location: str = "",
) -> list[dict[str, Any]]:
    """Compute optimal fuel stops along the route.

    Divides into floor(distance / MAX_RANGE_MILES) equal segments,
    picks the cheapest station in each segment's state.
    """
    fuel_loader.load_fuel_data()

    num_stops = int(total_distance_miles / MAX_RANGE_MILES)
    if num_stops == 0:
        return []

    segment_length = total_distance_miles / (num_stops + 1)
    stops: list[dict[str, Any]] = []
    remaining = total_distance_miles

    for i in range(num_stops):
        target = segment_length * (i + 1)
        lat, lon = _get_point_at_distance(legs, target)
        state = _lat_lon_to_state(lat, lon)

        station = fuel_loader.get_cheapest_in_state(state) if state else None
        if station is None:
            station = fuel_loader.get_cheapest_global()
        if station is None:
            logger.warning("No fuel station found for stop %d at (%.2f, %.2f)", i + 1, lat, lon)
            continue

        gallons = min(MAX_GALLONS_PER_TANK, remaining / FUEL_EFFICIENCY_MPG)
        stops.append({
            'city': station.city,
            'state': station.state,
            'fuel_price': round(station.price, 2),
            'gallons_purchased': round(gallons, 2),
            'cost': round(gallons * station.price, 2),
        })
        remaining -= MAX_RANGE_MILES

    return stops


def calculate_fuel_cost(distance_miles: float) -> dict[str, Any]:
    """Compute raw fuel metrics for a given distance."""
    return {
        'gallons': round(distance_miles / FUEL_EFFICIENCY_MPG, 2),
        'efficiency_mpg': FUEL_EFFICIENCY_MPG,
        'distance_miles': round(distance_miles, 2),
    }
