from pydantic import BaseModel


class PlaceSuggestion(BaseModel):
    place_id: str
    description: str


class PlacesAutocompleteResponse(BaseModel):
    suggestions: list[PlaceSuggestion]


class PlaceDetailsResponse(BaseModel):
    place_id: str
    formatted_address: str
    latitude: float
    longitude: float
