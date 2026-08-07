from flask import Flask, request, jsonify
import gpxpy
import io
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "SportDataSense Backend OK"

@app.route("/process", methods=["POST"])
def process_gpx():
    if "gpxfile" not in request.files:
        return jsonify({"error": "Nessun file inviato"}), 400

    file = request.files["gpxfile"]
    gpx_data = file.read().decode("utf-8")

    gpx = gpxpy.parse(gpx_data)

    lat, lon, ele, times = [], [], [], []
    hr, cad, power, temp = [], [], [], []
    logs = []

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                lat.append(point.latitude)
                lon.append(point.longitude)
                ele.append(point.elevation)
                times.append(point.time.isoformat() if point.time else None)

                if point.extensions:
                    hr_val = point.extensions.find("gpxtpx:hr")
                    cad_val = point.extensions.find("gpxtpx:cad")
                    power_val = point.extensions.find("gpxtpx:power")
                    temp_val = point.extensions.find("gpxtpx:atemp")

                    hr.append(int(hr_val.text) if hr_val is not None else None)
                    cad.append(int(cad_val.text) if cad_val is not None else None)
                    power.append(int(power_val.text) if power_val is not None else None)
                    temp.append(float(temp_val.text) if temp_val is not None else None)
                else:
                    hr.append(None)
                    cad.append(None)
                    power.append(None)
                    temp.append(None)

    if all(v is None for v in hr):
        logs.append("⚠ Il file GPX non contiene frequenza cardiaca (HR)")
    if all(v is None for v in cad):
        logs.append("⚠ Il file GPX non contiene cadenza")
    if all(v is None for v in power):
        logs.append("⚠ Il file GPX non contiene potenza")
    if all(v is None for v in temp):
        logs.append("⚠ Il file GPX non contiene temperatura")

    return jsonify({
        "lat": lat,
        "lon": lon,
        "ele": ele,
        "times": times,
        "hr": hr,
        "cad": cad,
        "power": power,
        "temp": temp,
        "logs": logs
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
