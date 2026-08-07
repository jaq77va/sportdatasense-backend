from flask import Flask, request, jsonify
import gpxpy
from flask_cors import CORS
import os
from google import genai

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Inizializza il client Gemini
# Assicurati che GEMINI_API_KEY sia impostata nelle variabili d'ambiente di Render
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@app.route("/")
def home():
    return "SportDataSense Backend OK"

@app.route("/process", methods=["POST"])
def process_gpx():
    if "gpxfile" not in request.files:
        return jsonify({"error": "Nessun file inviato"}), 400

    file = request.files["gpxfile"]
    try:
        gpx = gpxpy.parse(file.read().decode("utf-8"))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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

                h, c, p, t = None, None, None, None
                if point.extensions:
                    exts = point.extensions if isinstance(point.extensions, list) else [point.extensions]
                    for ext in exts:
                        for child in ext:
                            tag = child.tag.lower()
                            if 'hr' in tag: h = int(child.text)
                            elif 'cad' in tag: c = int(child.text)
                            elif 'power' in tag or 'watts' in tag: p = int(child.text)
                            elif 'atemp' in tag or 'temp' in tag: t = float(child.text)
                
                hr.append(h)
                cad.append(c)
                power.append(p)
                temp.append(t)

    return jsonify({
        "lat": lat, "lon": lon, "ele": ele, "times": times,
        "hr": hr, "cad": cad, "power": power, "temp": temp, "logs": logs
    })

@app.route("/chat", methods=["POST"])
def chat_gpx():
    req = request.json
    question = req.get("question", "")
    gpx_data = req.get("data", {})
    
    # Dati per il contesto
    elevations = gpx_data.get("ele", [])
    powers = gpx_data.get("power", [])
    hrs = gpx_data.get("hr", [])
    
    # Creiamo un riassunto dei dati per l'IA
    valid_ele = [e for e in elevations if e is not None]
    valid_pow = [p for p in powers if p is not None]
    valid_hr = [h for h in hrs if h is not None]

    context = f"""
    Sei l'assistente esperto di Sport Data Sense. Analizza questa sessione sportiva:
    - Punti traccia: {len(elevations)}
    - Altitudine: Max {max(valid_ele) if valid_ele else 0:.1f}m, Min {min(valid_ele) if valid_ele else 0:.1f}m
    - Potenza media: {sum(valid_pow)/len(valid_pow) if valid_pow else 0:.1f} W
    - Frequenza cardiaca media: {sum(valid_hr)/len(valid_hr) if valid_hr else 0:.1f} bpm
    
    Domanda dell'atleta: "{question}"
    
    Rispondi in modo professionale, tecnico e incoraggiante.
    """

    try:
        # Chiamata a Gemini 2.0 Flash
        response = client.models.generate_content(
        # AQ -model='gemini-2.0-flash',
        model='gemini-1.5-flash',
            contents=context,
        )
        answer = response.text
    except Exception as e:
        answer = f"Errore nell'analisi dell'assistente: {str(e)}"

    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
