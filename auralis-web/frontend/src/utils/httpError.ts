/**
 * HTTP error-body parsing shared by every fetch layer in the app.
 *
 * The backend raises `HTTPException(status_code=..., detail="...")` (see
 * `auralis-web/backend/routers/errors.py`), so the only useful part of a non-2xx
 * response — "Track 123 not found", "Invalid confirmation header", a 422 field
 * listing — lives in the JSON body. A layer that throws off `response.status` /
 * `response.statusText` alone discards it irrecoverably, since the body can only
 * be read once and only before the error propagates (#4831).
 *
 * Both `utils/apiRequest.ts` and `hooks/api/useRestAPI.ts` had (or lacked) their
 * own copy of this logic; this module is the single implementation.
 */

/** Outcome of reading a non-2xx response body. */
export interface HttpErrorBody {
  /** Detail message extracted from the body, if the body carried one. */
  detail?: string;
  /**
   * Whether the body parsed as JSON at all. Callers distinguish "JSON without a
   * `detail` key" from "not JSON" because they use different fallback messages.
   */
  parsed: boolean;
}

/**
 * Render FastAPI's 422 `detail` array (a list of
 * `{loc: [...], msg: "...", type: "..."}` entries) as one readable line.
 */
function formatValidationDetail(entries: unknown[]): string | undefined {
  const parts = entries
    .map((entry) => {
      if (typeof entry === 'string') return entry;
      if (typeof entry !== 'object' || entry === null) return undefined;
      const { loc, msg } = entry as { loc?: unknown; msg?: unknown };
      if (typeof msg !== 'string') return undefined;
      // Drop the leading "body"/"query" scope element — it names the request
      // part, not the field the user has to fix.
      const field = Array.isArray(loc) ? loc.slice(1).join('.') || loc.join('.') : '';
      return field ? `${field}: ${msg}` : msg;
    })
    .filter((part): part is string => Boolean(part));

  return parts.length > 0 ? parts.join('; ') : undefined;
}

/** Coerce whatever sits under `detail` / `message` into a display string. */
function coerceDetail(value: unknown): string | undefined {
  if (typeof value === 'string') return value || undefined;
  if (Array.isArray(value)) return formatValidationDetail(value);
  if (typeof value === 'object' && value !== null) {
    const { msg, message } = value as { msg?: unknown; message?: unknown };
    if (typeof msg === 'string') return msg;
    if (typeof message === 'string') return message;
  }
  return undefined;
}

/**
 * Read a failed `Response` and pull out the backend's error detail.
 *
 * Never throws: a non-JSON body, an already-consumed body or a `detail`-less
 * payload all resolve to `{ parsed, detail: undefined }` so callers can fall
 * back to their own generic message.
 */
export async function readHttpErrorBody(response: Response): Promise<HttpErrorBody> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { parsed: false };
  }

  if (typeof body !== 'object' || body === null) {
    return { parsed: true };
  }

  const { detail, message } = body as { detail?: unknown; message?: unknown };
  return { parsed: true, detail: coerceDetail(detail) ?? coerceDetail(message) };
}

/** An `Error` that carries the HTTP status it was built from. */
export interface HttpStatusError extends Error {
  status: number;
  detail?: string;
}

/**
 * Build the `Error` to throw for a non-2xx response, preferring the backend's
 * `detail` over the generic `HTTP {status}: {statusText}` string.
 *
 * The status is attached as a property rather than encoded in the message so
 * that `ApiErrorHandler.parse()` can recover it without the message having to
 * keep its `HTTP nnn:` prefix.
 */
export async function httpErrorFromResponse(response: Response): Promise<HttpStatusError> {
  const { detail } = await readHttpErrorBody(response);
  const error = new Error(detail ?? `HTTP ${response.status}: ${response.statusText}`);
  return Object.assign(error, { status: response.status, detail });
}
