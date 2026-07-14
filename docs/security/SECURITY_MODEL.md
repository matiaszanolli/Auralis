# Auralis Security Model

**Status**: Authoritative threat model for the local REST/WebSocket API.
**Scope**: `auralis-web/backend/` (FastAPI REST + WebSocket at `:8765`).
**Tracks**: #4385 (no API authentication — defense-in-depth).

## TL;DR

Auralis is a **single-user desktop application** (Electron shell + FastAPI
backend + Rust DSP), all running on `localhost`. The backend binds to the
loopback interface only and intentionally ships **no caller authentication**.
This is a deliberate design decision, not a defect. The sections below record
the assumption, the boundaries that make it safe, and the residual risk it
accepts.

## Deployment shape

- One user, one machine. There is no server deployment, no multi-tenant mode,
  no LAN/remote access scenario. See `docs/development` and the project memory
  ("Desktop-only distribution").
- The backend binds to `127.0.0.1` only
  ([main.py:210](../../auralis-web/backend/main.py#L210) — `host="127.0.0.1"`).
  It is not reachable from any other host on the network.
- The frontend and backend are bundled and launched together on the same
  machine (`launch-auralis-web.py`, Electron `desktop/`).

## Authentication posture

There is **no authentication** on REST or WebSocket. Any process on the local
machine, and any browser page whose `Origin` is in the loopback allowlist, can
invoke every endpoint (control playback, scan the library, edit metadata,
launch processing).

```
$ grep -rn "HTTPBearer|OAuth2|get_current_user|Security(" \
    auralis-web/backend/routers/ auralis-web/backend/main.py
  → (no matches — intentional)
```

## Boundaries that bound the risk

Authentication is absent, but three boundaries constrain who can reach the API:

1. **Loopback bind** — the socket listens on `127.0.0.1` only, so no LAN peer
   or remote host can connect. ([main.py:210](../../auralis-web/backend/main.py#L210))

2. **WebSocket Origin allowlist** — browser-originated WS upgrades must present
   an `Origin` in `ALLOWED_WS_ORIGINS` (loopback dev ports + `file://` for the
   Electron renderer). A cross-origin web page cannot hijack the socket.
   ([config/globals.py:30-38](../../auralis-web/backend/config/globals.py#L30-L38),
   `ConnectionManager.connect`, fixes #2413.)

3. **Empty-Origin loopback gate** — a non-browser process sends no `Origin`
   header. Such connections are accepted **only** from loopback hosts
   (`127.0.0.1`, `::1`, `localhost`), so a non-loopback client cannot bypass
   the Origin check by simply omitting the header.
   ([config/globals.py:43](../../auralis-web/backend/config/globals.py#L43),
   fixes #3845.)

## Residual risk (accepted)

The one actor these boundaries do **not** stop is a **co-resident local
process** — malware or a compromised process already running under the user's
account. It can open `ws://127.0.0.1:8765/ws` with no `Origin` (allowed as
loopback) and issue commands (`play_enhanced`, `stop`, `seek`, scan, trigger
processing), or call REST directly.

This is accepted because such a process **already holds the user's filesystem
privileges** — it can read/write the music library, the SQLite DB
(`~/.auralis/library.db`), and user files directly. Driving the Auralis API
grants it nothing it could not already do. The blast radius is marginal.

What is **not** exposed:

- No LAN peer can reach the API (loopback bind).
- No remote/cross-origin web page can drive the WS (Origin allowlist).
- Path inputs are still validated independently
  (`auralis-web/backend/security/path_security.py`) regardless of caller.

## Optional hardening (not implemented)

If defense against co-resident processes is ever desired, the Electron main
process could mint a **per-launch loopback capability token**, pass it to the
renderer at startup, and require it on WS connect and REST mutations. A local
process without the token would be rejected. This is a design decision with a
usability/complexity cost and is **not currently adopted** — the loopback bind
plus Origin gate is considered sufficient for the single-user desktop model.

## Related

- #3905 — directory-trust facet (`validate_user_chosen_directory` trusts any
  readable dir); tracked separately.
- #2413, #3845 — WebSocket Origin hardening (implemented).
- [WEBSOCKET_SECURITY_FIX_2156.md](WEBSOCKET_SECURITY_FIX_2156.md) — related WS
  security fix.
