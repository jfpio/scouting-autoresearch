FROM node:24-bookworm AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json package-lock.json requirements.txt ./
RUN npm ci \
    && python3 -m pip install --break-system-packages --no-cache-dir -r requirements.txt

COPY . .
RUN python3 scripts/validate.py \
    && npm run build

FROM nginx:1.29-alpine
COPY --from=build /app/dist /usr/share/nginx/html/scouting-autoresearch
EXPOSE 80
