#!/bin/sh
set -e

# ChromaDB latest version doesn't need numpy/hnswlib fixes
# The image already has the correct dependencies installed

export IS_PERSISTENT=${IS_PERSISTENT:-1}
export CHROMA_SERVER_NOFILE=${CHROMA_SERVER_NOFILE:-65535}

# Use the default ChromaDB entrypoint command
exec uvicorn chromadb.app:app --workers 1 --host 0.0.0.0 --port 8000 --proxy-headers --log-config chromadb/log_config.yml --timeout-keep-alive 30
