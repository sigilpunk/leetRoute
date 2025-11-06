# from LocationSearch import prompt_search, Location, Point
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

load_dotenv()
ORS_KEY = getenv("ORS_KEY")
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


def get_directions(start: Location, dest: Location, debug: bool=False, units: Literal["m", "km", "mi"]="mi") -> Directions:
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
        alternative_routes=None,
        units=units
        )
    
    pl_str = directions["routes"][0]["geometry"]
    pl_coords = polyline.decode(pl_str)
    directions["routes"][0]["polyline"] = pl_coords
    # pl_coords = [Point(*c) for c in pl_coords]
    # directions["routes"][0]["polyline"] = pl_coords

    if debug:
        with open("directions.json","w") as f:
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


start = Location(coords=Point(-85.4586982792198, 42.71960583782718),displayname="Home",name="Home")
dest = Location(coords=Point(-85.66661925485876, 42.96804797355541), displayname="GRCC Parking Ramp A",name="GRCC Parking Ramp A")
directions = get_directions(start, dest)
curvature = analyse_curvature(directions.routes[0])

def generate_kml(start: Location, dest: Location, route: Route, output_path: Path) -> None:
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
    
    outfile = output_path.joinpath(Path(f"Route from {start.name} to {dest.name}.kml"))
    kml.save(outfile)


def generate_maps_url(route: Route, max_waypoints: int=10) -> str:
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

def export_to_gpx(route: Route, outfile: Path, route_name: str="Route") -> None:
    gpx = f'''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="leetRoute">
    <trk>
        <name>{route_name}</name>
        <trkseg>
    '''
    for p in [Point(*c) for c in route.polyline]:
        gpx += f'\t\t<trkpt lat="{p.lat}" lon="{p.lon}"></trkpt>\n'
    gpx += "\t\t</trkseg>\n\t</trk>\n</gpx>"

    with open(outfile, "w") as f:
        f.write(gpx)


def export_route(
    route: Route, 
    start: Location, 
    dest: Location, 
    output_dir: Path = Path("./"),
    open_browser: bool = False
) -> dict[str, str]:
    """
    Export route in multiple formats.
    Returns dict with paths/URLs to exported files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    route_name = f"route_{start.name}_to_{dest.name}".replace(" ", "_")
    
    results = {}
    
    # 1. KML Export
    kml_path = output_dir / f"{route_name}.kml"
    generate_kml(start, dest, route, output_dir)
    results['kml'] = str(kml_path)
    
    # 2. GPX Export
    gpx_path = output_dir / f"{route_name}.gpx"
    export_to_gpx(route, gpx_path, f"Route from {start.name} to {dest.name}")
    results['gpx'] = str(gpx_path)
    
    # 3. Google Maps URL
    maps_url = generate_maps_url(route)
    results['google_maps_url'] = maps_url
    
    # 4. Optional: JSON export with metadata
    json_path = output_dir / f"{route_name}_data.json"
    route_data = {
        'start': {'name': start.name, 'coords': start.coords.to_tuple()},
        'dest': {'name': dest.name, 'coords': dest.coords.to_tuple()},
        'summary': route.summary,
        'curvature': analyse_curvature(route),
        'polyline': route.polyline,
        'google_maps_url': maps_url
    }
    with open(json_path, 'w') as f:
        json.dump(route_data, f, indent=2)
    results['json'] = str(json_path)
    
    # Open in browser if requested
    if open_browser:
        import webbrowser
        webbrowser.open(maps_url)
    
    return results


start = Location(coords=Point(-85.4586982792198, 42.71960583782718),displayname="Home",name="Home")
dest = Location(coords=Point(-85.66661925485876, 42.96804797355541), displayname="GRCC Parking Ramp A",name="GRCC Parking Ramp A")
directions = get_directions(start, dest)
export_data = export_route(
    directions.routes[0],
    start=start,
    dest=dest,
    output_dir=Path("./exports"),
    open_browser=True
)
# generate_kml(directions.routes[0], Path("./"))
# curvature = analyse_curvature(directions.routes[0])
# maps_url = generate_maps_url(directions.routes[0])
# export_to_gpx(directions.routes[0], Path("./route.gpx"))

