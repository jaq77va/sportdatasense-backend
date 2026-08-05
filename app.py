from flask import Flask, request, jsonify
import gpxpy
import io

app = Flask(__name__)

@app.route("/process", methods=["POST"])
def process():
    file = request.files.get("gpxfile")
    if not file:
        return jsonify({"error": "Nessun file GPX caricato"}), 400

    gpx_data = file.read().decode("utf-8")
    gpx = gpxpy.parse(io.StringIO(gpx_data))

    logs = []
    times, lats, lons, eles = [], [], [], []
    hrs, cadences, powers, temps = [], [], [], []

    has_hr = has_cad = has_power = has_temp = False

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.time is None:
                    continue

                times.append(point.time.isoformat())
                lats.append(point.latitude)
                lons.append(point.longitude)
                eles.append(point.elevation)

                hr = cad = power = temp = None

                if point.extensions:
                    for ext in point.extensions:
                        for child in ext:
                            tag = child.tag.lower()
                            val = child.text

                            if "hr" in tag:
                                try:
                                    hr = int(val)
                                    has_hr = True
                                except:
                                    pass

                            if "cad" in tag:
                                try:
                                    cad = int(val)
                                    has_cad = True
                                except:
                                    pass

                            if "power" in tag:
                                try:
                                    power = int(val)
                                    has_power = True
                                except:
                                    pass

                            if "temp" in tag or "atemp" in tag:
                                try:
                                    temp = float(val)
                                    has_temp = True
                                except:
                                    pass

                hrs.append(hr)
                cadences.append(cad)
                powers.append(power)
                temps.append(temp)

    if not times:
        return jsonify({"error": "Nessun punto valido nel GPX"}), 400

    if not has_hr:
        logs.append("⚠ Il file GPX non contiene frequenza cardiaca (HR).")
    if not has_cad:
        logs.append("⚠ Il file GPX non contiene cadenza.")
    if not has_power:
        logs.append("⚠ Il file GPX non contiene potenza.")
    if not has_temp:
        logs.append("⚠ Il file GPX non contiene temperatura.")

    return jsonify({
        "logs": logs,
        "times": times,
        "lat": lats,
        "lon": lons,
        "ele": eles,
        "hr": hrs,
        "cad": cadences,
        "power": powers,
        "temp": temps
    })


@app.route("/", methods=["GET"])
def home():
    return "SportDataSense Backend OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
