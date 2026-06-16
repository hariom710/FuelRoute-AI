# Fuel Route Optimizer API

A Django REST API that calculates driving routes between US locations and finds optimal fuel stops to minimize costs.

## Assumptions

- Vehicle maximum range: 500 miles per full tank
- Fuel efficiency: 10 miles per gallon
- Fuel optimization uses a heuristic strategy that prioritizes cost minimization while respecting vehicle range constraints
- All routes and locations are within the USA
- Fuel prices are loaded from the provided CSV containing 8,151 fuel stations and indexed in memory for fast lookups
- Routes that fit within a single tank require no fuel stops

## Tech Stack

- Python 3.12+
- Django 5.x
- Django REST Framework
- Requests
- geopy (Nominatim geocoding)

## Setup

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Mac/Linux
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server:**
   ```bash
   cd backend
   python manage.py runserver
   ```

4. **API is available at:** `http://127.0.0.1:8000/api/route/`

## API Usage

**Endpoint:** `POST /api/route/`

**Request:**
```json
{
  "start": "New York, NY",
  "finish": "Los Angeles, CA"
}
```

**Response:**
```json
{
  "distance_miles": 2798.19,
  "estimated_gallons": 279.82,
  "fuel_stops": [
    {
      "city": "London",
      "state": "OH",
      "fuel_price": 3.0,
      "gallons_purchased": 50.0,
      "cost": 149.95
    }
  ],
  "total_fuel_cost": 746.0,
  "route_polyline": "encoded_polyline_string"
}
```

### Error Responses

**400 Bad Request** — invalid input or unresolvable location:
```json
{
  "error": "Could not geocode start location: Could not geocode location: xyz"
}
```

```json
{
  "start": ["This field is required."],
  "finish": ["This field is required."]
}
```

**503 Service Unavailable** — routing service down:
```json
{
  "error": "Routing service error: Connection refused"
}
```

## Algorithm

The fuel optimization uses a heuristic strategy:

1. Divide the total route into `floor(distance / 500)` equal segments
2. For each segment boundary, interpolate the geographic coordinates along the route
3. Determine which US state that point falls in using a bounding-box lookup table
4. Select the lowest-cost fuel station in that state from the in-memory indexed CSV data
5. If no station exists in that state, fall back to the globally cheapest station
6. Calculate gallons needed (capped at 50-gallon tank) and multiply by the station's price

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| CSV loading | O(n) once | 8,151 stations loaded at startup, never re-read |
| State lookup | O(1) | 50-entry bounding box table scan |
| Station lookup by state | O(1) dict + O(s) min | s = stations in that state (typically < 200) |
| Global cheapest station | O(1) | Cached at load time |
| Route interpolation | O(S * k) | S = fuel stops (≤ 6), k = route steps |
| **External API calls** | **3 total** | 2 geocode + 1 OSRM route |
| **HTTP connections** | **Pooled** | `requests.Session` reuses TCP sockets |

## External Services

| Service | Purpose | API Key Required |
|---------|---------|-----------------|
| [Nominatim](https://nominatim.org/) (OpenStreetMap) | Geocoding location strings to coordinates | No |
| [OSRM](http://project-osrm.org/) | Driving route calculation | No |

Both are free public services. The API makes exactly 1 OSRM call per request.

## Architecture

```
backend/
  api/
    services/
      routing.py        # Geocoding + OSRM route fetching
      fuel_optimizer.py # Stop optimization algorithm
      fuel_loader.py    # CSV loading + in-memory indexing
    views.py            # API endpoint handler
    serializers.py      # Request/response validation
    urls.py             # URL routing
  fuel_route/
    settings.py         # Django settings
    urls.py             # Project URLs
```

## Postman Request

1. Set method to `POST`
2. Set URL to `http://127.0.0.1:8000/api/route/`
3. Go to Body > raw > JSON
4. Enter the request JSON
5. Click Send

## Loom Demo Script (Max 5 min)

1. **0:00-0:30** — Project overview and structure
2. **0:30-1:00** — Show the API endpoint in Postman
3. **1:00-2:00** — Demo NYC to LA request
4. **2:00-3:00** — Explain fuel optimization algorithm and state lookup
5. **3:00-4:00** — Walk through the code
6. **4:00-5:00** — Show results and discuss performance characteristics
