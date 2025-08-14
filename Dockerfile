# Stage 1: Build the client
FROM node:20-slim AS client
WORKDIR /app/client
COPY client/package.json client/package-lock.json ./ 
RUN npm install
COPY client/ ./ 
RUN npm run build

# Stage 2: Build the server
FROM python:3.11-slim

WORKDIR /app/server
COPY server/requirements.txt ./ 
RUN pip install --no-cache-dir -r requirements.txt

# Install FileBot
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL "https://raw.githubusercontent.com/filebot/plugins/master/gpg/maintainer.pub" | gpg --dearmor --output "/usr/share/keyrings/filebot.gpg" && \
    echo "deb [arch=all signed-by=/usr/share/keyrings/filebot.gpg] https://get.filebot.net/deb/ universal main" | tee "/etc/apt/sources.list.d/filebot.list" && \
    apt-get update && \
    apt-get install -y filebot && \
    apt-get clean

COPY server/ ./ 
COPY --from=client /app/client/dist ./static/client

ENV FLASK_APP=app.py
ENV FLASK_DEBUG=0


