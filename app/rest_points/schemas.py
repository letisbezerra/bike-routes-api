from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, field_validator

from app.shared.schemas import Feature, FeatureCollection, ListQuery

_ALLOWED_URL_SCHEMES = {"http", "https"}


class RestPointProperties(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_urls: list[str]

    @field_validator("image_urls")
    @classmethod
    def drop_disallowed_schemes(cls, value: list[str]) -> list[str]:
        # image_urls is extracted from raw HTML at ingestion time with no
        # scheme validation (docs/DATA_SOURCES.md #8) — this is the first
        # place it's ever returned by the API, so a javascript:/data: URL
        # must be dropped here, not surfaced.
        return [url for url in value if urlsplit(url).scheme in _ALLOWED_URL_SCHEMES]


RestPointFeature = Feature[RestPointProperties]
RestPointFeatureCollection = FeatureCollection[RestPointProperties]


class RestPointQuery(ListQuery):
    pass
