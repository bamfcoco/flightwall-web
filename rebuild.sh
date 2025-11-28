#!/bin/bash

cd /mnt/user/appdata/flightwall-web || exit 1

echo "Stopping container..."
docker stop flightwall-web 2>/dev/null

echo "Removing container..."
docker rm flightwall-web 2>/dev/null

echo "Rebuilding image..."
docker build -t flightwall-web .

echo "Starting container..."
docker run -d \
  --name flightwall-web \
  --restart unless-stopped \
  -p 8440:8440 \
  -e FLIGHTWALL_CENTER_LAT="42.5031239" \
  -e FLIGHTWALL_CENTER_LON="-83.6237014" \
  -e FLIGHTWALL_CENTER_LABEL="Y47 - OAKLAND SOUTHWEST" \
  -e FLIGHTWALL_RADIUS_KM="40" \
  flightwall-web

echo "Done! FlightWall has been rebuilt and restarted."
