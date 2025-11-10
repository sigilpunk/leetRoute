from flask import *
from LocationSearch import search_map, format_results
from engine import main as get_and_export_directions, Point
import json
from pathlib import Path

app = Flask(__name__)
app.debug = True
start_results = None
dest_results = None

@app.route("/", methods=["GET"])
def index():
    global start_results, dest_results

    args = request.args
    start = args.get("s")
    dest  = args.get("d")
    
    if start and dest:
        start_results = search_map(start, limit=50)
        dest_results = search_map(dest, limit=50)
        ex_sr = format_results(start_results, ansi=False)[0][0]
        ex_dr = format_results(dest_results, ansi=False)[0][0]
    else:
        ex_sr, ex_dr = None, None
    
    return render_template('index.html.jinja', start_res=ex_sr, dest_res=ex_dr)

@app.route("/getLocationByIndex", methods=["GET"])
def get_location_by_index():
    args = request.args
    index = args.get("i")
    loctype = args.get("t")
    if not index:
        return {"error": "no index given"}
    if not loctype:
        return {"error": "no location type given"}

    match loctype:
        case "start":
            results = start_results
        case "dest":
            results = dest_results
    if not results:
        return {}

    _, locations = format_results(results)
    chosen_location = locations[int(index)]

    # coordinates = ', '.join(str(n) for n in chosen_location.coords.to_tuple())
    coords = chosen_location.coords
    coords = {
        "loctype": loctype,
        "coords": {
            "lat": coords.lat,
            "lon": coords.lon
        }
    }
    return coords

@app.route("/calculate", methods=["GET"])
def calculate_page():
    args = request.args
    start = args.get("s")
    dest  = args.get("d")
    
    if start and dest:
        slon, slat = start.split(",")
        dlon, dlat = dest.split(",")
        sp = Point(slon, slat)
        dp = Point(dlon, dlat)
        results = get_and_export_directions(start=sp, dest=dp)
    else:
        results = {}
    
    return render_template('calculate.html.jinja', results=json.dumps(results))

@app.route("/exports/<path:filename>", methods=["GET"])
def download(filename: str):
    print(filename)
    # filepath = Path(filepath)
    # filename = filepath.name
    # filepath = Path(filepath).parts[:-1]
    filepath = Path(app.root_path).joinpath("exports")
    return send_from_directory(filepath, filename)

app.run()