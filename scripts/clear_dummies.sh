#!/usr/bin/env bash
set -euo pipefail

# Load PLEX_TOKEN, DISCOVER_MOVIES_LIB, DISCOVER_SHOWS_LIB from .env
ENV_FILE="$(dirname "$0")/../.env"
if [[ -f "$ENV_FILE" ]]; then
  export $(grep -v '^#' "$ENV_FILE" | grep -E '^(PLEX_TOKEN|DISCOVER_MOVIES_LIB|DISCOVER_SHOWS_LIB)=' | xargs)
fi

PLEX_TOKEN="${PLEX_TOKEN:?PLEX_TOKEN not set}"
# Always use localhost since this script runs on the host, not inside docker
PLEX_URL="http://localhost:32400"
MOVIES_LIB="${DISCOVER_MOVIES_LIB:-Movies}"
SHOWS_LIB="${DISCOVER_SHOWS_LIB:-TV Shows}"

echo "==> Deleting dummy .mkv files..."
docker exec plexflixarr sh -c '
  find /data/discover_movies /data/discover_shows -name "*.mkv" -delete
  find /data/discover_movies /data/discover_shows -mindepth 1 -type d -empty -delete
  echo "Files deleted."
'

echo "==> Fetching Plex library section IDs..."
SECTIONS_JSON=$(curl -sf "${PLEX_URL}/library/sections?X-Plex-Token=${PLEX_TOKEN}" \
  -H "Accept: application/json")

MOVIES_KEY=$(echo "$SECTIONS_JSON" | jq -r --arg lib "$MOVIES_LIB" \
  '.MediaContainer.Directory[] | select(.title == $lib) | .key')
SHOWS_KEY=$(echo "$SECTIONS_JSON" | jq -r --arg lib "$SHOWS_LIB" \
  '.MediaContainer.Directory[] | select(.title == $lib) | .key')

echo "  Movies section: ${MOVIES_KEY:-not found} ($MOVIES_LIB)"
echo "  Shows section:  ${SHOWS_KEY:-not found} ($SHOWS_LIB)"

for KEY in $MOVIES_KEY $SHOWS_KEY; do
  echo "==> Scanning section $KEY (forced)..."
  curl -sf "${PLEX_URL}/library/sections/${KEY}/refresh?force=1&X-Plex-Token=${PLEX_TOKEN}" > /dev/null
done

echo "==> Waiting for scans to settle (60s)..."
sleep 60

for KEY in $MOVIES_KEY $SHOWS_KEY; do
  echo "==> Emptying trash for section $KEY..."
  curl -sf -X PUT "${PLEX_URL}/library/sections/${KEY}/emptyTrash?X-Plex-Token=${PLEX_TOKEN}" > /dev/null
done

echo "Done. Dummy files removed and Plex libraries cleaned."
