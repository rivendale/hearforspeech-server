# Self-Hosting Guide

Clinics that do not want cloud processing can run this backend privately.

## Docker

```bash
docker build -t hearforspeech-server .
docker run --rm -p 8000:8000 \
  -e HFS_ALLOWED_ORIGINS=https://hearforspeech.com \
  -e HFS_API_KEY=change-me \
  hearforspeech-server
```

## Reverse Proxy

Terminate TLS with a reverse proxy such as Caddy, Nginx, Traefik, Cloudflare Tunnel, or a clinic-managed load balancer.

Example public URL:

```text
https://api.hearforspeech.com
```

## Operational Responsibilities

Deployers are responsible for:

- TLS
- access controls
- API keys or authentication
- logging policy
- temporary-file cleanup
- backup/retention policy
- HIPAA/FERPA compliance review
- BAAs/DPAs when applicable

## Recommended Defaults

- Keep retention temporary.
- Avoid raw-audio logs.
- Restrict CORS to approved app origins.
- Set `HFS_API_KEY`.
- Monitor CPU, memory, upload size, and error rates.
