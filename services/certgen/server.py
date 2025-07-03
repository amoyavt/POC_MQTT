from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import re

app = FastAPI()

class CertRequest(BaseModel):
    mac: str

def sanitize_mac(mac: str) -> str:
    if not re.fullmatch(r'([0-9a-f]{2}:){5}[0-9a-f]{2}', mac.lower()):
        raise ValueError("Invalid MAC format")
    return mac.lower().replace(":", "-")

@app.post("/issue")
def issue_cert(req: CertRequest):
    try:
        safe_mac = sanitize_mac(req.mac)
        result = subprocess.run(["/app/issue_cert.sh", safe_mac], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())
        return {"message": f"Certificate issued for {req.mac}"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
