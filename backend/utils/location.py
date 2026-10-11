import math


def has_location(latitude: float | None, longitude: float | None):
    return latitude is not None and longitude is not None


def has_partial_location(latitude: float | None, longitude: float | None):
    return (latitude is None) != (longitude is None)


def calculate_distance_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
):
    earth_radius_km = 6371.0
    lat_a = math.radians(latitude_a)
    lon_a = math.radians(longitude_a)
    lat_b = math.radians(latitude_b)
    lon_b = math.radians(longitude_b)

    delta_lat = lat_b - lat_a
    delta_lon = lon_b - lon_a

    haversine_value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )

    distance = 2 * earth_radius_km * math.asin(math.sqrt(haversine_value))
    return round(distance, 2)
