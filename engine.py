# from LocationSearch import prompt_search, Location, Point
from LocationSearch import reverse_geocode
import openrouteservice
from openrouteservice.directions import directions as ors_directions
from dotenv import load_dotenv
from os import getenv
import json
import polyline
import simplekml
import dataclasses
from pathlib import Path
from typing import Self, Literal
import math
from enum import Enum
import vercel_blob as blob

### TODO:
# - [IMPORTANT!!!] Setup `exports` usage in this script and `app.py` to use vercel blobs


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


load_dotenv()
ORS_KEY = getenv("ORS_KEY")
BLOB_READ_WRITE_TOKEN = getenv("BLOB_READ_WRITE_TOKEN")
ors = openrouteservice.Client(key=ORS_KEY)

class DistanceUnit(Enum):
    MILES = "miles"
    KILOMETERS = "kilometers"

@dataclasses.dataclass
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



@dataclasses.dataclass
class Location:
    coords: Point
    displayname: str=''
    name: str=''

    def __repr__(self) -> str:
        return self.displayname

    def __str__(self) -> str:
        return self.name


@dataclasses.dataclass
class Step:
    distance: float
    duration: float
    type: int
    instruction: str
    name: str
    way_points: list[int]
    exit_number: int | None=None

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(**data)


@dataclasses.dataclass
class Segment:
    distance: float
    duration: float
    steps: list[Step]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        conv_data = {}
        for k, v in data.items():
            if k == "steps":
                steps = []
                for dstep in v:
                    steps.append(Step.from_dict(dstep))
                v = steps
            conv_data[k] = v
        return cls(**conv_data)


@dataclasses.dataclass
class Route:
    summary: dict
    segments: list[Segment]
    bbox: list[float]
    geometry: str
    polyline: list[tuple[float,float]]
    way_points: list[int]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: dict) -> Self:
        conv_data = {}
        for k, v in data.items():
            if k == "segments":
                segments = []
                for dseg in v:
                    segments.append(Segment.from_dict(dseg))
                v = segments
            conv_data[k] = v
        return cls(**conv_data)


@dataclasses.dataclass
class Directions:
    bbox: list[float]
    routes: list[Route]
    metadata: dict
    engine: dict | None=None

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        conv_data = {}
        for k, v in data.items():
            if k == "routes":
                routes = []
                for droute in v:
                    routes.append(Route.from_dict(droute))
                v = routes
            conv_data[k] = v
        return cls(**conv_data)
    


def debug(content: str) -> None:
    """Send a debug message to the console

    Args:
        content (str): content to include
    """
    if ENGINE_DEBUGGING:
        print(f"\x1b[35m[DEBUG: {__file__}] {content}\x1b[0m")


def alt_routes(share_factor: float=0.8, target_count: int=2, weight_factor: int=2) -> dict[str,float|int]:
    return {
        "share_factor": share_factor,
        "target_count": target_count,
        "weight_factor": weight_factor
    }


def get_directions(start: Location, dest: Location, debug: bool=False, units: Literal["m", "km", "mi"]="mi", alternative_routes: dict[str,float|int] | None = None) -> Directions:
    """
    Get directions from Openroute Service

    Args:
        start (Location): Starting location
        dest (Location): Destination location
        debug (bool, optional): Save response from the API to a file. Defaults to False.
        units (Literal[&quot;m&quot;, &quot;km&quot;, &quot;mi&quot;], optional): Units to get response in. Defaults to "mi".

    Returns:
        Directions
    """
    
    
    coords = (start.coords.to_tuple(), dest.coords.to_tuple())
    directions = ors_directions(
        client=ors,
        coordinates=coords,
        alternative_routes=alternative_routes,
        units=units
        )
    
    for i in range(len(directions["routes"])):
        pl_str = directions["routes"][i]["geometry"]
        pl_coords = polyline.decode(pl_str)
        directions["routes"][i]["polyline"] = pl_coords
        # pl_coords = [Point(*c) for c in pl_coords]
        # directions["routes"][i]["polyline"] = pl_coords

    if debug:
        with open("directions.json","w", encoding="utf-8") as f:
            json.dump(directions, f, indent=4)
    
    return Directions.from_dict(directions)

def analyse_curvature(route: Route) -> dict:
    coords = [Point(*c) for c in route.polyline]
    turns = []
    for i in range(1, len(coords) - 1):
        b1 = coords[i-1].bearing(coords[i])
        b2 = coords[i].bearing(coords[i+1])
        theta = abs(b2 - b1)
        if theta > 180:
            theta = 360 - theta

        turns.append(theta)
    
    return {
        "total_turns": sum(turns),
        "avg_turn": sum(turns) / len(turns) if turns else 0,
        "max_turn": max(turns) if turns else 0,
        "significant_turns": sum(1 for t in turns if t > 15)
    }


# start = Location(coords=Point(-85.4586982792198, 42.71960583782718),displayname="Home",name="Home")
# dest = Location(coords=Point(-85.66661925485876, 42.96804797355541), displayname="GRCC Parking Ramp A",name="GRCC Parking Ramp A")
# directions = get_directions(start, dest)
# curvature = analyse_curvature(directions.routes[0])

def generate_kml(start: Location, dest: Location, route: Route, output_path: Path, use_blob: bool=False) -> None:
    kml = simplekml.Kml()
    # linestring_data = [(p.lon, p.lat) for p in directions]
    line = kml.newlinestring(
        name=f"Route from {start.name} to {dest.name}", 
        description=f"Route from {start.name} to {dest.name}", 
        coords=[Point(*c).to_tuple(swap=True) for c in route.polyline],
        )
    
    line.style.linestyle.color = simplekml.Color.aqua
    line.style.linestyle.width = 5

    s_point = kml.newpoint(
        name=start.name,
        coords=[(start.coords.lon, start.coords.lat)]
    )
    s_point.style.iconstyle.icon.href = "https://maps.google.com/mapfiles/kml/paddle/red-circle.png"

    f_point = kml.newpoint(
        name=dest.name,
        coords=[(dest.coords.lon, dest.coords.lat)]
    )
    f_point.style.iconstyle.icon.href = "https://maps.google.com/mapfiles/kml/paddle/grn-blank-lv.png"

    step_style = simplekml.Style()
    step_style.iconstyle.icon.href = "https://maps.google.com/mapfiles/kml/paddle/blu-blank-lv.png" 

    for segment in route.segments:
        for step in segment.steps:
            wp = Point(*route.polyline[step.way_points[0]])
            p = kml.newpoint(
                name=step.name,
                description=step.instruction,
                coords=[(wp.lon, wp.lat)]
            )
            p.style = step_style

    
    route_name = f"route_from_{start.name}_to_{dest.name}".replace(" ", "_")
    outfile = output_path.joinpath(Path(route_name+".kml"))
    if use_blob:
        resp = blob.put(outfile, kml.kml(), verbose=True)
        kml_path = resp.json().get("url")
        return kml_path
    else:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(kml.kml())


def generate_maps_url(route: Route, max_waypoints: int=10, embed: bool=False) -> str:
    """
    Generates a Google Maps directions URL from a Route object
    Google Maps only supports <=10 waypoints in the URL, so the route is sampled at 10 equidistant points.
    """
    coords = route.polyline

    if len(coords) < 2:
        raise ValueError("Google Maps route requires more than 2 points for a route")
    
    start = Point(*coords[0])
    end = Point(*coords[-1])

    if len(coords) > max_waypoints:
        stepsize = len(coords) // (max_waypoints - 1)
        waypoints = coords[1:-1:stepsize][:(max_waypoints - 2)]
    else:
        waypoints = coords[1:-1]

    waypoints = [Point(*wp) for wp in waypoints]
    
    base_url = "https://www.google.com/maps/dir/"
    url = f"{base_url}{start.lat},{start.lon}/"
    for wp in waypoints:
        url += f"{wp.lat},{wp.lon}/"
    
    url += f"{end.lat},{end.lon}"

    return url

def export_to_gpx(route: Route, outfile: Path, route_name: str="Route", use_blob: bool=False) -> None:
    gpx = f'''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="leetRoute">
    <trk>
        <name>{route_name}</name>
        <trkseg>
    '''
    for p in [Point(*c) for c in route.polyline]:
        gpx += f'\t\t<trkpt lat="{p.lat}" lon="{p.lon}"></trkpt>\n'
    gpx += "\t\t</trkseg>\n\t</trk>\n</gpx>"

    if use_blob:
        resp = blob.put(outfile, gpx, verbose=True)
        return resp.json().get("url")
    else:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(gpx)



def export_route(
    route: Route, 
    start: Location, 
    dest: Location, 
    output_dir: Path = Path("./"),
    open_browser: bool = False,
    use_blob: bool=False
) -> dict[str, str]:
    """
    Export route in multiple formats.
    Returns dict with paths/URLs to exported files.
    """
    if not use_blob:
        output_dir.mkdir(parents=True, exist_ok=True)
    route_name = f"route_from_{start.name}_to_{dest.name}".replace(" ", "_")
    debug(f"{route_name=}")
    
    # results = {'embeds':{}}
    results = {}
    
    # 1. KML Export
    kml_path = output_dir / f"{route_name}.kml"
    kml_blob_path = generate_kml(start, dest, route, output_dir, use_blob)
    if use_blob and kml_blob_path:
        results['KML'] = kml_blob_path
    else:
        results['KML'] = f"/exports/{kml_path.name}"


    
    # 2. GPX Export
    gpx_path = output_dir / f"{route_name}.gpx"
    gpx_blob_path = export_to_gpx(route, gpx_path, f"Route from {start.name} to {dest.name}", use_blob)
    if use_blob and gpx_blob_path:
        results['GPX'] = gpx_blob_path
    else:
        results['GPX'] = f"/exports/{kml_path.name}"

    # 3. Optional: JSON export with metadata
    maps_url = generate_maps_url(route)
    json_path = output_dir / f"{route_name}_data.json"
    route_data = {
        'start': {'name': start.name, 'coords': start.coords.to_tuple()},
        'dest': {'name': dest.name, 'coords': dest.coords.to_tuple()},
        'summary': route.summary,
        'curvature': analyse_curvature(route),
        'polyline': route.polyline,
        'google_maps_url': maps_url
    }
    if use_blob:
        resp = blob.put(json_path, json.dumps(route_data), verbose=True)
        json_path = resp.json().get("url")
    else:
        with open(json_path, 'w', encoding="utf-8") as f:
            json.dump(route_data, f, indent=2)

    results['JSON'] = str(json_path)

    # 4. Google Maps URL
    results['Google Maps'] = maps_url

    # # 5. Google Maps Embed URL
    # maps_embed_url = generate_maps_url(route, embed=True)
    # results['embeds']['maps'] = maps_embed_url
    
    
    # Open in browser if requested
    if open_browser:
        import webbrowser
        webbrowser.open(maps_url)
    
    return results


def names_from_result(result: dict) -> list[str]:
    """Generates display names from an OSM result

    Args:
        result (dict): an OSM search result

    Returns:
        list[str]: list of names ordered by index in the "features" list
    """
    names = []
    for feature in result.get("features", []) or []:
        p = feature.get("properties") or {}
        if not p:
            continue

        housenumber = p.get("housenumber")
        street = p.get("street", p.get("name"))
        city = p.get("city")
        state = p.get("state")
        countrycode = p.get("countrycode")
        ftype = p.get("osm_value")
        ftype = ftype.replace("_", " ").capitalize()

        parts = [housenumber, street, city, state, countrycode, ftype]

        name = " ".join(str(part) for part in parts if part)
        names.append(name)
    return names


def main(start: Point, dest: Point, use_blob: bool=True) -> dict[str, str]:
    start_geocode = reverse_geocode(start)
    start_geocode["coords"] = dataclasses.asdict(start)
    dest_geocode = reverse_geocode(dest)
    dest_geocode["coords"] = dataclasses.asdict(dest)
    start_name = names_from_result(start_geocode)[0]
    dest_name = names_from_result(dest_geocode)[0]
    # with open("res.start.json", "w", encoding="utf-8") as f:
    #     json.dump(start_geocode, f, indent=4)
    # with open("res.dest.json", "w", encoding="utf-8") as f:
    #     json.dump(dest_geocode, f, indent=4)
    start = Location(coords=start,name=start_name)
    dest = Location(coords=dest, name=dest_name)
    directions = get_directions(start, dest)
    return export_route(
        directions.routes[0],
        start=start,
        dest=dest,
        output_dir=Path("./exports"),
        open_browser=False,
        use_blob=use_blob
    )
# generate_kml(directions.routes[0], Path("./"))
# curvature = analyse_curvature(directions.routes[0])
# maps_url = generate_maps_url(directions.routes[0])
# export_to_gpx(directions.routes[0], Path("./route.gpx"))

