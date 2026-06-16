"""Request/response serializers for the route API."""

from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    """Input payload for POST /api/route/."""

    start = serializers.CharField(max_length=255)
    finish = serializers.CharField(max_length=255)

    def validate_start(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Must not be blank.")
        return value.strip()

    def validate_finish(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Must not be blank.")
        return value.strip()


class FuelStopSerializer(serializers.Serializer):
    city = serializers.CharField()
    state = serializers.CharField()
    fuel_price = serializers.FloatField()
    gallons_purchased = serializers.FloatField()
    cost = serializers.FloatField()


class RouteResponseSerializer(serializers.Serializer):
    distance_miles = serializers.FloatField()
    estimated_gallons = serializers.FloatField()
    fuel_stops = FuelStopSerializer(many=True)
    total_fuel_cost = serializers.FloatField()
    route_polyline = serializers.CharField()
