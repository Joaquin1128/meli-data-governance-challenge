FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml requirements-api.txt ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir -r requirements-api.txt

EXPOSE 8000

CMD ["uvicorn", "meli_api.adapters.inbound.http.app:app", "--host", "0.0.0.0", "--port", "8000"]
