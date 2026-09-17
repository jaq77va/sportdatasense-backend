from flask import Flask, request, jsonify
import gpxpy
from flask_cors import CORS
import os
import time
import math
from datetime import datetime
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

client = genai.Client()

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calcola la distanza in chilometri tra due punti geografici usando la formula di Haversine.
    """
    R = 6371.0  # Raggio medio della Terra in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def extract_extensions(element):
    """
    Funzione ausiliaria per estrarre in modo ricorsivo i dati estesi dai tag GPX.
    """
    data = {}
    if element is None:
        return data
        
    for child in element:
        tag = child.tag.split('}')[-1].lower() if '}' in child.tag else child.tag.lower()
        if child.text and child.text.strip():
            try:
                if '.' in child.text:
                    data[tag] = float(child.text)
                else:
                    data[tag] = int(child.text)
            except ValueError:
                data[tag] = child.text.strip()
        
        # Ricorsione sui nodi figli
        data.update(extract_extensions(child))
    return data

@app.route("/")
def home():
    return "SportDataSense Backend v2.0 - Biomeccanica Avanzata & Synchronized Viewer"

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
    
    # Serie temporali e metriche per i grafici
    distance = []      # Distanza progressiva in km (Profilo Altimetrico, Tempo vs Distanza)
    speed = []         # Velocità istantanea in km/h
    pace = []          # Passo istantaneo in min/km
    elapsed_time = []  # Tempo trascorso in secondi dall'inizio
    logs = []

    total_dist = 0.0
    first_timestamp = None

    for track in gpx.tracks:
        for segment in track.segments:
            for i, point in enumerate(segment.points):
                curr_lat = point.latitude
                curr_lon = point.longitude
                curr_ele = point.elevation
                
                # Conversione e gestione timestamp
                p_time = point.time
                p_time_str = p_time.isoformat() if p_time else None

                if p_time:
                    if first_timestamp is None:
                        first_timestamp = p_time
                    sec_elapsed = (p_time - first_timestamp).total_seconds()
                else:
                    sec_elapsed = 0 if not elapsed_time else elapsed_time[-1]

                # Calcolo della distanza progressiva, velocità e passo
                curr_speed = 0.0
                curr_pace = 0.0

                if i == 0 and len(distance) == 0:
                    total_dist = 0.0
                else:
                    prev_lat = lat[-1]
                    prev_lon = lon[-1]
                    delta_d = haversine_distance(prev_lat, prev_lon, curr_lat, curr_lon)
                    total_dist += delta_d

                    if i > 0 and segment.points[i-1].time and p_time:
                        time_diff = (p_time - segment.points[i-1].time).total_seconds()
                        if time_diff > 0:
                            curr_speed = delta_d / (time_diff / 3600.0)  # km/h
                            if curr_speed > 0:
                                curr_pace = 60.0 / curr_speed  # min/km

                lat.append(curr_lat)
                lon.append(curr_lon)
                ele.append(curr_ele)
                times.append(p_time_str)
                distance.append(round(total_dist, 3))
                speed.append(round(curr_speed, 2))
                pace.append(round(curr_pace, 2))
                elapsed_time.append(sec_elapsed)

                # Estrazione avanzata e ricorsiva delle estensioni (HR, Cadence, Power, Temp)
                h, c, p, t = None, None, None, None
                if point.extensions:
                    exts = point.extensions if isinstance(point.extensions, list) else [point.extensions]
                    for ext in exts:
                        ext_data = extract_extensions(ext)
                        
                        for key, val in ext_data.items():
                            if 'hr' in key or 'heartrate' in key:
                                h = int(val) if isinstance(val, (int, float)) else h
                            elif 'cad' in key or 'cadence' in key:
                                c = int(val) if isinstance(val, (int, float)) else c
                            elif 'power' in key or 'watts' in key:
                                p = int(val) if isinstance(val, (int, float)) else p
                            elif 'atemp' in key or 'temp' in key:
                                t = float(val) if isinstance(val, (int, float)) else t
                
                hr.append(h)
                cad.append(c)
                power.append(p)
                temp.append(t)

    # Generazione coordinate tridimensionali per la Mappa 3D
    map_3d_coordinates = [
        {"lat": l, "lon": ln, "ele": e if e is not None else 0.0}
        for l, ln, e in zip(lat, lon, ele)
    ]

    return jsonify({
        "lat": lat, 
        "lon": lon, 
        "ele": ele, 
        "times": times,
        "hr": hr, 
        "cad": cad, 
        "power": power, 
        "temp": temp,
        "distance": distance,                  # Profilo Altimetrico e Tempo vs Distanza
        "speed": speed,                        # Velocità istantanea (km/h)
        "pace": pace,                          # Passo (min/km)
        "elapsed_time": elapsed_time,          # Tempo trascorso in secondi
        "map_3d_coordinates": map_3d_coordinates, # Coordinate 3D per rendering mappa
        "logs": logs
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
                model='gemini-2.5-flash',
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
