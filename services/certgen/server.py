from fastapi import FastAPI, HTTPException, Request
import subprocess
import re
import json
import os
from datetime import datetime, timedelta

app = FastAPI()

def sanitize_mac(mac: str) -> str:
    if not re.fullmatch(r'([0-9a-f]{2}:){5}[0-9a-f]{2}', mac.lower()):
        raise ValueError("Invalid MAC format")
    return mac.lower().replace(":", "")

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Certificate Generation Service is running"}

@app.post("/issue")
async def issue_cert(request: Request):
    try:
        data = await request.json()
        mac = data['mac']
        safe_mac = sanitize_mac(mac)
        result = subprocess.run(
            ["/app/issue_cert.sh", safe_mac], capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        
        # Read the generated certificate files
        cert_file = f"/issued/{safe_mac}.crt"
        key_file = f"/issued/{safe_mac}.key"
        ca_cert_file = "/ca/ca.crt"
        
        # Check if files exist
        if not os.path.exists(cert_file):
            raise FileNotFoundError(f"Certificate file not found: {cert_file}")
        if not os.path.exists(key_file):
            raise FileNotFoundError(f"Private key file not found: {key_file}")
        if not os.path.exists(ca_cert_file):
            raise FileNotFoundError(f"CA certificate file not found: {ca_cert_file}")
        
        # Read certificate contents
        with open(cert_file, 'r') as f:
            client_cert = f.read()
        with open(key_file, 'r') as f:
            private_key = f.read()
        with open(ca_cert_file, 'r') as f:
            ca_cert = f.read()
        
        # Calculate expiry date (assuming DEVICE_EXPIRY days from now)
        device_expiry = int(os.getenv('DEVICE_EXPIRY', '365'))
        expires_at = (datetime.now() + timedelta(days=device_expiry)).isoformat() + "Z"
        
        return {
            "mac": mac,
            "client_cert": client_cert,
            "private_key": private_key,
            "ca_cert": ca_cert,
            "expires_at": expires_at
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except KeyError:
        raise HTTPException(status_code=400, detail="Missing 'mac' field in JSON payload")
    except FileNotFoundError as fe:
        raise HTTPException(status_code=500, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
