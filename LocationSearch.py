from typing import *
import requests
import inquirer
import json
from dataclasses import dataclass, asdict
from enum import Enum
import math
from strip_ansi import strip_ansi


with open("config.json", "r") as f:
    CONFIG = json.load(f)
__VERSION_ROOT = CONFIG.get("version")
__DEBUGGING_ROOT = CONFIG.get("debugging")

LEETROUTE_VERSION = __VERSION_ROOT.get("base")
ENGINE_VERSION = __VERSION_ROOT.get("engine")
WEBAPP_VERSION = __VERSION_ROOT.get("webapp")

ENGINE_DEBUGGING = __DEBUGGING_ROOT.get("engine")
LOCSEARCH_DEBUGGING = __DEBUGGING_ROOT.get("LocationSearch")
WEBAPP_DEBUGGING = __DEBUGGING_ROOT.get("webapp")


class DistanceUnit(Enum):
    MILES = "miles"
    KILOMETERS = "kilometers"

@dataclass
class Point:
    lat: float | int=0
    lon: float | int=0
    
    def rad(self) -> Self:
        return Point(math.radians(self.lat), math.radians(self.lon))

    def distance(self, other: Self, unit: DistanceUnit) -> float:
        R = 3959 if unit == "miles" else 6357

        dlat = self.rad().lat - other.rad().lat
        dlon = self.rad().lon - other.rad().lon
        h = 2 * math.asin( math.sqrt( (math.sin(dlat / 2)**2) + math.cos(self.rad().lat) * math.cos(other.rad().lat) * (math.sin(dlon / 2)**2) ) )
        d = h * R

        return d
    
    def bearing(self, other: Self) -> float:
        p1 = self.rad()
        p2 = other.rad()
        dlon = p2.lon - p1.lon
        x = math.sin(dlon) * math.cos(p2.lat)
        y = math.cos(p1.lat) * math.sin(p2.lat) - math.sin(p1.lat) * math.cos(p2.lat) * math.cos(dlon)
        bearing = math.atan2(x, y)
        return math.degrees(bearing)
    
    @classmethod
    def from_tuple(cls, data: tuple[float,float]) -> Self:
        return cls(*data)
    
    def to_tuple(self, swap: bool=False) -> tuple[float,float]:
        return (self.lon, self.lat) if swap else (self.lat, self.lon)

    def __repr__(self) -> str:
        return f"Point({self.lat}, {self.lon})"



@dataclass
class Location:
    coords: Point
    displayname: str=''
    name: str=''

    def __repr__(self) -> str:
        return self.displayname

    def __str__(self) -> str:
        return self.name
    

def debug(content: str) -> None:
    """Send a debug message to the console

    Args:
        content (str): content to include
    """
    if LOCSEARCH_DEBUGGING:
        print(f"\x1b[35m[DEBUG: {__file__}] {content}\x1b[0m")


def search_map(query: str, priority_pos: Optional[tuple[float, float]] = None, limit: int = 15) -> dict[str, Any]:
    """Perform a search using Komoot Photon

    Args:
        query (str): Query to search
        priority_pos (Optional[tuple[float, float]], optional): Set a location to prioritize results that are near. Normal sorting is applied if left blank or set to `False` Defaults to None.
        limit (int, optional): How many search results to return (max 50). Defaults to 15.

    Returns:
        dict[str, Any]
    """
    
    url = "https://photon.komoot.io/api/"
    params = {
        "q": query,
        "limit": limit
    }

    if priority_pos:
        lat, lon = priority_pos
        params["lat"] = lat
        params["lon"] = lon

    headers = {
        "User-Agent": f"leetRoute/{LEETROUTE_VERSION}"
    }

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    res = response.json()
    res["query"] = query
    return res


def debug(content: str) -> None:
    """Send a debug message to the console

    Args:
        content (str): content to include
    """
    if ENGINE_DEBUGGING:
        print(f"\x1b[35m[DEBUG: {__file__}] {content}\x1b[0m")


def reverse_geocode(coord: Point, limit: int=1) -> dict[str, Any]:
    """Perform a reverse-geocode search using Komoot Photon

    Args:
        coord (Point): Coordinates to search
        limit (int): Max number of results to return

    Returns:
        dict[str, Any]
    """

    url = "https://photon.komoot.io/reverse"
    params = {
        "lon": coord.lat,
        "lat": coord.lon,
        "limit": limit
    }

    headers = {
        "User-Agent": f"leetRoute/{LEETROUTE_VERSION}"
    }

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    res = response.json()
    return res

def format_results(results: dict[str, Any], ansi: bool=True) -> tuple[list[dict[str, Any]], list[Location]]:
    """
    Returns a tuple (question_dicts, locations_list).
    question_dicts: list of question-definition dicts (each has 'kind', 'name', etc).
    locations_list: list of Location objects so we can map the user's choice back.
    """
    locations: list[Location] = []

    default_icon = "📍"

    ftype_table = {
    # Buildings & Residences
    "house": "🏠",
    "residential": "🏘",
    "apartments": "🏢",
    "yes": "🏚",

    # Roads & Transportation
    "trunk": "🛣",
    "primary": "🛣",
    "secondary": "🛤",
    "tertiary": "🛤",
    "footway": "🚶",
    "cycleway": "🚲",
    "bus_stop": "🚌",
    "parking": "🅿️",

    # Education
    "school": "🏫",
    "university": "🏫",
    "college": "🏫",

    # Government & Civic
    "townhall": "🏛",
    "courthouse": "⚖️",
    "police": "🚔",
    "fire_station": "🚒",

    # Emergency / Medical
    "hospital": "🏥",
    "clinic": "🏥",
    "pharmacy": "💊",

    # Retail / Restaurants
    "retail": "🛍",
    "supermarket": "🛒",
    "mall": "🏬",
    "restaurant": "🍽",
    "cafe": "☕",
    "fast_food": "🍔",
    "bakery": "🥐",

    # Tourism / Culture
    "museum": "🏛",
    "theatre": "🎭",
    "cinema": "🎦",
    "artwork": "🎨",
    "monument": "🗿",

    # Nature
    "forest": "🌲",
    "meadow": "🌿",
    "park": "🌳",
    "beach": "🏖",

    # Religion
    "church": "⛪",
    "mosque": "🕌",
    "synagogue": "🕍",

    # Death-Related
    "tomb": "⛬",
    "cemetery": "⚰",

    # Industrial
    "industrial": "🏭",
    "warehouse": "📦",

    # Misc
    "water": "💧",
    "lake": "💧",
    "river": "🌊",
    "bridge": "🌉",
}


    for feature in results.get("features", []) or []:
        p = feature.get("properties") or {}
        if not p:
            continue

        housenumber = p.get("housenumber")
        street = p.get("street", p.get("name"))
        city = p.get("city")
        state = p.get("state")
        countrycode = p.get("countrycode")
        ftype = p.get("osm_value")
        ftype = ftype_table.get(ftype, default_icon) + f" ({ftype.replace("_", " ").capitalize()})"

        geom = feature.get("geometry") or {}
        coords_raw = geom.get("coordinates") or (None, None)
        # geometry.coordinates from Photon is [lon, lat]; keep as-is or flip if you prefer
        coords = tuple(coords_raw)[::-1]
        coords = Point(*coords)

        parts = [housenumber, street, city, state, countrycode, ftype]

        # name: plain joined string of available parts
        name = " ".join(str(part) for part in parts if part)

        # displayname: apply ANSI styling (bold for city/state onwards, dim for housenumber/street)
        # This will be shown in terminals that support ANSI; if not supported it will show raw escape codes.
        display_parts: list[str] = []
        for i, part in enumerate(parts):
            if not part:
                continue
            # use dim for first two parts, bold for others
            prefix = "" if i <= 1 else "\x1b[2m"
            suffix = "\x1b[0m"
            display_parts.append(f"{prefix}{part}{suffix}")
        displayname = " ".join(display_parts)

        loc = Location(coords=coords, displayname=displayname, name=name)
        locations.append(loc)

    # Build choices as (label, index) pairs so the prompt returns the index
    choices = [(loc.displayname if ansi else loc.name, idx) for idx, loc in enumerate(locations)]

    question_dicts = [
        {
            "kind": "list",  # NOTE: this library expects 'kind' not 'type'
            "name": "destination",
            "message": f"Showing {len(results.get('features'))} results for \"{results.get('query')}\"",
            "choices": choices
        }
    ]

    return question_dicts, locations


def prompt_results(results: dict[str, Any]) -> Any:
    question_dicts, locations = format_results(results)

    # Convert each question dict into inquirer question objects (load_from_dict expects one question dict)
    question_objs: list[Any] = []
    for qd in question_dicts:
        loaded = inquirer.load_from_dict(qd)
        # load_from_dict may return a list or a single question object depending on version; handle both.
        if isinstance(loaded, list):
            question_objs.extend(loaded)
        else:
            question_objs.append(loaded)

    # Now prompt the user
    answers = inquirer.prompt(question_objs)
    if not answers:
        print("No answer (possibly user aborted).")
        return None

    # answers['destination'] will be the index (because we used (label, index) pairs)
    idx = answers.get("destination")
    if idx is None:
        print("No destination chosen.")
        return None

    # map back to Location
    try:
        chosen_location = locations[int(idx)]
    except (IndexError, ValueError, TypeError):
        print("Invalid selection returned by inquirer:", idx)
        return None

    print("You chose:", chosen_location.displayname)   # uses __repr__ -> displayname
    print("Plain name:", chosen_location.name)
    print("Coords:", chosen_location.coords)
    return chosen_location


def prompt_search(query: str, priority_pos: Optional[tuple[float, float]] = None, limit: int = 15) -> Location | None:
    res = search_map(query=query, priority_pos=priority_pos, limit=limit)
    # with open("res.json", "w", encoding="utf-8") as f:
    #     json.dump(res, f, indent=4)
    loc = prompt_results(res)
    return loc


# if __name__ == "__main__":
#     res = search_map("490 Tanglewood Drive Middleville", limit=100)
#     with open("res.json", "w", encoding="utf-8") as f:
#         json.dump(res, f, indent=4)
#     prompt_results(res)
