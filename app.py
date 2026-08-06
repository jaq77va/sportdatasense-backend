from flask import Flask, request

app = Flask(__name__)

@app.route("/process_gpx", methods=["POST"])
def process_gpx():
    print("LOG SERVER: Richiesta ricevuta su /process_gpx")

    file = request.files.get("gpx")

    if not file:
        print("LOG SERVER: Nessun file ricevuto")
        return "Nessun file ricevuto"

    print(f"LOG SERVER: File ricevuto: {file.filename}, dimensione: {len(file.read())} bytes")

    return f"File ricevuto: {file.filename}"
