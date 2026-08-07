from flask import Flask, request, jsonify
import gpxpy
import io
from flask_cors import CORS

app = Flask(__name__)
# Configurazione CORS estesa per evitare errori di connessione tra frontend e backend
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/")
def home():
    return "SportDataSense Backend OK"

@app.route("/process", methods=["POST"])
def process_gpx():
    if "gpxfile" not in request.files:
        return jsonify({"error": "Nessun file inviato"}), 400

    file = request.files["gpxfile"]
    
    try:
        # Lettura del file
        gpx_data = file.read().decode("utf-8")
        gpx = gpxpy.parse(gpx_data)
    except Exception as e:
        return jsonify({"error": f"Errore durante il parsing del GPX: {str(e)}"}), 400

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
                    # Estrazione dati con ricerca multipla per evitare errori di namespace
                    hr_val = point.extensions.find("gpxtpx:hr")
                    cad_val = point.extensions.find("gpxtpx:cad")
                    # Correzione: cerchiamo prima con il namespace, poi senza
                    power_val = point.extensions.find("gpxtpx:power")
                    if power_val is None:
                        power_val = point.extensions.find("power")
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

    # Logging per debug lato server
    if all(v is None for v in power):
        logs.append("⚠ Il file GPX non contiene dati di potenza validi.")

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
    # Il porto 10000 è corretto per Render
    app.run(host="0.0.0.0", port=10000)
