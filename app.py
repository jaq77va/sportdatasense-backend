import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy

app = Flask(__name__)
CORS(app)

@app.route('/process', methods=['POST'])
def process_gpx():
    if 'gpxfile' not in request.files:
        return jsonify({"error": "Nessun file trovato nella richiesta"}), 400
    
    file = request.files['gpxfile']
    if file.filename == '':
        return jsonify({"error": "Nome file non valido"}), 400

    logs = []
    try:
        gpx = gpxpy.parse(file)
        
        latitudes = []
        longitudes = []
        elevations = []
        timestamps = []
        heart_rates = []
        cadences = []
        powers = []
        temperatures = []

        total_points = 0

        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    total_points += 1
                    latitudes.append(point.latitude)
                    longitudes.append(point.longitude)
                    elevations.append(point.elevation if point.elevation is not None else 0.0)
                    
                    if point.time:
                        timestamps.append(point.time.strftime('%H:%M:%S'))
                    else:
                        timestamps.append(None)
                    
                    hr = None
                    cad = None
                    power = None
                    temp = None

                    if point.extensions:
                        for ext in point.extensions:
                            for child in ext:
                                tag_lower = child.tag.lower()
                                if 'hr' in tag_lower or 'heartrate' in tag_lower:
                                    try: hr = float(child.text)
                                    except: pass
                                elif 'cad' in tag_lower:
                                    try: cad = float(child.text)
                                    except: pass
                                elif 'power' in tag_lower or 'watts' in tag_lower:
                                    try: power = float(child.text)
                                    except: pass
                                elif 'atemp' in tag_lower or 'temp' in tag_lower:
                                    try: temp = float(child.text)
                                    except: pass

                    heart_rates.append(hr)
                    cadences.append(cad)
                    powers.append(power)
                    temperatures.append(temp)

        logs.append(f"Letti {total_points} punti dalla traccia GPX.")

        return jsonify({
            "lat": latitudes,
            "lon": longitudes,
            "ele": elevations,
            "time": timestamps,
            "hr": heart_rates,
            "cad": cadences,
            "power": powers,
            "temp": temperatures,
            "logs": logs
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
