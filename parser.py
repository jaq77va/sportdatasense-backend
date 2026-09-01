# parsers.py - Modulo di parsing in-memory per FIT, TCX e GPX
import io
import xml.etree.ElementTree as ET
import gpxpy
import fitparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SportDataSense-Parsers")

def parse_telemetry_file(file_content: bytes, filename: str) -> dict:
    """
    Analizza i file di telemetria (FIT, TCX, GPX) interamente in-memory,
    senza scrivere alcun file su disco del server.
    Restituisce un dizionario strutturato con le metriche estratte e i grafici disponibili.
    """
    ext = filename.lower().split('.')[-1]
    logger.info(f"Inizio parsing in-memory per il file: {filename} (formato: {ext})")
    
    timestamps = []
    heart_rate = []
    power = []
    cadence = []
    altitude = []
    distance = []
    speed = []

    try:
        if ext == 'fit':
            # Parsing file binario FIT Garmin
            fit_file = fitparse.FitFile(io.BytesIO(file_content))
            for record in fit_file.get_messages('record'):
                data = {field.name: field.value for field in record}
                if 'timestamp' in data and data['timestamp']:
                    timestamps.append(str(data['timestamp']))
                    heart_rate.append(data.get('heart_rate'))
                    power.append(data.get('power'))
                    cadence.append(data.get('cadence'))
                    altitude.append(data.get('enhanced_altitude') or data.get('altitude'))
                    distance.append(data.get('distance'))
                    speed.append(data.get('enhanced_speed') or data.get('speed'))

        elif ext == 'tcx':
            # Parsing file XML TCX
            tree = ET.parse(io.BytesIO(file_content))
            root = tree.getroot()
            # Namespace tipico TCX
            ns = {'ns': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.html'}
            
            # Cerca tutti i Trackpoint
            for tp in root.iter():
                # Rimuove il namespace per facilitare il match dei tag
                tag = tp.tag.split('}')[-1]
                if tag == 'Trackpoint':
                    time_val, hr_val, pwr_val, cad_val, alt_val, dist_val = None, None, None, None, None, None
                    for child in tp:
                        c_tag = child.tag.split('}')[-1]
                        if c_tag == 'Time':
                            time_val = child.text
                        elif c_tag == 'AltitudeMeters':
                            alt_val = float(child.text) if child.text else None
                        elif c_tag == 'DistanceMeters':
                            dist_val = float(child.text) if child.text else None
                        elif c_tag == 'HeartRateBpm':
                            for sub in child:
                                if sub.tag.split('}')[-1] == 'Value':
                                    hr_val = int(sub.text) if sub.text else None
                        elif c_tag == 'Cadence':
                            cad_val = int(child.text) if child.text else None
                        elif c_tag == 'Extensions':
                            # Ricerca potenza nei blocchi estesi
                            for ext_node in child.iter():
                                if 'Watts' in ext_node.tag:
                                    pwr_val = int(ext_node.text) if ext_node.text else None
                    
                    if time_val:
                        timestamps.append(time_val)
                        heart_rate.append(hr_val)
                        power.append(pwr_val)
                        cadence.append(cad_val)
                        altitude.append(alt_val)
                        distance.append(dist_val)
                        speed.append(None) # Velocità derivata o assente nel singolo punto base

        elif ext == 'gpx':
            # Parsing file GPX con gpxpy
            gpx = gpxpy.parse(file_content.decode('utf-8', errors='ignore'))
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        timestamps.append(str(point.time) if point.time else "")
                        altitude.append(point.elevation)
                        distance.append(None)
                        speed.append(point.speed)
                        
                        # Controllo estensioni GPX per HR e Cadenza se presenti
                        hr_val, cad_val, pwr_val = None, None, None
                        if point.extensions:
                            for ext in point.extensions:
                                for child in ext:
                                    tag_lower = child.tag.lower()
                                    if 'hr' in tag_lower:
                                        hr_val = int(child.text) if child.text else None
                                    elif 'cad' in tag_lower:
                                        cad_val = int(child.text) if child.text else None
                                    elif 'power' in tag_lower or 'watts' in tag_lower:
                                        pwr_val = int(child.text) if child.text else None
                        heart_rate.append(hr_val)
                        cadence.append(cad_val)
                        power.append(pwr_val)
        else:
            raise ValueError(f"Formato file non supportato: {ext}")

        # Identificazione delle metriche effettivamente presenti (non tutte None)
        available_metrics = {
            "heart_rate": any(v is not None for v in heart_rate),
            "power": any(v is not None for v in power),
            "cadence": any(v is not None for v in cadence),
            "altitude": any(v is not None for v in altitude),
            "speed": any(v is not None for v in speed)
        }

        logger.info(f"Parsing completato con successo. Metriche rilevate: {available_metrics}")

        return {
            "filename": filename,
            "total_points": len(timestamps),
            "available_metrics": available_metrics,
            "data": {
                "timestamps": timestamps,
                "heart_rate": heart_rate,
                "power": power,
                "cadence": cadence,
                "altitude": altitude,
                "distance": distance,
                "speed": speed
            }
        }

    except Exception as e:
        logger.error(f"Errore durante il parsing del file {filename}: {str(e)}", exc_info=True)
        raise ValueError(f"Errore di elaborazione telemetrica: {str(e)}")
