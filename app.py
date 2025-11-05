from flask import *
from LocationSearch import search_map, format_results

app = Flask(__name__)
app.debug = True

@app.route("/")
def index():
    args = request.args
    start = args.get("s")
    dest  = args.get("d")
    
    if start and dest:
        start_results = format_results(search_map(start, limit=50), ansi=False)[0][0]
        dest_results = format_results(search_map(dest, limit=50), ansi=False)[0][0]
    else:
        start_results = None
        dest_results = None
    
    return render_template('index.html', start_res=start_results, dest_res=dest_results)

app.run()