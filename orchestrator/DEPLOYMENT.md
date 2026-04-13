# Orchestrator deployment hardening notes

## Caddy public-path policy

Recommended policy for the public reverse proxy:

- Allow unauthenticated access only to:
  - `/healthz`
  - `/github/webhook`
  - `/openai/webhook`
- Keep `/runs` behind `basic_auth`
- Return `404` for all other paths before proxying to FastAPI

Example Caddy snippet:

```caddy
orchestrator.example.com {
	@healthz path /healthz
	@github path /github/webhook
	@openai path /openai/webhook
	@runs path /runs

	handle @healthz {
		reverse_proxy 127.0.0.1:8000
	}

	handle @github {
		reverse_proxy 127.0.0.1:8000
	}

	handle @openai {
		reverse_proxy 127.0.0.1:8000
	}

	handle @runs {
		basic_auth {
			dm JDJhJDE0JHdoZXJlLWEtcmVhbC1iY3J5cHQtaGFzaC1nb2Vz
		}
		reverse_proxy 127.0.0.1:8000
	}

	respond 404
}
```

## Manual live-ops follow-up

- Rotate the live `/runs` basic-auth password in the real Caddy config (the previous test credential was exposed).
- Apply the path-filtering policy above on the proxy VM and reload Caddy.
