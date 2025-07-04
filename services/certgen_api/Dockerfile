FROM python:3-alpine

WORKDIR /app

# Copy all files explicitly
COPY services/certgen_api/api.py .
COPY services/certgen_api/issue_cert.sh .
COPY services/certgen_api/openssl.cnf .
COPY services/certgen_api/entrypoint.sh .
COPY services/shared ./shared

# Install required packages, fix line endings, set permissions
RUN apk update && \
    apk add --no-cache bash dos2unix openssl && \
    pip install uv && \
    uv pip install --system fastapi uvicorn && \
    dos2unix /app/issue_cert.sh && \
    dos2unix /app/entrypoint.sh && \
    chmod +x /app/issue_cert.sh /app/entrypoint.sh

EXPOSE 8080

CMD ["sh", "/app/entrypoint.sh"]
