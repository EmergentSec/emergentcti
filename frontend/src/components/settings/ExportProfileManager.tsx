import { useState } from 'react'
import { Copy, DownloadSimple } from '@phosphor-icons/react'
import {
  useExportProfiles,
  useExportProfilePreview,
  useCreateExportProfile,
  useUpdateExportProfile,
  useDeleteExportProfile,
} from '@/hooks/useExportProfiles'
import { useFeeds } from '@/hooks/useFeeds'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { exportProfileDownloadPath, exportProfileDownloadUrl } from '@/api/exportProfiles'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Dialog } from '@/components/ui/Dialog'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { apiErrorMessage, apiErrorStatus } from '@/lib/apiError'
import {
  PROFILE_DESCRIPTION_MAX_LENGTH,
  PROFILE_NAME_MAX_LENGTH,
  MAX_EXPORT_AGE_DAYS,
  validateExportProfile,
  type ProfileFormErrors,
} from '@/lib/policyValidation'
import { cn, typeLabels } from '@/lib/utils'
import type { ExportProfile, ExportProfileFormat } from '@/types/exportProfile'
import type { Feed } from '@/types/feed'
import type { ObservableType } from '@/types/observable'

const DEFAULT_CONFIDENCE_MIN = '70'

const FORMAT_LABELS: Record<ExportProfileFormat, string> = {
  text: 'Text',
  json: 'JSON',
}

const FORMAT_OPTIONS = [
  { value: 'text', label: 'Text — one value per line' },
  { value: 'json', label: 'JSON' },
]

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  ...Object.entries(typeLabels).map(([value, label]) => ({ value, label })),
]

function feedLabel(feedId: string | null, feeds: Feed[] | undefined): string {
  if (!feedId) return 'All sources'
  return feeds?.find((f) => f.id === feedId)?.name ?? 'Unknown feed'
}

// ── Preview ───────────────────────────────────────────────────────────────────

function ProfilePreview({ profile }: { profile: ExportProfile }) {
  const { data, isLoading, isFetching, error, refetch } = useExportProfilePreview(profile.id)

  return (
    <section
      aria-label={`Preview of ${profile.name}`}
      className="mt-4 rounded-md border border-border bg-surface2 p-4"
    >
      {isLoading ? (
        <div className="flex justify-center py-4">
          <LoadingSpinner />
        </div>
      ) : error || !data ? (
        <p role="alert" className="text-sm text-destructive-foreground">
          {apiErrorMessage(error, 'Failed to load preview')}
        </p>
      ) : (
        <div className="space-y-3">
          <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">Would be exported</dt>
              <dd className="font-mono font-semibold tabular-nums text-foreground">
                {data.count.toLocaleString('en-US')}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Excluded by allowlist</dt>
              <dd className="font-mono font-semibold tabular-nums text-foreground">
                {data.excluded_allowlisted.toLocaleString('en-US')}
              </dd>
            </div>
          </dl>
          {data.sample.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No indicators currently match this profile.
            </p>
          ) : (
            <div>
              <p className="mb-1 text-xs text-muted-foreground">
                {data.count > data.sample.length
                  ? `Sample — first ${data.sample.length} of ${data.count.toLocaleString('en-US')} values`
                  : 'Sample'}
              </p>
              <ul className="max-h-48 overflow-auto rounded border border-border bg-background px-3 py-2 font-mono text-xs text-foreground">
                {data.sample.map((value, idx) => (
                  <li key={`${idx}-${value}`} className="break-all">
                    {value}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      <div className="mt-3 flex justify-end">
        <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? 'Refreshing...' : 'Refresh preview'}
        </Button>
      </div>
    </section>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ExportProfileManager() {
  const { isAdmin } = useAuth()
  const { toast } = useToast()

  const { data: profiles, isLoading, error } = useExportProfiles()
  const { data: feeds } = useFeeds()
  const createProfile = useCreateExportProfile()
  const updateProfile = useUpdateExportProfile()
  const deleteProfile = useDeleteExportProfile()

  // Create / edit dialog state (editTarget === null while creating)
  const [showForm, setShowForm] = useState(false)
  const [editTarget, setEditTarget] = useState<ExportProfile | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [format, setFormat] = useState<ExportProfileFormat>('text')
  const [type, setType] = useState<ObservableType | ''>('')
  const [confidenceMin, setConfidenceMin] = useState(DEFAULT_CONFIDENCE_MIN)
  const [maxAgeDays, setMaxAgeDays] = useState('')
  const [feedId, setFeedId] = useState('')
  const [formErrors, setFormErrors] = useState<ProfileFormErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)

  const [previewId, setPreviewId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ExportProfile | null>(null)

  const isSaving = createProfile.isPending || updateProfile.isPending

  // Keep a saved feed selectable even when the feed list is missing it, so an
  // edit never silently broadens the profile to all sources.
  const feedOptions = [
    { value: '', label: 'All sources' },
    ...(feeds ?? []).map((f) => ({ value: f.id, label: f.name })),
    ...(feedId && !feeds?.some((f) => f.id === feedId)
      ? [{ value: feedId, label: 'Unknown feed' }]
      : []),
  ]

  const openCreate = () => {
    setEditTarget(null)
    setName('')
    setDescription('')
    setFormat('text')
    setType('')
    setConfidenceMin(DEFAULT_CONFIDENCE_MIN)
    setMaxAgeDays('')
    setFeedId('')
    setFormErrors({})
    setSubmitError(null)
    setShowForm(true)
  }

  const openEdit = (profile: ExportProfile) => {
    setEditTarget(profile)
    setName(profile.name)
    setDescription(profile.description ?? '')
    setFormat(profile.format)
    setType(profile.type ?? '')
    setConfidenceMin(String(profile.confidence_min))
    setMaxAgeDays(profile.max_age_days == null ? '' : String(profile.max_age_days))
    setFeedId(profile.feed_id ?? '')
    setFormErrors({})
    setSubmitError(null)
    setShowForm(true)
  }

  const closeForm = () => {
    setShowForm(false)
    setEditTarget(null)
    setFormErrors({})
    setSubmitError(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitError(null)
    const errors = validateExportProfile({ name, description, confidenceMin, maxAgeDays })
    setFormErrors(errors)
    if (Object.keys(errors).length > 0) return

    const data = {
      name: name.trim(),
      description: description.trim() || null,
      format,
      type: type || null,
      confidence_min: Number(confidenceMin),
      max_age_days: maxAgeDays.trim() ? Number(maxAgeDays) : null,
      feed_id: feedId || null,
    }
    const callbacks = {
      onSuccess: () => {
        toast(editTarget ? 'Export profile updated' : 'Export profile created', 'success')
        closeForm()
      },
      onError: (err: unknown) => {
        const message =
          apiErrorStatus(err) === 409
            ? 'An export profile with this name already exists.'
            : apiErrorMessage(err, 'Failed to save export profile')
        setSubmitError(message)
        toast(message, 'error')
      },
    }

    if (editTarget) {
      updateProfile.mutate({ id: editTarget.id, data }, callbacks)
    } else {
      createProfile.mutate(data, callbacks)
    }
  }

  const handleDelete = () => {
    if (!deleteTarget) return
    deleteProfile.mutate(deleteTarget.id, {
      onSuccess: () => {
        toast(`${deleteTarget.name} deleted`, 'success')
        if (previewId === deleteTarget.id) setPreviewId(null)
        setDeleteTarget(null)
      },
      onError: (err) => {
        toast(apiErrorMessage(err, 'Failed to delete export profile'), 'error')
        setDeleteTarget(null)
      },
    })
  }

  const handleCopyUrl = async (profile: ExportProfile) => {
    try {
      await navigator.clipboard.writeText(exportProfileDownloadUrl(profile.id))
      toast('Download URL copied to clipboard', 'success')
    } catch {
      toast('Failed to copy to clipboard', 'error')
    }
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Export profiles</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Saved export filters with a stable download URL, shared by everyone on this instance
          </p>
        </div>
        {isAdmin && (
          <Button variant="brand" onClick={openCreate}>
            New profile
          </Button>
        )}
      </div>

      <Card className="space-y-2 p-5 text-sm text-muted-foreground">
        <p>
          Each download evaluates the saved filters against current data. Allowlisted observables
          are always excluded. Text and JSON downloads both contain every eligible indicator with
          no row cap, so the preview count matches the download. Text formats omit values
          containing control characters to keep one indicator per line.
        </p>
        <p>
          Download URLs contain no credentials. Firewalls and scripts authenticate with the{' '}
          <code className="rounded bg-surface2 px-1 py-0.5 font-mono text-xs">X-API-Key</code>{' '}
          header; in the browser your signed-in session is used.
        </p>
      </Card>

      {!isAdmin && (
        <p className="text-sm text-muted-foreground">
          Only administrators can create, edit or delete export profiles.
        </p>
      )}

      {/* Profiles */}
      {isLoading ? (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      ) : error ? (
        <p role="alert" className="text-sm text-destructive-foreground">
          Failed to load export profiles
        </p>
      ) : !profiles || profiles.length === 0 ? (
        <p className="text-sm text-muted-foreground">No export profiles yet.</p>
      ) : (
        <ul className="space-y-3">
          {profiles.map((profile) => {
            const previewOpen = previewId === profile.id
            return (
              <li key={profile.id}>
                <Card className="p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-medium text-foreground">{profile.name}</h3>
                      {profile.description && (
                        <p className="mt-0.5 text-sm text-muted-foreground">
                          {profile.description}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-expanded={previewOpen}
                        aria-label={`${previewOpen ? 'Hide preview of' : 'Preview'} ${profile.name}`}
                        onClick={() => setPreviewId(previewOpen ? null : profile.id)}
                      >
                        {previewOpen ? 'Hide preview' : 'Preview'}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Copy download URL for ${profile.name}`}
                        onClick={() => handleCopyUrl(profile)}
                      >
                        <Copy size={14} className="mr-1.5" />
                        Copy URL
                      </Button>
                      <a
                        href={exportProfileDownloadPath(profile.id)}
                        download
                        aria-label={`Download ${profile.name}`}
                        className={cn(
                          'inline-flex items-center justify-center font-medium transition-colors',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                          'focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                          'hover:bg-accent hover:text-accent-foreground',
                          'h-8 rounded-sm px-3 text-xs',
                        )}
                      >
                        <DownloadSimple size={14} className="mr-1.5" />
                        Download
                      </a>
                      {isAdmin && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Edit ${profile.name}`}
                            onClick={() => openEdit(profile)}
                          >
                            Edit
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Delete ${profile.name}`}
                            onClick={() => setDeleteTarget(profile)}
                            className="text-destructive hover:text-destructive"
                          >
                            Delete
                          </Button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Saved filters */}
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <Badge variant="secondary">{FORMAT_LABELS[profile.format] ?? profile.format}</Badge>
                    <Badge variant="outline">
                      {profile.type ? (typeLabels[profile.type] ?? profile.type) : 'All types'}
                    </Badge>
                    <Badge variant="outline">Confidence ≥ {profile.confidence_min}</Badge>
                    <Badge variant="outline">
                      {profile.max_age_days == null
                        ? 'Any age'
                        : `Seen in last ${profile.max_age_days}d`}
                    </Badge>
                    <Badge variant="outline">{feedLabel(profile.feed_id, feeds)}</Badge>
                  </div>

                  <code className="mt-3 block break-all rounded bg-surface2 px-2 py-1.5 font-mono text-xs text-muted-foreground">
                    {exportProfileDownloadUrl(profile.id)}
                  </code>

                  {previewOpen && <ProfilePreview profile={profile} />}
                </Card>
              </li>
            )
          })}
        </ul>
      )}

      {/* Create / edit dialog */}
      <Dialog
        open={showForm}
        onClose={closeForm}
        title={editTarget ? 'Edit export profile' : 'New export profile'}
      >
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <Input
            id="profile-name"
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Firewall IP blocklist"
            maxLength={PROFILE_NAME_MAX_LENGTH}
            error={formErrors.name}
            aria-invalid={formErrors.name ? true : undefined}
            autoFocus
          />
          <Input
            id="profile-description"
            label="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={PROFILE_DESCRIPTION_MAX_LENGTH}
            error={formErrors.description}
            aria-invalid={formErrors.description ? true : undefined}
          />
          <div className="grid grid-cols-2 gap-4">
            <Select
              id="profile-format"
              label="Format"
              value={format}
              onChange={(e) => setFormat(e.target.value as ExportProfileFormat)}
              options={FORMAT_OPTIONS}
            />
            <Select
              id="profile-type"
              label="Observable type"
              value={type}
              onChange={(e) => setType(e.target.value as ObservableType | '')}
              options={TYPE_OPTIONS}
            />
            <Input
              id="profile-confidence-min"
              label="Minimum confidence"
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              step={1}
              value={confidenceMin}
              onChange={(e) => setConfidenceMin(e.target.value)}
              error={formErrors.confidenceMin}
              aria-invalid={formErrors.confidenceMin ? true : undefined}
            />
            <Input
              id="profile-max-age"
              label="Maximum age in days (optional)"
              type="number"
              inputMode="numeric"
              min={1}
              max={MAX_EXPORT_AGE_DAYS}
              step={1}
              value={maxAgeDays}
              onChange={(e) => setMaxAgeDays(e.target.value)}
              placeholder="Any age"
              error={formErrors.maxAgeDays}
              aria-invalid={formErrors.maxAgeDays ? true : undefined}
            />
          </div>
          <Select
            id="profile-feed"
            label="Source"
            value={feedId}
            onChange={(e) => setFeedId(e.target.value)}
            options={feedOptions}
          />
          {submitError && (
            <p role="alert" className="text-sm text-destructive">
              {submitError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={closeForm}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? 'Saving...' : editTarget ? 'Save changes' : 'Create profile'}
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete export profile"
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Delete <span className="font-medium text-foreground">{deleteTarget?.name}</span>? Its
            download URL will stop working for any firewall or script that uses it.
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteProfile.isPending}>
              {deleteProfile.isPending ? 'Deleting...' : 'Delete profile'}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
