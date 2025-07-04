from fastapi import FastAPI, HTTPException, Request
import subprocess
import re
import json
import os
from datetime import datetime, timedelta
import sys
import os
import logging
from logging.handlers import RotatingFileHandler
sys.path.append('/app')
from shared.models import CertificateResponse, CertificateRequest

app = FastAPI()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler('/app/logs/certgen-api.log', maxBytes=10485760, backupCount=5)
    ]
)
logger = logging.getLogger(__name__)

def sanitize_mac(mac: str) -> str:
    if not re.fullmatch(r'([0-9a-f]{2}:){5}[0-9a-f]{2}', mac.lower()):
        raise ValueError("Invalid MAC format")
    return mac.lower().replace(":", "")

@app.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "ok", "message": "Certificate Generation Service is running"}

@app.post("/issue", response_model=CertificateResponse)
async def issue_cert(request: CertificateRequest) -> CertificateResponse:
    try:
        mac = request.mac
        logger.info(f"Certificate issuance requested for MAC: {mac}")
        safe_mac = sanitize_mac(mac)
        logger.info(f"MAC sanitized: {safe_mac}")
        logger.info(f"Executing certificate generation script for MAC: {safe_mac}")
        result = subprocess.run(
            ["/app/issue_cert.sh", safe_mac], capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error(f"Certificate generation failed for MAC {safe_mac}: {result.stderr}")
            raise RuntimeError(result.stderr)
        logger.info(f"Certificate generation completed successfully for MAC: {safe_mac}")
        
        # Read the generated certificate files
        cert_file = f"/issued/{safe_mac}.crt"
        key_file = f"/issued/{safe_mac}.key"
        ca_cert_file = "/ca/ca.crt"
        
        # Check if files exist
        logger.info(f"Checking for certificate files: {cert_file}, {key_file}, {ca_cert_file}")
        if not os.path.exists(cert_file):
            logger.error(f"Certificate file not found: {cert_file}")
            raise FileNotFoundError(f"Certificate file not found: {cert_file}")
        if not os.path.exists(key_file):
            logger.error(f"Private key file not found: {key_file}")
            raise FileNotFoundError(f"Private key file not found: {key_file}")
        if not os.path.exists(ca_cert_file):
            logger.error(f"CA certificate file not found: {ca_cert_file}")
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
        
        logger.info(f"Certificate successfully issued for MAC: {mac}, expires at: {expires_at}")
        return CertificateResponse(
            mac=mac,
            client_cert=client_cert,
            private_key=private_key,
            ca_cert=ca_cert,
            expires_at=expires_at
        )
    except ValueError as ve:
        logger.error(f"Invalid MAC format provided: {mac} - {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError as fe:
        logger.error(f"File not found error for MAC {mac}: {str(fe)}")
        raise HTTPException(status_code=500, detail=str(fe))
    except Exception as e:
        logger.error(f"Unexpected error during certificate issuance for MAC {mac}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
