#!/bin/sh
set -e

# Ensure numpy stays on 1.x (needed by chromadb 0.4.x) and install matching hnswlib wheel
pip install --no-cache-dir --force-reinstall "numpy<2" "chroma-hnswlib==0.7.3"

export IS_PERSISTENT=${IS_PERSISTENT:-1}
export CHROMA_SERVER_NOFILE=${CHROMA_SERVER_NOFILE:-65535}

exec uvicorn chromadb.app:app --workers 1 --host 0.0.0.0 --port 8000 --proxy-headers --log-config chromadb/log_config.yml --timeout-keep-alive 30
