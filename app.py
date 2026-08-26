from flask import Flask, request, jsonify
import gpxpy
from flask_cors import CORS
import os
from google import genai

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Inizializzazione client Gemini (assicurati di avere la chiave API configurata nell'ambiente su Render)
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

    # Iniezione della serie temporale dettagliata (inclusa temperatura) dalla vista sincronizzata a schermo
    timeseries_details = ""
    if sync_view and "labels" in sync_view:
        labels = sync_view.get("labels", [])
        series = sync_view.get("series", {})
        timeseries_details = "\n\nSerie temporale dettagliata punto per punto (vista sincronizzata):\n"
        for idx, label in enumerate(labels):
            row_str = f"- Tempo {label}: "
            elements_in_row = []
            for key, values in series.items():
                if values and idx < len(values) and values[idx] is not None:
                    elements_in_row.append(f"{key}={values[idx]}")
            if elements_in_row:
                timeseries_details += row_str + ", ".join(elements_in_row) + "\n"

    system_instruction = (
        "Sei l'assistente esperto di Sport Data Sense, specializzato in analisi di dati sportivi e biomeccanica. "
        "Fornisci sempre risposte estremamente curate dal punto di vista della formattazione visiva: "
        "usa generosamente elenchi puntati (*), grassetti (**...**) per evidenziare i dati chiave, "
        "e sezioni titolate per suddividere l'analisi logica. "
        "Basati rigorosamente sui dati della traccia, sulla serie temporale dettagliata fornita, "
        "sui marker biomeccanici e sulla conversazione. "
        "Se l'utente chiede un valore a uno specifico secondo (es. 4s), cercalo direttamente nella serie temporale fornita. "
        "Se mancano dati cruciali per una stima perfetta (es. FC massima teorica, peso, tipo di vista video), "
        "segnalalo chiaramente alla fine della risposta."
    )

    formatted_contents = []
    formatted_contents.append({
        "role": "user",
        "parts": [{"text": f"Dati di riferimento attuali: {context_summary} {timeseries_details}"}]
    })
    formatted_contents.append({
        "role": "model",
        "parts": [{"text": "Dati ricevuti, indicizzazione temporale e serie analitiche memorizzate correttamente."}]
    })

    # Limitiamo gli ultimi scambi della history per evitare payload giganti
    recent_history = history[-6:] if len(history) > 6 else history
    for message in recent_history[:-1]:
        role = "user" if message.get("role") == "user" else "model"
        content_text = message.get("content", "")
        if content_text:
            formatted_contents.append({
                "role": role,
                "parts": [{"text": content_text[:1000]}]
            })

    formatted_contents.append({
        "role": "user",
        "parts": [{"text": question}]
    })

    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=formatted_contents,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.2,
            }
        )
        answer = response.text
    except Exception as e:
        print(f"ERRORE API: {str(e)}")
        q_lower = question.lower()
        if any(k in q_lower for k in ["frequenza", "cuore", "hr"]):
            answer = f"La frequenza cardiaca media registrata è di {avg_hr:.1f} bpm (Max: {max_hr} bpm)."
        elif any(k in q_lower for k in ["potenza", "watt", "w"]):
            answer = f"La tua potenza media è di {avg_p:.1f}W, con un picco massimo di {max_p}W."
        else:
            answer = f"Analisi completata sui dati disponibili. (Nota di fallback per carico server: {str(e)})"

    return jsonify({"answer": answer})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
