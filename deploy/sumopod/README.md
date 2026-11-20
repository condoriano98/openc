# OpenC on Sumopod

The canonical application is https://openc.43.173.40.109.sslip.io.
Caddy terminates HTTPS, compresses responses and caches immutable frontend assets.
The backend serves the frontend at /app/build. The frontend and API share an origin.

## State
The Docker volume openc_data holds the database, uploads and persistent session secret.
Do not remove it. A pre-migration SQLite backup is stored as
/app/backend/data/pre-frontend-migration.db in that volume.

## Frontend releases
Build the public frontend on a build host with sufficient RAM (the public Vercel
project now serves only a redirect, so use a separate build host for updates):

    CYPRESS_INSTALL_BINARY=0 npm ci --legacy-peer-deps --onnxruntime-node-install-cuda=skip
    npm run crypto:verify
    npm run pyodide:fetch
    VERCEL=1 node --max-old-space-size=6144 node_modules/vite/bin/vite.js build
    node scripts/package-frontend.mjs

Serve the build directory over HTTPS without the repository's Vercel redirect rules.
Leave VITE_WEBUI_SOCKET_URL unset for a same-origin deployment. Transfer from that URL with:

    python3 deploy/sumopod/install-frontend.py https://BUILD_HOST

The installer validates part lengths and SHA-256 hashes before switching the frontend
symlink. Releases remain under frontend-releases. Recreate the backend after changing
the symlink; Docker resolves bind-mount symlinks when creating containers:

    sudo docker compose -f deploy/sumopod/compose.yaml -f deploy/sumopod/https.yaml up -d --force-recreate backend

To roll back, repoint deploy/sumopod/frontend to the previous release and recreate the backend.
This does not change the database or uploads.

Vercel's public application link redirects to the canonical Sumopod application.
Build hosts must keep their transfer files available until installation completes.
The transfer package contains public frontend output only.
