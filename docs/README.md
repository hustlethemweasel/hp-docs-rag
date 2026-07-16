# Source documents

This directory holds the two HP PDFs the vector database is built from (SPEC §7):

1. HP ENVY 6000 All-in-One series User Guide
2. Maintenance and Service Guide — OMEN 17.3 inch Gaming Laptop PC

Run `./scripts/fetch_docs.sh` once to download them and pin their SHA-256s in
`checksums.txt`. The ingest job verifies these checksums at startup and fails
fast on any mismatch. **Verify the URLs in the script against the links in the
assignment before running** — HP occasionally moves documents.
