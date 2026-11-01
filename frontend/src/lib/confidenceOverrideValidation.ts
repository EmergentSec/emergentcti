const RANGE_MESSAGE = 'Enter a whole number from 0 to 100'

/** Validates admin override input: whole numbers 0–100 only. */
export function validateConfidenceOverrideInput(
  raw: string,
): { ok: true; value: number } | { ok: false; message: string } {
  const trimmed = raw.trim()
  if (trimmed === '') return { ok: false, message: RANGE_MESSAGE }
  if (!/^\d+$/.test(trimmed)) return { ok: false, message: RANGE_MESSAGE }
  const value = Number(trimmed)
  if (value < 0 || value > 100) return { ok: false, message: RANGE_MESSAGE }
  return { ok: true, value }
}

export const CONFIDENCE_OVERRIDE_HELP =
  "Pins this observable's confidence. Feed updates and decay won't change it until you clear the override. Lower values can remove it from blocklist exports."
