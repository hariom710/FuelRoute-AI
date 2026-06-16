import csv
from collections import defaultdict

from django.conf import settings


class FuelStation:
    __slots__ = ('name', 'address', 'city', 'state', 'price')

    def __init__(self, name: str, address: str, city: str, state: str, price: float):
        self.name = name
        self.address = address
        self.city = city
        self.state = state
        self.price = price


_stations: list[FuelStation] = []
_stations_by_state: dict[str, list[FuelStation]] = {}
_cheapest_global: FuelStation | None = None
_loaded = False


def load_fuel_data(csv_path: str | None = None) -> None:
    """Load fuel-price CSV into memory. No-op after first call."""
    global _stations, _stations_by_state, _cheapest_global, _loaded

    if _loaded:
        return

    if csv_path is None:
        csv_path = getattr(settings, 'FUEL_CSV_PATH', None)
        if csv_path is None:
            raise ValueError("FUEL_CSV_PATH not configured in Django settings")

    by_state: dict[str, list[FuelStation]] = defaultdict(list)

    with open(csv_path, 'r', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            try:
                price = float(row['Retail Price'])
            except (ValueError, KeyError):
                continue
            station = FuelStation(
                name=row.get('Truckstop Name', ''),
                address=row.get('Address', ''),
                city=row.get('City', ''),
                state=row.get('State', ''),
                price=price,
            )
            _stations.append(station)
            by_state[station.state.strip().upper()].append(station)

    _stations_by_state = dict(by_state)
    _cheapest_global = min(_stations, key=lambda s: s.price) if _stations else None
    _loaded = True


def get_stations_by_state(state: str) -> list[FuelStation]:
    return _stations_by_state.get(state.strip().upper(), [])


def get_cheapest_in_state(state: str) -> FuelStation | None:
    stations = get_stations_by_state(state)
    return min(stations, key=lambda s: s.price) if stations else None


def get_cheapest_global() -> FuelStation | None:
    return _cheapest_global
