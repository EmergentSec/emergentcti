import { useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  DownloadSimple,
  LinkSimple,
  Paperclip,
  PencilSimple,
  Robot,
  Trash,
  UploadSimple,
  X,
} from '@phosphor-icons/react'
import {
  useReport,
  useUpdateReport,
  useDeleteReport,
  useUploadReportAttachment,
  useRemoveReportAttachment,
  useLinkReportObservable,
  useUnlinkReportObservable,
} from '@/hooks/useReports'
import { useObservables } from '@/hooks/useObservables'
import { downloadReportAttachment } from '@/api/reports'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { ReportContent, formatProvenance, isSafeHttpUrl } from '@/components/reports/ReportContent'
import { ReportForm } from '@/components/reports/ReportForm'
import { formatDate, typeLabels } from '@/lib/utils'
import { apiErrorMessage } from '@/lib/apiError'
import type { ReportCreate } from '@/types/report'

const MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const { toast } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: report, isLoading, error } = useReport(id ?? null)
  const updateReport = useUpdateReport()
  const deleteReport = useDeleteReport()
  const uploadAttachment = useUploadReportAttachment()
  const removeAttachment = useRemoveReportAttachment()
  const linkObservable = useLinkReportObservable()
  const unlinkObservable = useUnlinkReportObservable()

  const [showEdit, setShowEdit] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [showRemoveAttachment, setShowRemoveAttachment] = useState(false)
  const [linkQuery, setLinkQuery] = useState('')
  const [showLinkSearch, setShowLinkSearch] = useState(false)

  const linkSearchActive = showLinkSearch && linkQuery.trim().length > 0
  const { data: searchResults } = useObservables(
    { q: linkQuery.trim(), page: 1, size: 5 },
    { enabled: linkSearchActive },
  )

  const handleDownload = async () => {
    if (!report) return
    try {
      const blob = await downloadReportAttachment(report.id)
      const filename = report.attachment?.original_filename ?? 'attachment'
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.rel = 'noopener noreferrer'
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 0)
    } catch (err) {
      toast(apiErrorMessage(err, 'Failed to download attachment'), 'error')
    }
  }

  const handleUpload = (file: File | undefined) => {
    if (!report || !file) return
    if (file.size > MAX_ATTACHMENT_BYTES) {
      toast('File must be 20 MiB or smaller', 'error')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }
    uploadAttachment.mutate(
      { id: report.id, file },
      {
        onSuccess: () => toast('Attachment uploaded', 'success'),
        onError: (err) => toast(apiErrorMessage(err, 'Upload failed'), 'error'),
      },
    )
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleRemoveAttachment = () => {
    if (!report) return
    removeAttachment.mutate(report.id, {
      onSuccess: () => {
        toast('Attachment removed', 'success')
        setShowRemoveAttachment(false)
      },
      onError: (err) =>
        toast(apiErrorMessage(err, 'Failed to remove attachment'), 'error'),
    })
  }

  const handleEdit = (payload: ReportCreate) => {
    if (!report) return
    updateReport.mutate(
      { id: report.id, data: payload },
      {
        onSuccess: () => {
          toast('Report updated', 'success')
          setShowEdit(false)
        },
        onError: (err) => toast(apiErrorMessage(err, 'Failed to update report'), 'error'),
      },
    )
  }

  const handleDelete = () => {
    if (!report) return
    deleteReport.mutate(report.id, {
      onSuccess: () => {
        toast('Report deleted', 'success')
        navigate('/reports')
      },
      onError: (err) => toast(apiErrorMessage(err, 'Failed to delete report'), 'error'),
    })
  }

  const handleLink = (observableId: string) => {
    if (!report) return
    linkObservable.mutate(
      { reportId: report.id, observableId },
      {
        onSuccess: () => {
          toast('Observable linked', 'success')
          setLinkQuery('')
          setShowLinkSearch(false)
        },
        onError: (err) => toast(apiErrorMessage(err, 'Failed to link observable'), 'error'),
      },
    )
  }

  const handleUnlink = (observableId: string) => {
    if (!report) return
    unlinkObservable.mutate(
      { reportId: report.id, observableId },
      {
        onSuccess: () => toast('Observable unlinked', 'success'),
        onError: (err) => toast(apiErrorMessage(err, 'Failed to unlink observable'), 'error'),
      },
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !report) {
    return (
      <EmptyState
        className="[&_h3]:text-destructive"
        title="Failed to load report"
        description={error instanceof Error ? error.message : 'Report not found'}
      />
    )
  }

  const safeSourceUrl = isSafeHttpUrl(report.source_url) ? report.source_url : null

  return (
    <div className="space-y-4">
      <Link
        to="/reports"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft size={14} />
        Reports
      </Link>

      <Card>
        <CardContent className="space-y-4 p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 flex-1">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="capitalize">
                  {report.origin}
                </Badge>
                {report.is_ai_generated && (
                  <Badge variant="secondary">
                    <Robot size={12} aria-hidden="true" />
                    AI-generated
                  </Badge>
                )}
              </div>
              <h2 className="text-xl font-semibold leading-tight">{report.title}</h2>
              {report.summary && (
                <p className="mt-2 text-sm text-muted-foreground">{report.summary}</p>
              )}
            </div>
            {isAdmin && (
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => setShowEdit(true)}>
                  <PencilSimple size={14} />
                  Edit
                </Button>
                <Button variant="destructive" size="sm" onClick={() => setShowDelete(true)}>
                  <Trash size={14} />
                  Delete
                </Button>
              </div>
            )}
          </div>

          <div className="grid gap-3 rounded-lg border border-border bg-surface2 p-4 sm:grid-cols-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Source / author
              </p>
              <p className="mt-1 text-sm">{report.source_name ?? '—'}</p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Published
              </p>
              <p className="mt-1 font-mono text-sm">{formatDate(report.published_at)}</p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Created
              </p>
              <p className="mt-1 font-mono text-sm">{formatDate(report.created_at)}</p>
              {report.created_by && (
                <p className="text-xs text-muted-foreground">by {report.created_by}</p>
              )}
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Updated
              </p>
              <p className="mt-1 font-mono text-sm">{formatDate(report.updated_at)}</p>
            </div>
            {safeSourceUrl && (
              <div className="sm:col-span-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Source URL
                </p>
                <a
                  href={safeSourceUrl}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="mt-1 inline-block break-all text-sm text-primary underline-offset-2 hover:underline"
                >
                  {safeSourceUrl}
                </a>
              </div>
            )}
          </div>

          {report.is_ai_generated && (
            <div className="rounded-lg border border-border bg-surface2 p-4">
              <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                AI provenance
              </p>
              <dl className="grid gap-2 sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-muted-foreground">Provider</dt>
                  <dd className="text-sm">{formatProvenance(report.ai_provider)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Model</dt>
                  <dd className="text-sm">{formatProvenance(report.ai_model)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Generated at</dt>
                  <dd className="text-sm">
                    {report.ai_generated_at ? formatDate(report.ai_generated_at) : 'Unknown'}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="p-5">
        <h3 className="mb-3 text-sm font-semibold">Content</h3>
        <ReportContent content={report.content} contentFormat={report.content_format} />
      </Card>

      <Card className="p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Attachment</h3>
          {isAdmin && (
            <div className="flex flex-wrap gap-2">
              <input
                ref={fileInputRef}
                type="file"
                className="sr-only"
                accept=".pdf,.md,.markdown,.txt"
                onChange={(e) => handleUpload(e.target.files?.[0])}
              />
              <Button
                variant="outline"
                size="sm"
                disabled={uploadAttachment.isPending}
                onClick={() => fileInputRef.current?.click()}
              >
                <UploadSimple size={14} />
                {report.attachment ? 'Replace' : 'Upload'}
              </Button>
              {report.attachment && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={removeAttachment.isPending}
                  onClick={() => setShowRemoveAttachment(true)}
                >
                  <X size={14} />
                  Remove
                </Button>
              )}
            </div>
          )}
        </div>
        {report.attachment ? (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface2 p-4">
            <Paperclip size={18} className="text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{report.attachment.original_filename}</p>
              <p className="text-xs text-muted-foreground">
                {formatBytes(report.attachment.size_bytes)} · {report.attachment.content_type}
              </p>
            </div>
            <Button variant="brand" size="sm" onClick={handleDownload}>
              <DownloadSimple size={14} />
              Download
            </Button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No attachment.</p>
        )}
      </Card>

      <Card className="p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Linked observables</h3>
          {isAdmin && (
            <Button variant="outline" size="sm" onClick={() => setShowLinkSearch((v) => !v)}>
              <LinkSimple size={14} />
              Link observable
            </Button>
          )}
        </div>

        {isAdmin && showLinkSearch && (
          <div className="mb-4 space-y-2 rounded-lg border border-border bg-surface2 p-4">
            <Input
              label="Search observables"
              value={linkQuery}
              onChange={(e) => setLinkQuery(e.target.value)}
              placeholder="Search by value…"
            />
            {searchResults?.items.map((obs) => {
              const linked = report.observables.some((o) => o.id === obs.id)
              return (
                <div
                  key={obs.id}
                  className="flex items-center justify-between gap-2 rounded-md border border-border bg-background px-3 py-2"
                >
                  <span className="min-w-0 truncate font-mono text-sm">{obs.value}</span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={linked || linkObservable.isPending}
                    onClick={() => handleLink(obs.id)}
                  >
                    {linked ? 'Linked' : 'Link'}
                  </Button>
                </div>
              )
            })}
          </div>
        )}

        {report.observables.length === 0 ? (
          <p className="text-sm text-muted-foreground">No linked observables.</p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {report.observables.map((obs) => (
              <li key={obs.id} className="flex flex-wrap items-center gap-2 px-3 py-2.5">
                <Link
                  to={`/observables/${obs.id}`}
                  className="min-w-0 flex-1 font-mono text-sm hover:text-primary"
                >
                  {obs.value}
                </Link>
                <span className="text-xs text-muted-foreground">
                  {typeLabels[obs.type] ?? obs.type} · {obs.confidence_score}
                </span>
                {isAdmin && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 px-0"
                    aria-label={`Unlink ${obs.value}`}
                    onClick={() => handleUnlink(obs.id)}
                  >
                    <X size={14} />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Dialog open={showEdit} onClose={() => setShowEdit(false)} title="Edit report">
        <ReportForm
          initial={report}
          onSubmit={handleEdit}
          onCancel={() => setShowEdit(false)}
          isLoading={updateReport.isPending}
        />
      </Dialog>

      <Dialog
        open={showRemoveAttachment}
        onClose={() => setShowRemoveAttachment(false)}
        title="Remove attachment"
      >
        <p className="text-sm text-muted-foreground">
          Remove the attachment from{' '}
          <span className="font-medium text-foreground">{report.title}</span>? The file will be
          deleted from storage.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setShowRemoveAttachment(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={removeAttachment.isPending}
            onClick={handleRemoveAttachment}
          >
            {removeAttachment.isPending ? 'Removing…' : 'Remove attachment'}
          </Button>
        </div>
      </Dialog>

      <Dialog open={showDelete} onClose={() => setShowDelete(false)} title="Delete report">
        <p className="text-sm text-muted-foreground">
          Permanently delete <span className="font-medium text-foreground">{report.title}</span>?
          This removes the attachment and observable links.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setShowDelete(false)}>
            Cancel
          </Button>
          <Button variant="destructive" disabled={deleteReport.isPending} onClick={handleDelete}>
            {deleteReport.isPending ? 'Deleting…' : 'Delete report'}
          </Button>
        </div>
      </Dialog>
    </div>
  )
}
