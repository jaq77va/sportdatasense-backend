import io
import datetime
import xml.etree.ElementTree as ET
from fitparse import FitFile
import gpxpy

def parse_telemetry_file(file_content: bytes, filename: str) -> dict:
    """
    Parser professionale conforme alle specifiche ufficiali Garmin FIT SDK e TCX XSD.
    Esegue l'elaborazione interamente in-memory (Zero Server Storage).
    """
    ext = filename.split('.')[-1].lower()
    data = {
        "filename": filename,
        "format": ext,
        "timestamps": [],
        "heart_rate": [],
        "power": [],
        "cadence": [],
        "altitude": [],
        "distance": [],
        "speed": [],
        "available_metrics": []
    }

    try:
        if ext == 'fit':
            # Parsing file FIT binario ufficiale
            fitfile = FitFile(io.BytesIO(file_content))
            for record in fitfile.get_messages('record'):
                rec = {field.name: field.value for field in record}
                
                ts = rec.get('timestamp')
                if isinstance(ts, datetime.datetime):
                    data["timestamps"].append(ts.isoformat())
                else:
                    data["timestamps"].append(str(ts) if ts else "")
                
                data["heart_rate"].append(rec.get('heart_rate') or rec.get('enhanced_heart_rate'))
                data["power"].append(rec.get('power'))
                data["cadence"].append(rec.get('cadence'))
                data["altitude"].append(rec.get('altitude') or rec.get('enhanced_altitude'))
                data["distance"].append(rec.get('distance'))
                data["speed"].append(rec.get('speed') or rec.get('enhanced_speed'))

        elif ext == 'gpx':
            # Parsing file GPX standard
            gpx = gpxpy.parse(file_content.decode('utf-8', errors='ignore'))
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        data["timestamps"].append(point.time.isoformat() if point.time else "")
                        data["altitude"].append(point.elevation)
                        data["distance"].append(None)
                        data["heart_rate"].append(None)
                        data["power"].append(None)
                        data["cadence"].append(None)
                        data["speed"].append(point.speed)

        elif ext == 'tcx':
            # Parsing file TCX Garmin con gestione namespace
            root = ET.fromstring(file_content)
            ns = {
                'ns': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2',
                'ns3': 'http://www.garmin.com/xmlschemas/ActivityExtension/v2'
            }
            
            for trackpoint in root.iter('{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}Trackpoint'):
                time_elem = trackpoint.find('ns:Time', ns)
                hr_elem = trackpoint.find('ns:HeartRateBpm/ns:Value', ns)
                dist_elem = trackpoint.find('ns:DistanceMeters', ns)
                alt_elem = trackpoint.find('ns:AltitudeMeters', ns)
                cad_elem = trackpoint.find('ns:Cadence', ns)
                
                power_val = None
                extensions = trackpoint.find('ns:Extensions', ns)
                if extensions is not None:
                    tpx = extensions.find('.//ns3:Watts', ns)
                    if tpx is not None:
                        try:
                            power_val = float(tpx.text)
                        except ValueError:
                            pass

                data["timestamps"].append(time_elem.text if time_elem is not None else "")
                data["heart_rate"].append(int(hr_elem.text) if hr_elem is not None else None)
                data["distance"].append(float(dist_elem.text) if dist_elem is not None else None)
                data["altitude"].append(float(alt_elem.text) if alt_elem is not None else None)
                data["cadence"].append(int(cad_elem.text) if cad_elem is not None else None)
                data["power"].append(power_val)
                data["speed"].append(None)

        # Mappatura delle metriche presenti
        if any(v is not None for v in data["power"]): data["available_metrics"].append("power")
        if any(v is not None for v in data["heart_rate"]): data["available_metrics"].append("heart_rate")
        if any(v is not None for v in data["cadence"]): data["available_metrics"].append("cadence")
        if any(v is not None for v in data["altitude"]): data["available_metrics"].append("altitude")
        if any(v is not None for v in data["speed"]): data["available_metrics"].append("speed")

    except Exception as e:
        data["error"] = f"Errore di parsing: {str(e)}"

    return data
