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
- The backend binds to `127.0.0.1` only (`uvicorn.run(host="127.0.0.1", ...)`
  in `auralis-web/backend/main.py`). It is not reachable from any other host on
  the network.
- The frontend and backend are bundled and launched together on the same
  machine (`launch-auralis-web.py`, Electron `desktop/`). The packaged renderer
  loads from the backend's own origin, `http://127.0.0.1:8765` (`APP_ORIGIN` in
  `desktop/url-safety.js`); no file-scheme origin is involved.

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

Authentication is absent, but these boundaries constrain who can reach the API.
Each names the code that enforces it; line numbers are deliberately omitted
because they drift.

1. **Loopback bind**: the socket listens on `127.0.0.1` only, so no LAN peer or
   remote host can connect (`main.py`, `uvicorn.run`).

2. **No proxy headers**: `uvicorn.run(proxy_headers=False)` (#6168). With no
   reverse proxy, `X-Forwarded-For` must not rewrite the client address that the
   loopback checks below read.

3. **Host header allowlist**: `LoggingTrustedHostMiddleware` with
   `config/middleware/hosts.py:trusted_hosts()` (#4353). A page on another
   domain rebound to 127.0.0.1 (DNS rebinding) arrives with its own `Host` and
   is refused before any handler runs.

4. **WebSocket Origin matrix**: a browser WS upgrade must present an `Origin`
   from `websocket/connection_manager.py:build_ws_origins()`, which is
   `config/origins.py:origin_matrix(("http", "https", "ws", "wss"))`: the
   loopback hosts (`localhost`, `127.0.0.1`) times the allowed ports (the
   backend port; the Vite dev ports only in dev mode, #4350) times those
   schemes. The file scheme is not on it (#5066). A cross-origin web page cannot
   hijack the socket (#2413).

5. **Empty-Origin loopback gate**: a non-browser client sends no `Origin`. A WS
   connection without one is accepted only from a loopback peer
   (`connection_manager.LOOPBACK_HOSTS`: `127.0.0.1`, `::1`, `localhost`,
   #3845), so a non-loopback client cannot skip the Origin check by omitting
   the header. REST state-changing requests get the same rule (item 6).

6. **REST origin check**: `config/middleware/origin_check.py:OriginCheckMiddleware`
   (#4893). A `POST`/`PUT`/`DELETE`/`PATCH` under `/api` needs an `Origin` from
   the CORS allowlist, or no `Origin` and a loopback peer. A `GET`/`HEAD` under
   `/api` is refused when the browser marks it `Sec-Fetch-Site: cross-site` or
   `same-site` and neither its `Origin` nor its `Referer` is trusted (#6158), so
   a hostile page cannot fire the few unsafe GETs blind with `<img src>`.

7. **CORS**: an explicit allowlist (`cors_allowed_origins()`, the same loopback
   matrix), never a wildcard with credentials (#2224).

8. **Electron shell**: the renderer runs with `contextIsolation`, `sandbox` and
   no `nodeIntegration`; every IPC handler refuses a sender that is not the
   app's own top-level document (`isTrustedIpcSender`, #6174); in-window
   navigation is limited to the app origin (`isAllowedAppNavigation`), external
   links go through `isSafeExternalUrl`, and web permission requests are denied
   (`setPermissionRequestHandler` in `desktop/main.js`).

Path inputs are validated independently of the caller
(`auralis-web/backend/security/path_security.py`).

## Residual risk

### Accepted: a process running as the same user

These boundaries do **not** stop a **co-resident local process running under
the user's own account** (malware or a compromised program). It can open
`ws://127.0.0.1:8765/ws` with no `Origin` (allowed as loopback) and issue
commands (`play_enhanced`, `stop`, `seek`, scan, trigger processing), or call
REST directly.

This is accepted because such a process **already holds the user's filesystem
privileges**: it can read and write the music library, the SQLite DB
(`~/.auralis/library.db`) and the user's files directly. Driving the Auralis
API grants it nothing it could not already do.

### Not accepted: another OS account on the same machine

Loopback is shared by every account on the machine, so a process run by
**another local user** passes the same boundaries (loopback peer, no `Origin`).
The argument above does not hold for it: that user cannot read `~/.auralis`
(owner-only, #2577, #4347, #4824) or, typically, this user's music, yet through the API
it can list the library, read metadata and artwork, start scans of folders this
user can read, and control playback. This is an **open risk, tracked in
#6520**, not an accepted one. The capability token below would close it.

What is **not** exposed to anyone off the machine:

- No LAN peer can reach the API (loopback bind).
- No remote or cross-origin web page can drive the WS or the REST API (Origin
  matrix, REST origin check, Host allowlist).

## Optional hardening (not implemented)

If defense against co-resident processes is ever desired, the Electron main
process could mint a **per-launch loopback capability token**, pass it to the
renderer at startup, and require it on WS connect and REST mutations. A local
process without the token would be rejected. This is a design decision with a
usability/complexity cost and is **not currently adopted**: the boundaries above
are considered sufficient against a same-user process and anything off the
machine. It is the candidate fix for the cross-account risk (#6520).

## Related

- #3905 — directory-trust facet (`validate_user_chosen_directory` trusts any
  readable dir); tracked separately.
- #2413, #3845, #5066 — WebSocket Origin hardening (implemented).
- #4893, #6158 — REST origin check and its Sec-Fetch-Site GET gate.
- #6520 — the cross-OS-account actor (open).
- [WEBSOCKET_SECURITY_FIX_2156.md](WEBSOCKET_SECURITY_FIX_2156.md) — related WS
  security fix.
