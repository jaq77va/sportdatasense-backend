from flask import Flask, request, jsonify
import gpxpy
from flask_cors import CORS
import os
import time
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

client = genai.Client()

@app.route("/")
def home():
    return "SportDataSense Backend v2.0 - Biomeccanica Avanzata (Coordinate + Angoli)"

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
    req = request.json or {}
    question = req.get("question", "")
    history = req.get("history", [])
    gpx_data = req.get("data", {})
    bio_data = req.get("biomechanical_data", None)
    sync_view = req.get("synchronized_view", None)
    
    elevations = gpx_data.get("ele", []) if gpx_data else []
    powers = gpx_data.get("power", []) if gpx_data else []
    hrs = gpx_data.get("hr", []) if gpx_data else []

    valid_hr = [h for h in hrs if h is not None]
    avg_hr = sum(valid_hr) / len(valid_hr) if valid_hr else 0
    max_hr = max(valid_hr) if valid_hr else 0

    valid_p = [p for p in powers if p is not None]
    avg_p = sum(valid_p) / len(valid_p) if valid_p else 0
    max_p = max(valid_p) if valid_p else 0

    context_summary = (
        f"Statistiche traccia: Punti totali={len(elevations)}, "
        f"FC Media={avg_hr:.1f}bpm (Max={max_hr}), "
        f"Potenza Media={avg_p:.1f}W (Max={max_p}), "
        f"Marker video tracciati={len(bio_data) if bio_data else 0}."
    )

    timeseries_details = ""
    if sync_view:
        labels = sync_view.get("labels", [])
        series = sync_view.get("series", {})
        bio_series = sync_view.get("biomechanical_series", [])
        
        timeseries_details = "\n\nSerie temporale dettagliata punto per punto (vista sincronizzata):\n"
        
        if labels and series:
            for idx, label in enumerate(labels):
                row_str = f"- Tempo {label}: "
                elements_in_row = []
                for key, values in series.items():
                    if values and idx < len(values) and values[idx] is not None:
                        elements_in_row.append(f"{key}={values[idx]}")
                if elements_in_row:
                    timeseries_details += row_str + ", ".join(elements_in_row) + "\n"
        
        if bio_series:
            timeseries_details += "\nDati Biomeccanici video (Coordinate Marker e Angoli) punto per punto:\n"
            for item in bio_series:
                sec = item.get("second") or item.get("time") or "N/D"
                markers = item.get("markers", [])
                angle = item.get("angle", None)
                
                marker_strs = []
                for m_idx, m_coords in enumerate(markers):
                    if m_coords:
                        mx = m_coords.get("x", "N/D")
                        my = m_coords.get("y", "N/D")
                        marker_strs.append(f"M{m_idx+1}(X={mx}, Y={my})")
                
                line_desc = f"- Secondo {sec}s: "
                if marker_strs:
                    line_desc += ", ".join(marker_strs)
                if angle is not None:
                    line_desc += f" | Angolo Articolare={angle}°"
                timeseries_details += line_desc + "\n"

    system_instruction = (
        "Sei l'assistente esperto di Sport Data Sense, specializzato in analisi di dati sportivi e biomeccanica. "
        "Fornisci sempre risposte curate con elenchi puntati (*), grassetti (**...**) e sezioni titolate. "
        "Basati rigorosamente sui dati della traccia, sulla serie temporale e sui dati biomeccanici (coordinate e angoli)."
    )

    formatted_history = []
    initial_context_text = f"Dati di riferimento attuali: {context_summary} {timeseries_details}"
    formatted_history.append(types.Content(role="user", parts=[types.Part.from_text(text=initial_context_text)]))
    formatted_history.append(types.Content(role="model", parts=[types.Part.from_text(text="Dati biomeccanici, coordinate e angoli memorizzati correttamente.")]))

    recent_history = history[-6:] if len(history) > 6 else history
    for message in recent_history[:-1]:
        role = "user" if message.get("role") == "user" else "model"
        content_text = message.get("content", "")
        if content_text:
            formatted_history.append(types.Content(role=role, parts=[types.Part.from_text(text=content_text[:1000])]))

    answer = None
    for attempt in range(3):
        try:
            chat = client.chats.create(
                model='gemini-3.6-flash',
                history=formatted_history,
                config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
            )
            response = chat.send_message(question)
            answer = response.text
            break
        except Exception as e:
            if attempt == 2:
                answer = "I server di IA sono momentaneamente sovraccarichi. Riprova tra qualche istante."
            else:
                time.sleep(1.5)

    return jsonify({"answer": answer})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
