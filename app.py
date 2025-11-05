from flask import *
from LocationSearch import search_map, format_results

app = Flask(__name__)
app.debug = True
start_results = None
dest_results = None

@app.route("/")
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

@app.route("/getLocationByIndex")
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

    question_dicts, locations = format_results(results)
    chosen_location = locations[int(index)]

    # coordinates = ', '.join(str(n) for n in chosen_location.coords.to_tuple())
    coords = chosen_location.coords
    coords = {
        "lat": coords.lat,
        "lon": coords.lon
    }
    return coords

app.run()