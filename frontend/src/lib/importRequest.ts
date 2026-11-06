import { isAxiosError } from 'axios'
import { apiErrorMessage, importValidationErrorDetail } from '@/lib/apiError'
import type { ImportResult } from '@/types/reportIocExtraction'

/** POST /reports/{id}/import. Bounds a stalled proxy so the dialog can recover. */
export const IMPORT_REQUEST_TIMEOUT_MS = 60_000

/**
 * Close stays locked this long after import starts. A fast result still lands
 * in the dialog; a hang can be dismissed once the lock lifts.
 */
export const IMPORT_CLOSE_UNLOCK_MS = 8_000

export const IMPORT_TIMEOUT_MESSAGE =
  'The import request timed out. It may still have been saved. The import is transactional and idempotent, so retrying is safe.'

export const IMPORT_STILL_RUNNING_MESSAGE =
  'Import is still running. You will be notified when it finishes. If it times out, it may already have been saved, and retrying is safe.'

export function importPendingLockedMessage(): string {
  const seconds = IMPORT_CLOSE_UNLOCK_MS / 1000
  return `Import in progress. Close unlocks after ${seconds} seconds if the request is still running.`
}

export const IMPORT_PENDING_UNLOCKED_MESSAGE =
  'This import is still running. You can close this dialog and you will still be notified of the result.'

export function importSuccessMessage(
  result: Pick<ImportResult, 'created' | 'attributed_existing' | 'already_attributed'>,
): string {
  return `Import complete: ${result.created} created, ${result.attributed_existing} attributed, ${result.already_attributed} already linked`
}

/** Axios timeout (ECONNABORTED, "timeout of Nms exceeded"), not a user cancel. */
export function isImportRequestTimeout(err: unknown): boolean {
  return isAxiosError(err) && err.code === 'ECONNABORTED' && /timeout/i.test(err.message)
}

export function importFailureMessage(err: unknown): string {
  if (isImportRequestTimeout(err)) return IMPORT_TIMEOUT_MESSAGE
  const parsed = importValidationErrorDetail(err)
  if (parsed) return parsed.messages.join('\n')
  return apiErrorMessage(err, 'Import failed')
}

/**
 * True while IndicatorImportReview is showing failures inline.
 * Cleared synchronously on dismiss so a later timeout still toasts.
 */
let showImportFailureInline = false

export function setImportFailureInline(show: boolean): void {
  showImportFailureInline = show
}

export function importFailureShownInline(): boolean {
  return showImportFailureInline
}
