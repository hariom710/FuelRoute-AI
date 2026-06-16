"""API view for route calculation and fuel-stop optimization."""

import logging

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RouteRequestSerializer
from .services import fuel_optimizer, routing

logger = logging.getLogger(__name__)

_FALLBACK_FUEL_PRICE = 3.50


class RouteView(APIView):
    """POST /api/route/ — driving route with optimal fuel stops."""

    def post(self, request: Request) -> Response:
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start = serializer.validated_data['start']
        finish = serializer.validated_data['finish']

        # Geocode both locations.
        try:
            start_coords = routing.geocode_location(start)
        except ValueError as exc:
            logger.info("Geocode failed for start '%s': %s", start, exc)
            return Response(
                {'error': f'Could not geocode start location: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            end_coords = routing.geocode_location(finish)
        except ValueError as exc:
            logger.info("Geocode failed for finish '%s': %s", finish, exc)
            return Response(
                {'error': f'Could not geocode finish location: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Single OSRM route call.
        try:
            route_data = routing.get_osrm_route(start_coords, end_coords)
        except ValueError as exc:
            logger.info("Routing failed: %s", exc)
            return Response(
                {'error': f'Could not calculate route: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("Unexpected routing error")
            return Response(
                {'error': f'Routing service error: {exc}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        total_distance = route_data['distance_miles']
        estimated_gallons = fuel_optimizer.calculate_fuel_cost(total_distance)['gallons']

        try:
            fuel_stops = fuel_optimizer.optimize_fuel_stops(
                total_distance_miles=total_distance,
                legs=route_data['legs'],
            )
        except Exception:
            logger.exception("Fuel optimization failed; returning empty stops")
            fuel_stops = []

        if fuel_stops:
            total_fuel_cost = round(sum(stop['cost'] for stop in fuel_stops), 2)
        else:
            total_fuel_cost = round(estimated_gallons * _FALLBACK_FUEL_PRICE, 2)

        return Response({
            'distance_miles': round(total_distance, 2),
            'estimated_gallons': round(estimated_gallons, 2),
            'fuel_stops': fuel_stops,
            'total_fuel_cost': total_fuel_cost,
            'route_polyline': route_data['polyline'],
        }, status=status.HTTP_200_OK)
