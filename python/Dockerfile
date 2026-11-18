FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY app.py .
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8104", "--no-access-log"]
