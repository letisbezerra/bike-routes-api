from geoalchemy2.shape import to_shape
from geoalchemy2.types import WKBElement
from shapely.geometry import mapping


def to_geojson_geometry(geometry: WKBElement) -> dict:
    return mapping(to_shape(geometry))
