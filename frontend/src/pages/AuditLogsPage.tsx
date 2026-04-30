import { type FormEvent, useEffect, useState } from 'react'
import { FiDownload, FiRefreshCw, FiSearch, FiShield } from 'react-icons/fi'
import { api } from '../services/api'
import { useAuthStore } from '../stores/authStore'

interface AuditLogEntry {
  id: number
  organization_id: number | null
  branch_id: number | null
  source_device_id: number | null
  user_id: number | null
  action: string
  entity_type: string | null
  entity_id: number | null
  description: string | null
  extra_data: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

interface AuditLogResponse {
  total: number
  limit: number
  offset: number
  items: AuditLogEntry[]
}

interface AuditFilters {
  organization_id: string
  branch_id: string
  action: string
  entity_type: string
  user_id: string
  start_at: string
  end_at: string
}

const emptyFilters: AuditFilters = {
  organization_id: '',
  branch_id: '',
  action: '',
  entity_type: '',
  user_id: '',
  start_at: '',
  end_at: '',
}

function compactParams(filters: AuditFilters, limit = 100, offset = 0) {
  return {
    ...(filters.organization_id ? { organization_id: Number(filters.organization_id) } : {}),
    ...(filters.branch_id ? { branch_id: Number(filters.branch_id) } : {}),
    ...(filters.action.trim() ? { action: filters.action.trim() } : {}),
    ...(filters.entity_type.trim() ? { entity_type: filters.entity_type.trim() } : {}),
    ...(filters.user_id ? { user_id: Number(filters.user_id) } : {}),
    ...(filters.start_at ? { start_at: new Date(filters.start_at).toISOString() } : {}),
    ...(filters.end_at ? { end_at: new Date(filters.end_at).toISOString() } : {}),
    limit,
    offset,
  }
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatAction(value: string) {
  return value.replace(/_/g, ' ')
}

function formatExtraData(value: Record<string, unknown> | null) {
  if (!value || Object.keys(value).length === 0) return '-'
  return JSON.stringify(value)
}

export default function AuditLogsPage() {
  const { user } = useAuthStore()
  const [filters, setFilters] = useState<AuditFilters>({
    ...emptyFilters,
    organization_id: user?.organization_id ? String(user.organization_id) : '',
    branch_id: user?.branch_id ? String(user.branch_id) : '',
  })
  const [data, setData] = useState<AuditLogResponse>({ total: 0, limit: 100, offset: 0, items: [] })
  const [isLoading, setIsLoading] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const organizationLocked = user?.organization_id != null
  const branchLocked = user?.branch_id != null

  useEffect(() => {
    loadAuditLogs()
  }, [])

  const loadAuditLogs = async (nextOffset = 0) => {
    setIsLoading(true)
    setError(null)
    try {
      const response: AuditLogResponse = await api.getAuditLogs(compactParams(filters, 100, nextOffset))
      setData(response)
    } catch (error) {
      setError('Audit logs could not be loaded.')
    } finally {
      setIsLoading(false)
    }
  }

  const submitFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    loadAuditLogs(0)
  }

  const exportCsv = async () => {
    setIsExporting(true)
    setError(null)
    try {
      const blob: Blob = await api.exportAuditLogsCsv(compactParams(filters, 5000, 0))
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'audit-logs.csv'
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      setError('Audit log export failed.')
    } finally {
      setIsExporting(false)
    }
  }

  const canPageBack = data.offset > 0
  const canPageForward = data.offset + data.limit < data.total

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-gray-100">
            <FiShield className="h-6 w-6 text-primary-600 dark:text-primary-400" />
            Audit Logs
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Tenant-scoped operational activity trail
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => loadAuditLogs(data.offset)}
            disabled={isLoading}
            className="btn-secondary flex h-10 items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FiRefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            type="button"
            onClick={exportCsv}
            disabled={isExporting}
            className="btn-primary flex h-10 items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FiDownload className={`h-4 w-4 ${isExporting ? 'animate-pulse' : ''}`} />
            Export CSV
          </button>
        </div>
      </div>

      <form onSubmit={submitFilters} className="card p-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="block">
            <span className="label">Organization ID</span>
            <input
              className="input h-10"
              inputMode="numeric"
              value={filters.organization_id}
              onChange={(event) => setFilters({ ...filters, organization_id: event.target.value })}
              disabled={organizationLocked}
            />
          </label>
          <label className="block">
            <span className="label">Branch ID</span>
            <input
              className="input h-10"
              inputMode="numeric"
              value={filters.branch_id}
              onChange={(event) => setFilters({ ...filters, branch_id: event.target.value })}
              disabled={branchLocked}
            />
          </label>
          <label className="block">
            <span className="label">Action</span>
            <input
              className="input h-10"
              value={filters.action}
              onChange={(event) => setFilters({ ...filters, action: event.target.value })}
            />
          </label>
          <label className="block">
            <span className="label">Entity type</span>
            <input
              className="input h-10"
              value={filters.entity_type}
              onChange={(event) => setFilters({ ...filters, entity_type: event.target.value })}
            />
          </label>
          <label className="block">
            <span className="label">User ID</span>
            <input
              className="input h-10"
              inputMode="numeric"
              value={filters.user_id}
              onChange={(event) => setFilters({ ...filters, user_id: event.target.value })}
            />
          </label>
          <label className="block">
            <span className="label">Start</span>
            <input
              className="input h-10"
              type="datetime-local"
              value={filters.start_at}
              onChange={(event) => setFilters({ ...filters, start_at: event.target.value })}
            />
          </label>
          <label className="block">
            <span className="label">End</span>
            <input
              className="input h-10"
              type="datetime-local"
              value={filters.end_at}
              onChange={(event) => setFilters({ ...filters, end_at: event.target.value })}
            />
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary flex h-10 w-full items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <FiSearch className="h-4 w-4" />
              Apply filters
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-100">
          {error}
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="flex flex-col gap-2 border-b border-gray-200 p-4 dark:border-gray-700 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Activity</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {data.total.toLocaleString()} matching records
            </p>
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Showing {data.items.length ? data.offset + 1 : 0}-{data.offset + data.items.length}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Time</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Action</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Scope</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Entity</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">User</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white dark:divide-gray-700 dark:bg-gray-800">
              {data.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-500 dark:text-gray-400">
                    {isLoading ? 'Loading audit logs...' : 'No audit logs found'}
                  </td>
                </tr>
              ) : (
                data.items.map((entry) => (
                  <tr key={entry.id}>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                      {formatDateTime(entry.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm font-semibold capitalize text-gray-900 dark:text-gray-100">
                        {formatAction(entry.action)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">{entry.description || '-'}</div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                      Org {entry.organization_id ?? '-'} · Branch {entry.branch_id ?? '-'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                      {entry.entity_type || '-'} #{entry.entity_id ?? '-'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                      {entry.user_id ?? 'system'}
                    </td>
                    <td className="max-w-md px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                      <span className="line-clamp-3 break-words">{formatExtraData(entry.extra_data)}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-gray-200 p-4 dark:border-gray-700">
          <button
            type="button"
            disabled={!canPageBack || isLoading}
            onClick={() => loadAuditLogs(Math.max(0, data.offset - data.limit))}
            className="btn-secondary h-10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Page {Math.floor(data.offset / data.limit) + 1}
          </span>
          <button
            type="button"
            disabled={!canPageForward || isLoading}
            onClick={() => loadAuditLogs(data.offset + data.limit)}
            className="btn-secondary h-10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
