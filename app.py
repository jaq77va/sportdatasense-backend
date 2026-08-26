from flask import Flask, request, jsonify
import gpxpy
from flask_cors import CORS
import os
import time
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Inizializzazione client Gemini (assicurati di avere la chiave API configurata nell'ambiente su Render)[cite: 5]
client = genai.Client()

@app.route("/")
def home():
    return "SportDataSense Backend v2.0 - Chat con Cronologia Attiva"

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

    # Contesto sintetico di base
    context_summary = (
        f"Statistiche traccia: Punti totali={len(elevations)}, "
        f"FC Media={avg_hr:.1f}bpm (Max={max_hr}), "
        f"Potenza Media={avg_p:.1f}W (Max={max_p}), "
        f"Marker video tracciati={len(bio_data) if bio_data else 0}."
    )

    # Iniezione della serie temporale dettagliata e dei marker biomeccanici dalla vista sincronizzata a schermo
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
            timeseries_details += "\nCoordinate dei Marker Biomeccanici video punto per punto:\n"
            for item in bio_series:
                sec = item.get("second") or item.get("time") or "N/D"
                markers = item.get("markers", [])
                marker_strs = []
                for m_idx, m_coords in enumerate(markers):
                    if m_coords:
                        mx = m_coords.get("x", "N/D")
                        my = m_coords.get("y", "N/D")
                        marker_strs.append(f"Marker {m_idx+1}(X={mx}, Y={my})")
                if marker_strs:
                    timeseries_details += f"- Secondo {sec}s: " + ", ".join(marker_strs) + "\n"

    system_instruction = (
        "Sei l'assistente esperto di Sport Data Sense, specializzato in analisi di dati sportivi e biomeccanica. "
        "Fornisci sempre risposte estremamente curate dal punto di vista della formattazione visiva: "
        "usa generosamente elenchi puntati (*), grassetti (**...**) per evidenziare i dati chiave, "
        "e sezioni titolate per suddividere l'analisi logica. "
        "Basati rigorosamente sui dati della traccia, sulla serie temporale dettagliata fornita, "
        "sui marker biomeccanici e sulla conversazione. "
        "Se l'utente chiede un valore a uno specifico secondo (es. 4s o 5s), cercalo direttamente nella serie temporale o nelle coordinate dei marker fornite. "
        "Se mancano dati cruciali per una stima perfetta (es. FC massima teorica, peso, tipo di vista video), "
        "segnalalo chiaramente alla fine della risposta."
    )

    formatted_history = []
    initial_context_text = f"Dati di riferimento attuali: {context_summary} {timeseries_details}"
    formatted_history.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=initial_context_text)]
        )
    )
    formatted_history.append(
        types.Content(
            role="model",
            parts=[types.Part.from_text(text="Dati ricevuti, indicizzazione temporale e serie analitiche memorizzate correttamente.")]
        )
    )

    recent_history = history[-6:] if len(history) > 6 else history
    for message in recent_history[:-1]:
        role = "user" if message.get("role") == "user" else "model"
        content_text = message.get("content", "")
        if content_text:
            formatted_history.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content_text[:1000])]
                )
            )

    # Logica di Retry per gestire gli errori temporanei 503 / High Demand
    max_retries = 3
    retry_delay = 1.5
    answer = None

    for attempt in range(max_retries):
        try:
            chat = client.chats.create(
                model='gemini-3.6-flash',
                history=formatted_history,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                )
            )
            
            response = chat.send_message(question)
            answer = response.text
            break # Se ha successo, usciamo dal ciclo di retry
            
        except Exception as e:
            error_str = str(e)
            print(f"Tentativo {attempt + 1} fallito - ERRORE API: {error_str}")
            
            # Se è un errore 503 o di alto traffico e abbiamo ancora tentativi, attendiamo e riproviamo
            if ("503" in error_str or "UNAVAILABLE" in error_str or "high demand" in error_str) and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Raddoppia l'attesa per il tentativo successivo (es. 1.5s -> 3s)
                continue
            
            # Se i tentativi sono esauriti o è un altro tipo di errore, applichiamo il fallback
            if attempt == max_retries - 1:
                answer = "I server di IA sono momentaneamente sovraccarichi (503). Riprova tra qualche istante."
            else:
                q_lower = question.lower()
                if any(k in q_lower for k in ["frequenza", "cuore", "hr"]):
                    answer = f"La frequenza cardiaca media registrata è di {avg_hr:.1f} bpm (Max: {max_hr} bpm)."
                elif any(k in q_lower for k in ["potenza", "watt", "w"]):
                    answer = f"La tua potenza media è di {avg_p:.1f}W, con un picco massimo di {max_p}W."
                else:
                    answer = f"Analisi completata sui dati disponibili. (Nota di fallback per carico server: {error_str})"

    return jsonify({"answer": answer})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
