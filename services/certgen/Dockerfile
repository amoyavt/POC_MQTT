FROM python:3-alpine

WORKDIR /app
COPY server.py .
COPY issue_cert.sh /app/issue_cert.sh
COPY openssl.cnf /app/openssl.cnf
COPY entrypoint.sh /app/entrypoint.sh

RUN apk update && \
    apk add --no-cache openssl && \
    pip install uv && \
    uv pip install --system fastapi uvicorn && \
    chmod +x /app/issue_cert.sh /app/entrypoint.sh

EXPOSE 8080
CMD ["sh", "/app/entrypoint.sh"]
