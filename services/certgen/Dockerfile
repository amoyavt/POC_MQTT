FROM python:3-alpine

WORKDIR /app
COPY server.py .
COPY issue_cert.sh /app/issue_cert.sh
COPY openssl.cnf /ca/openssl.cnf
COPY entrypoint.sh /app/entrypoint.sh

RUN apt-get update && \
    apt-get install -y openssl && \
    rm -rf /var/lib/apt/lists/* && \
    pip install fastapi uvicorn && \
    chmod +x /app/issue_cert.sh /app/entrypoint.sh

EXPOSE 8080
CMD ["/app/entrypoint.sh"]
