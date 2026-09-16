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
    R = 6371.0  # Raggio medio della Terra in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def extract_extensions(element):
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
    distance, speed, pace, elapsed_time = [], [], [], []
    logs = []

    total_dist = 0.0
    first_timestamp = None

    for track in gpx.tracks:
        for segment in track.segments:
            for i, point in enumerate(segment.points):
                curr_lat = point.latitude
                curr_lon = point.longitude
                curr_ele = point.elevation
                p_time = point.time
                p_time_str = p_time.isoformat() if p_time else None

                if p_time:
                    if first_timestamp is None:
                        first_timestamp = p_time
                    sec_elapsed = (p_time - first_timestamp).total_seconds()
                else:
                    sec_elapsed = 0 if not elapsed_time else elapsed_time[-1]

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
                            curr_speed = delta_d / (time_diff / 3600.0)
                            if curr_speed > 0:
                                curr_pace = 60.0 / curr_speed

                lat.append(curr_lat)
                lon.append(curr_lon)
                ele.append(curr_ele)
                times.append(p_time_str)
                distance.append(round(total_dist, 3))
                speed.append(round(curr_speed, 2))
                pace.append(round(curr_pace, 2))
                elapsed_time.append(sec_elapsed)

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

    map_3d_coordinates = [
        {"lat": l, "lon": ln, "ele": e if e is not None else 0.0}
        for l, ln, e in zip(lat, lon, ele)
    ]

    return jsonify({
        "lat": lat, "lon": lon, "ele": ele, "times": times,
        "hr": hr, "cad": cad, "power": power, "temp": temp,
        "distance": distance, "speed": speed, "pace": pace, 
        "elapsed_time": elapsed_time, "map_3d_coordinates": map_3d_coordinates,
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

    system_instruction = (
        "Sei l'assistente esperto di Sport Data Sense, specializzato in analisi di dati sportivi e biomeccanica. "
        "Fornisci sempre risposte curate con elenchi puntati (*), grassetti (**...**) e sezioni titolate."
    )

    formatted_history = []
    initial_context_text = f"Dati di riferimento attuali: {context_summary}"
    formatted_history.append(types.Content(role="user", parts=[types.Part.from_text(text=initial_context_text)]))
    formatted_history.append(types.Content(role="model", parts=[types.Part.from_text(text="Dati memorizzati correttamente.")]))

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
