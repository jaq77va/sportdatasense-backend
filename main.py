from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI(title="SportDataSense Backend", version="1.0.0")

# Configurazione CORS per permettere al frontend statico (su Render o locale) di comunicare con il server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione puoi limitarlo all'URL esatto del tuo frontend statico su Render
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AIChatRequest(BaseModel):
    query: str
    session_summary: Optional[Dict[Any, Any]] = None

@app.get("/")
def read_root():
    return {"status": "online", "message": "SportDataSense Backend FastAPI attivo."}

@app.post("/api/parse")
async def parse_telemetry_file(file: UploadFile = File(...)):
    filename = file.filename.lower()
    content = await file.read()
    
    # Esempio di logica di parsing basata sull'estensione del file (FIT, GPX, TCX, CSV, JSON)
    if filename.endswith(('.gpx', '.fit', '.tcx', '.csv', '.json')):
        # Qui inserisci i tuoi parser dedicati per estrarre serie temporali e metriche
        # Restituiamo una struttura dati di esempio coerente con il frontend
        mock_timestamps = list(range(0, 100))
        mock_power = [150 + (i % 50) for i in range(100)]
        mock_hr = [120 + (i % 20) for i in range(100)]
        mock_cadence = [85 + (i % 10) for i in range(100)]
        mock_altitude = [300 + (i * 2) for i in range(100)]
        mock_speed = [25 + ((i % 10) * 0.2) for i in range(100)]

        return {
            "filename": file.filename,
            "available_metrics": {
                "power": True,
                "heart_rate": True,
                "cadence": True,
                "altitude": True,
                "speed": True
            },
            "data": {
                "timestamps": mock_timestamps,
                "power": mock_power,
                "heart_rate": mock_hr,
                "cadence": mock_cadence,
                "altitude": mock_altitude,
                "speed": mock_speed
            }
        }
    else:
        raise HTTPException(status_code=400, detail="Formato file non supportato o non valido.")

@app.post("/api/ai-chat")
async def ai_chat_endpoint(payload: AIChatRequest):
    user_query = payload.query.lower()
    
    # Logica di risposta basata sui dati della sessione o interazione generale
    response_text = f"Ho analizzato la tua richiesta: '{payload.query}'. I dati della sessione sono pronti per essere valutati dal team."
    
    if "potenza" in user_query or "power" in user_query:
        response_text = "Analizzando il profilo di potenza, la distribuzione dello sforzo rientra nei parametri ottimali della sessione."
    elif "frequenza" in user_query or "hr" in user_query:
        response_text = "I valori della frequenza cardiaca mostrano una buona stabilità cardiocircolatoria durante il carico di lavoro."

    return {"response": response_text}
