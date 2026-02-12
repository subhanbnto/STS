FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Dashboard runs on 5050; Fly will forward to this port
EXPOSE 5050

CMD ["python", "main.py"]
