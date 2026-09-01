from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from parsers import parse_telemetry_file

app = FastAPI(title="SportDataSense Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AIChatRequest(BaseModel):
    message: str
    session_data: dict = {}

@app.get("/")
def read_root():
    return {"status": "online", "message": "SportDataSense API Server attivo in-memory."}

@app.post("/api/parse")
async def parse_file_endpoint(file: UploadFile = File(...)):
    content = await file.read()
    parsed_data = parse_telemetry_file(content, file.filename)
    if "error" in parsed_data:
        raise HTTPException(status_code=400, detail=parsed_data['error'])
    return {"success": True, "data": parsed_data}

@app.post("/api/ai-chat")
async def ai_chat_endpoint(payload: AIChatRequest):
    return {
        "reply": f"Analisi completata per la richiesta: '{payload.message}'.",
        "timestamp_link": "04:15"
    }
