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
    req = request.json or {}
    question = req.get("question", "")
    history = req.get("history", []) # Riceviamo lo storico della chat dal frontend
    gpx_data = req.get("data", {})
    bio_data = req.get("biomechanical_data", None)  # Riceve i dati dei marker video
    
    # Estraiamo i dati di riepilogo di base
    elevations = gpx_data.get("ele", []) if gpx_data else []
    powers = gpx_data.get("power", []) if gpx_data else []
    hrs = gpx_data.get("hr", []) if gpx_data else []
    cads = gpx_data.get("cad", []) if gpx_data else []

    # Calcoli statistici rapidi di supporto da passare come contesto all'AI
    valid_hr = [h for h in hrs if h is not None]
    avg_hr = sum(valid_hr) / len(valid_hr) if valid_hr else 0
    max_hr = max(valid_hr) if valid_hr else 0

    valid_p = [p for p in powers if p is not None]
    avg_p = sum(valid_p) / len(valid_p) if valid_p else 0
    max_p = max(valid_p) if valid_p else 0

    # Prepariamo un contesto riassuntivo pulito dei dati attualmente caricati
    context_summary = (
        f"[Dati Traccia caricati]\n"
        f"- Punti totali: {len(elevations)}\n"
        f"- Frequenza Cardiaca Media: {avg_hr:.1f} bpm (Max: {max_hr} bpm)\n"
        f"- Potenza Media: {avg_p:.1f}W (Max: {max_p}W)\n"
        f"- Dati Biomeccanici Video (Marker): {len(bio_data) if bio_data else 0} marker tracciati."
    )

    # Istruzione di sistema per garantire analisi profonde e indicazione dei dati mancanti
    system_instruction = (
        "Sei l'assistente esperto di Sport Data Sense, specializzato in analisi di dati sportivi (GPX/FIT) "
        "e biomeccanica. Fornisci sempre analisi approfondite, critiche e strutturate basandoti sui dati della traccia, "
        "sui dati biomeccanici e sulla cronologia della conversazione. "
        "Se l'utente menziona informazioni anagrafiche o personali (es. l'età), ricordale e usale per valutare parametri come la frequenza cardiaca. "
        "Se mancano dati cruciali per darti una risposta o una stima perfetta (es. FC massima teorica, peso, soglie), "
        "rispondi comunque in modo completo ed esaustivo con i dati che possiedi, e indica chiaramente quali metriche o informazioni "
        "ulteriori mancherebbero per raggiungere la massima precisione."
    )

    # Ricostruiamo la cronologia dei messaggi per Gemini
    formatted_contents = []
    
    # Iniettiamo il contesto dei dati come primo messaggio di sistema/istruzione nascosta o lo accodiamo
    formatted_contents.append({
        "role": "user",
        "parts": [{"text": f"Contesto attuale dell'atleta:\n{context_summary}\n\nTieni conto di questi dati per le risposte future."}]
    })
    formatted_contents.append({
        "role": "model",
        "parts": [{"text": "Ho memorizzato il contesto dei dati attuali. Sono pronto ad analizzarli."}]
    })

    # Aggiungiamo lo storico reale della chat precedente
    for message in history[:-1]: # Escludiamo l'ultima che aggiungiamo pulita sotto
        role = "user" if message.get("role") == "user" else "model"
        content_text = message.get("content", "")
        if content_text:
            formatted_contents.append({
                "role": role,
                "parts": [{"text": content_text}]
            })

    # Aggiungiamo la domanda corrente
    formatted_contents.append({
        "role": "user",
        "parts": [{"text": question}]
    })

    try:
        # Chiamata al modello Gemini per una risposta fluida, contestuale e approfondita
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=formatted_contents,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.4,
            }
        )
        answer = response.text
    except Exception as e:
        # Fallback di sicurezza basato sulla tua logica originaria se l'API dovesse avere problemi temporanei
        if bio_data and any(k in question.lower() for k in ["marker", "video", "coordinata", "x", "y", "z", "andamento"]):
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
        elif "frequenza" in question.lower() or "cuore" in question.lower() or "hr" in question.lower():
            answer = f"La frequenza cardiaca media registrata è di {avg_hr:.1f} bpm (Max: {max_hr} bpm)."
        else:
            answer = f"La frequenza cardiaca media registrata è di {avg_hr:.1f} bpm. (Nota di fallback offline: {str(e)})"

    return jsonify({"answer": answer})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
