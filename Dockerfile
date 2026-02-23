FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt

# Copy backend code
COPY backend/ .

# Expose port
EXPOSE 8080

# Start command
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
