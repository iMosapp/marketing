FROM python:3.11-slim

# Install Node.js for building frontend
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Build frontend
COPY frontend/ ./frontend/
WORKDIR /app/frontend
RUN npm install -g yarn && yarn install && npx expo export --platform web

# Move frontend build to be served by backend
RUN mkdir -p /app/backend/static && cp -r /app/frontend/dist/* /app/backend/static/

WORKDIR /app/backend

# Expose port
EXPOSE 8080

# Start command
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
