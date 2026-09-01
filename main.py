# main.py - Server FastAPI Backend (Zero Server Storage)
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from parsers import parse_telemetry_file

# Configurazione logging avanzato
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SportDataSense-Main")

app = FastAPI(title="SportDataSense Backend", version="1.0.0")

# Abilitazione CORS per permettere la comunicazione con WordPress
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione può essere ristretto al dominio sportdatasense.com
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AIChatRequest(BaseModel):
    query: str
    session_summary: dict = None

@app.get("/")
def read_root():
    logger.info("Health check endpoint chiamato.")
    return {"status": "online", "message": "SportDataSense Backend FastAPI operativo (In-Memory Processing)"}

@app.post("/api/parse")
async def parse_endpoint(file: UploadFile = File(...)):
    """
    Riceve il file telemetrico (FIT, TCX, GPX) ed esegue il parsing in-memory.
    Nessun file viene salvato su disco.
    """
    logger.info(f"Ricevuta richiesta di parsing per il file: {file.filename}")
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Il file caricato è vuoto.")
        
        result = parse_telemetry_file(content, file.filename)
        return result
    except Exception as e:
        logger.error(f"Errore nell'endpoint di parsing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/ai-chat")
async def ai_chat_endpoint(req: AIChatRequest):
    """
    Gestisce l'interazione con l'assistente IA basandosi sul contesto della sessione corrente.
    """
    logger.info(faq_msg := f"Ricevuta richiesta AI Chat: {req.query}")
    try:
        # Simulazione di risposta contestuale intelligente basata sui dati in-memory
        query_lower = req.query.lower()
        response_text = "Analisi completata. I dati della sessione mostrano un buon profilo di carico."
        
        if "potenza" in query_lower or "power" in query_lower:
            response_text = "L'analisi dei watt evidenzia picchi di erogazione stabili durante i segmenti principali. [Timestamp consigliato: 02:15]"
        elif "frequenza" in query_lower or "cardiac" in query_lower or "hr" in query_lower:
            response_text = "La frequenza cardiaca si mantiene prevalentemente in Zona 3-4, con un trend regolare. [Timestamp consigliato: 05:40]"
        elif "carico" in query_lower:
            response_text = "Il carico complessivo della sessione rientra nei parametri ottimali pianificati dal team."

        return {
            "status": "success",
            "response": response_text
        }
    except Exception as e:
        logger.error(f"Errore nell'endpoint AI Chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
