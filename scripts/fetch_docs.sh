#!/usr/bin/env bash
# Fetch the two HP source documents and pin their SHA-256s.
# Run once from the repo root: ./scripts/fetch_docs.sh
set -euo pipefail

DOCS_DIR="$(dirname "$0")/../docs"

# Official HP document URLs — verify/update before first run:
ENVY_URL="https://h10032.www1.hp.com/ctg/Manual/c06584210.pdf"   # HP ENVY 6000 AiO User Guide
OMEN_URL="https://kaas.hpcloud.hp.com/pdf-public/pdf_10301542_en-US-1.pdf"   # OMEN 17.3" Maintenance & Service Guide

curl -fL "$ENVY_URL" -o "$DOCS_DIR/hp-envy-6000-user-guide.pdf"
curl -fL "$OMEN_URL" -o "$DOCS_DIR/omen-17-maintenance-service-guide.pdf"

cd "$DOCS_DIR"
sha256sum hp-envy-6000-user-guide.pdf omen-17-maintenance-service-guide.pdf > checksums.txt
echo "Pinned:"
cat checksums.txt
