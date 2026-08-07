from flask import Flask, request, jsonify
import gpxpy
import io
from flask_cors import CORS

app = Flask(__name__)
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

                hr_val, cad_val, power_val, temp_val = None, None, None, None

                if point.extensions:
                    # Gestiamo point.extensions sia che sia una lista/iterabile sia che sia un elemento singolo
                    extensions_list = point.extensions if isinstance(point.extensions, (list, tuple)) else [point.extensions]
                    
                    for ext in extensions_list:
                        # Se l'estensione contiene dei figli (es. tag Garmin)
                        children = list(ext) if hasattr(ext, '__iter__') else []
                        for child in children:
                            tag_lower = child.tag.lower()
                            if 'hr' in tag_lower:
                                hr_val = child.text
                            elif 'cad' in tag_lower:
                                cad_val = child.text
                            elif 'power' in tag_lower or 'watts' in tag_lower:
                                power_val = child.text
                            elif 'atemp' in tag_lower or 'temp' in tag_lower:
                                temp_val = child.text

                hr.append(int(hr_val) if hr_val is not None else None)
                cad.append(int(cad_val) if cad_val is not None else None)
                power.append(int(power_val) if power_val is not None else None)
                temp.append(float(temp_val) if temp_val is not None else None)

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
