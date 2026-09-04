/**
 * A non-numeric port typed into these fields doesn't error -- Number("abc")
 * is NaN, and JSON.stringify(NaN) serializes to `null`, which the backend
 * can't tell apart from "left blank". The typed value is silently dropped
 * before it ever reaches validation. This must be caught here, client-side,
 * at the point of entry.
 */
export function isValidPortText(raw: string): boolean {
  const trimmed = raw.trim();
  if (!trimmed) return true; // blank is valid -- means "no change" / not provided
  const n = Number(trimmed);
  return Number.isInteger(n) && n >= 1 && n <= 65535;
}

export const INVALID_PORT_MESSAGE = "Not a valid port (1-65535) -- as typed, this value will be ignored.";
