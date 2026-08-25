from flask import Flask, request, jsonify
import gpxpy
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

                # Estrazione estensioni Garmin
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
    question = req.get("question", "").lower()
    gpx_data = req.get("data", {})
    bio_data = req.get("biomechanical_data", None)  # Riceve i dati dei marker video
    
    # Estraiamo i dati di riepilogo per dare contesto all'assistente GPX
    elevations = gpx_data.get("ele", []) if gpx_data else []
    powers = gpx_data.get("power", []) if gpx_data else []
    hrs = gpx_data.get("hr", []) if gpx_data else []
    cads = gpx_data.get("cad", []) if gpx_data else []
    
    answer = "Non ho abbastanza dati per rispondere a questa domanda."
    
    # Gestione delle domande sui dati biomeccanici/video
    if bio_data and any(k in question for k in ["marker", "video", "coordinata", "x", "y", "z", "andamento"]):
        marker_summaries = []
        for m in bio_data:
            m_id = m.get("marker")
            hx = m.get("historyX", [])
            hy = m.get("historyY", [])
            hz = m.get("historyZ", [])
            
            summary = f"Marker {m_id}: "
            if hx and hy:
                avg_x = sum(hx) / len(hx)
                avg_y = sum(hy) / len(hy)
                summary += f"Media X: {avg_x:.1f}, Media Y: {avg_y:.1f}"
                if hz:
                    avg_z = sum(hz) / len(hz)
                    summary += f", Media Z: {avg_z:.1f}"
            else:
                summary += "Nessun dato di movimento registrato."
            marker_summaries.append(summary)
        
        answer = f"Analisi biomeccanica completa (Assi X, Y, Z):\n" + "\n".join(marker_summaries)

    elif "rallentato" in question or "lento" in question or "perché" in question:
        if powers:
            min_power_idx = powers.index(min([p for p in powers if p is not None] or [0]))
            answer = f"Analizzando la traccia, hai registrato il calo di potenza/ritmo maggiore (minima potenza di {powers[min_power_idx]}W) verso il punto {min_power_idx + 1} del percorso. Potrebbe esserci stata una salita ripida o un ostacolo."
        else:
            answer = "Il file non contiene dati di potenza sufficienti per analizzare i rallentamenti."
            
    elif "potenza" in question:
        valid_p = [p for p in powers if p is not None]
        avg_p = sum(valid_p) / len(valid_p) if valid_p else 0
        max_p = max(valid_p) if valid_p else 0
        answer = f"La tua potenza media è di {avg_p:.1f}W, con un picco massimo di {max_p}W."
        
    elif "frequenza" in question or "cuore" in question or "hr" in question:
        valid_hr = [h for h in hrs if h is not None]
        avg_hr = sum(valid_hr) / len(valid_hr) if valid_hr else 0
        answer = f"La frequenza cardiaca media registrata è di {avg_hr:.1f} bpm."
        
    else:
        parts = []
        if elevations:
            parts.append(f"traccia GPX di {len(elevations)} punti")
        if bio_data:
            parts.append(f"{len(bio_data)} marker biomeccanici tracciati")
            
        if parts:
            answer = f"Ho a disposizione: {' e '.join(parts)}. Puoi chiedermi informazioni su potenza, frequenza cardiaca o sull'andamento dei marker video."
        else:
            answer = "Non hai caricato né dati GPX né tracciato video con marker. Carica almeno una delle due fonti per iniziare."

    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
