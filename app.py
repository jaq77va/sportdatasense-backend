from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import gpxpy.gpx

app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def home():
    return "SportDataSense Backend OK"

@app.route("/process", methods=["POST"])
def process_gpx():
    if "gpxfile" not in request.files:
        return jsonify({"error": "Nessun file caricato"}), 400
    
    file = request.files["gpxfile"]
    
    try:
        gpx = gpxpy.parse(file)
    except Exception as e:
        return jsonify({"error": f"Errore nel parsing del GPX: {str(e)}"}), 400

    elevations = []
    lats = []
    lons = []
    hrs = []
    cads = []
    powers = []
    temps = []
    logs = []

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                # Coordinate e Altitudine
                lats.append(point.latitude)
                lons.append(point.longitude)
                elevations.append(point.elevation if point.elevation is not None else 0.0)

                # Estrazione Potenza (può essere un attributo diretto o in extension)
                pw = getattr(point, 'power', None)
                if pw is None:
                    # Fallivo ricerca nei tag extension generici se strutturati diversamente
                    pw = 0
                powers.append(float(pw))

                # Estrazione Estensioni Garmin (HR, Cadenza, Temperatura)
                hr_val = 0
                cad_val = 0
                temp_val = 0

                if point.extensions:
                    for ext in point.extensions:
                        # Gestione tag Garmin TrackPointExtension
                        for child in ext:
                            tag_name = child.tag.split('}')[-1] # Rimuove namespace XML
                            if tag_name == 'hr':
                                hr_val = float(child.text)
                            elif tag_name == 'cad':
                                cad_val = float(child.text)
                            elif tag_name == 'atemp':
                                temp_val = float(child.text)

                hrs.append(hr_val)
                cads.append(cad_val)
                temps.append(temp_val)

    logs.append(f"Punti totali estratti: {len(elevations)}")

    return jsonify({
        "ele": elevations,
        "lat": lats,
        "lon": lons,
        "hr": hrs,
        "cad": cads,
        "power": powers,
        "temp": temps,
        "logs": logs
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
