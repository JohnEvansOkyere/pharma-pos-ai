/**
 * OfflineQueuePage — Operator view of the IndexedDB offline sale queue.
 *
 * Shows pending and failed sales queued during connectivity loss.
 * Operators can:
 *   • Retry individual failed items (resets attempts → pending)
 *   • Retry all failed at once
 *   • Delete a specific item (with confirmation)
 *   • Export failed items as JSON for manual reconciliation
 *   • Export the full queue as JSON
 *   • Trigger a manual flush when connectivity is present
 */
import { useCallback, useEffect, useState } from 'react'
import {
  FiAlertTriangle,
  FiCheckCircle,
  FiClock,
  FiDownload,
  FiRefreshCw,
  FiTrash2,
  FiWifi,
  FiWifiOff,
  FiXCircle,
} from 'react-icons/fi'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import {
  clearFailed,
  exportAll,
  exportFailed,
  failedCount,
  flush,
  list,
  pendingCount,
  removeItem,
  retryAllFailed,
  retryFailed,
  type QueuedSale,
} from '../services/offlineQueue'
import { useOnlineStatus } from '../hooks/useOnlineStatus'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function StatusBadge({ status }: { status: QueuedSale['status'] }) {
  if (status === 'pending') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
        style={{ background: '#1d4ed8', color: '#bfdbfe' }}>
        <FiClock size={11} /> Pending
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ background: '#7f1d1d', color: '#fecaca' }}>
      <FiXCircle size={11} /> Failed
    </span>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function OfflineQueuePage() {
  const { isOnline } = useOnlineStatus()
  const [items, setItems] = useState<QueuedSale[]>([])
  const [pendingCnt, setPendingCnt] = useState(0)
  const [failedCnt, setFailedCnt] = useState(0)
  const [loading, setLoading] = useState(true)
  const [flushing, setFlushing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const loadQueue = useCallback(async () => {
    setLoading(true)
    try {
      const [all, pending, failed] = await Promise.all([
        list(),
        pendingCount(),
        failedCount(),
      ])
      setItems(all)
      setPendingCnt(pending)
      setFailedCnt(failed)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadQueue()
  }, [loadQueue])

  // ── Actions ────────────────────────────────────────────────────────────────

  async function handleFlush() {
    if (!isOnline) {
      toast.error('Cannot flush — you are offline')
      return
    }
    setFlushing(true)
    try {
      const result = await flush(
        (payload) => api.createSale(payload as never),
        () => loadQueue(),
      )
      toast.success(`Flushed ${result.flushed} sale(s). ${result.failed} failed.`)
    } catch {
      toast.error('Flush error — check console')
    } finally {
      setFlushing(false)
      await loadQueue()
    }
  }

  async function handleRetryOne(id: number) {
    await retryFailed(id)
    await loadQueue()
    toast.success('Item reset to pending')
  }

  async function handleRetryAll() {
    const n = await retryAllFailed()
    await loadQueue()
    toast.success(`${n} item(s) reset to pending`)
  }

  async function handleDelete(id: number) {
    await removeItem(id)
    setConfirmDelete(null)
    await loadQueue()
    toast.success('Item removed')
  }

  async function handleClearFailed() {
    const n = await clearFailed()
    await loadQueue()
    toast.success(`${n} failed item(s) cleared`)
  }

  async function handleExportFailed() {
    const n = await exportFailed()
    if (n === 0) toast('No failed items to export')
    else toast.success(`Exported ${n} failed item(s) as JSON`)
  }

  async function handleExportAll() {
    const n = await exportAll()
    if (n === 0) toast('Queue is empty')
    else toast.success(`Exported ${n} item(s) as JSON`)
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const card: React.CSSProperties = {
    background: 'linear-gradient(135deg, #0f1f3d 0%, #1a2f50 100%)',
    border: '1px solid #1e3a6a',
    borderRadius: 12,
    padding: '1rem 1.25rem',
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0a1628', color: '#e2e8f0', padding: '1.5rem' }}>
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
          Offline Sale Queue
        </h1>
        <p style={{ color: '#94a3b8', marginTop: 4, fontSize: 14 }}>
          Sales queued during connectivity loss. Flush to sync with the server when back online.
        </p>
      </div>

      {/* Durability warning */}
      <div style={{
        ...card,
        border: '1px solid #92400e',
        background: '#1c1007',
        display: 'flex',
        gap: 12,
        alignItems: 'flex-start',
        marginBottom: '1.25rem',
      }}>
        <FiAlertTriangle style={{ color: '#f59e0b', flexShrink: 0, marginTop: 2 }} size={18} />
        <p style={{ margin: 0, color: '#fcd34d', fontSize: 13, lineHeight: 1.6 }}>
          <strong>Data durability notice:</strong> This queue is stored in browser IndexedDB.
          Clearing browser data, using incognito mode, or a browser crash may destroy unsynced sales.
          Export failed items before clearing browser data. For mission-critical offline operation,
          use <strong>local_pos</strong> mode, which writes to a local PostgreSQL database.
        </p>
      </div>

      {/* KPI tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: '1.25rem' }}>
        <div style={{ ...card, textAlign: 'center' }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#60a5fa' }}>{pendingCnt}</div>
          <div style={{ color: '#94a3b8', fontSize: 13 }}>Pending</div>
        </div>
        <div style={{ ...card, textAlign: 'center' }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#f87171' }}>{failedCnt}</div>
          <div style={{ color: '#94a3b8', fontSize: 13 }}>Failed</div>
        </div>
        <div style={{ ...card, textAlign: 'center' }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: isOnline ? '#4ade80' : '#f87171' }}>
            {isOnline ? <FiWifi style={{ display: 'inline' }} /> : <FiWifiOff style={{ display: 'inline' }} />}
          </div>
          <div style={{ color: '#94a3b8', fontSize: 13 }}>{isOnline ? 'Online' : 'Offline'}</div>
        </div>
      </div>

      {/* Action bar */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        <button
          id="btn-flush-queue"
          onClick={handleFlush}
          disabled={flushing || !isOnline || pendingCnt === 0}
          style={{
            background: pendingCnt > 0 && isOnline ? '#2563eb' : '#1e3a6a',
            color: '#e2e8f0',
            border: 'none',
            borderRadius: 8,
            padding: '8px 16px',
            cursor: pendingCnt > 0 && isOnline ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 14,
            fontWeight: 600,
            opacity: flushing ? 0.7 : 1,
          }}
        >
          <FiRefreshCw size={14} style={{ animation: flushing ? 'spin 1s linear infinite' : 'none' }} />
          {flushing ? 'Flushing…' : 'Flush Now'}
        </button>

        {failedCnt > 0 && (
          <>
            <button
              id="btn-retry-all-failed"
              onClick={handleRetryAll}
              style={{ background: '#065f46', color: '#a7f3d0', border: 'none', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}
            >
              ↺ Retry All Failed
            </button>
            <button
              id="btn-export-failed"
              onClick={handleExportFailed}
              style={{ background: '#1e3a6a', color: '#93c5fd', border: '1px solid #2563eb', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 14 }}
            >
              <FiDownload size={14} /> Export Failed
            </button>
            <button
              id="btn-clear-failed"
              onClick={handleClearFailed}
              style={{ background: '#450a0a', color: '#fca5a5', border: '1px solid #7f1d1d', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', fontSize: 14 }}
            >
              <FiTrash2 size={14} style={{ display: 'inline', marginRight: 4 }} />
              Clear Failed
            </button>
          </>
        )}

        {items.length > 0 && (
          <button
            id="btn-export-all"
            onClick={handleExportAll}
            style={{ background: '#1e3a6a', color: '#93c5fd', border: '1px solid #2563eb', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 14 }}
          >
            <FiDownload size={14} /> Export All
          </button>
        )}

        <button
          id="btn-refresh-queue"
          onClick={loadQueue}
          style={{ background: 'transparent', color: '#64748b', border: '1px solid #1e3a6a', borderRadius: 8, padding: '8px 12px', cursor: 'pointer', fontSize: 13 }}
        >
          Refresh
        </button>
      </div>

      {/* Queue table */}
      {loading ? (
        <div style={{ color: '#64748b', textAlign: 'center', padding: '2rem' }}>Loading queue…</div>
      ) : items.length === 0 ? (
        <div style={{ ...card, textAlign: 'center', padding: '3rem' }}>
          <FiCheckCircle size={40} style={{ color: '#4ade80', marginBottom: 12 }} />
          <div style={{ fontSize: 16, fontWeight: 600, color: '#94a3b8' }}>Queue is empty</div>
          <div style={{ color: '#475569', fontSize: 13, marginTop: 4 }}>All sales have been synced.</div>
        </div>
      ) : (
        <div style={card}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e3a6a', color: '#64748b', textAlign: 'left' }}>
                <th style={{ padding: '8px 10px' }}>Invoice</th>
                <th style={{ padding: '8px 10px' }}>Queued At</th>
                <th style={{ padding: '8px 10px' }}>Status</th>
                <th style={{ padding: '8px 10px' }}>Attempts</th>
                <th style={{ padding: '8px 10px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <>
                  <tr
                    key={item.id}
                    style={{
                      borderBottom: '1px solid #1e3a6a',
                      cursor: 'pointer',
                      background: expandedId === item.id ? '#0f1f3d' : 'transparent',
                    }}
                    onClick={() => setExpandedId(expandedId === item.id ? null : item.id!)}
                  >
                    <td style={{ padding: '10px', fontFamily: 'monospace', color: '#60a5fa' }}>
                      {item.localInvoice}
                    </td>
                    <td style={{ padding: '10px', color: '#94a3b8' }}>{fmtDate(item.queuedAt)}</td>
                    <td style={{ padding: '10px' }}><StatusBadge status={item.status} /></td>
                    <td style={{ padding: '10px', color: '#94a3b8', textAlign: 'center' }}>{item.attempts}</td>
                    <td style={{ padding: '10px' }}>
                      <div style={{ display: 'flex', gap: 8 }}>
                        {item.status === 'failed' && (
                          <button
                            id={`btn-retry-${item.id}`}
                            onClick={(e) => { e.stopPropagation(); handleRetryOne(item.id!) }}
                            title="Retry this item"
                            style={{ background: '#065f46', color: '#a7f3d0', border: 'none', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 12 }}
                          >
                            ↺ Retry
                          </button>
                        )}
                        {confirmDelete === item.id ? (
                          <>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDelete(item.id!) }}
                              style={{ background: '#7f1d1d', color: '#fca5a5', border: 'none', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 12 }}
                            >
                              Confirm
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); setConfirmDelete(null) }}
                              style={{ background: '#1e3a6a', color: '#94a3b8', border: 'none', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 12 }}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button
                            id={`btn-delete-${item.id}`}
                            onClick={(e) => { e.stopPropagation(); setConfirmDelete(item.id!) }}
                            title="Delete this item"
                            style={{ background: 'transparent', color: '#64748b', border: 'none', cursor: 'pointer' }}
                          >
                            <FiTrash2 size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {expandedId === item.id && (
                    <tr key={`${item.id}-exp`} style={{ background: '#0b1829' }}>
                      <td colSpan={5} style={{ padding: '12px 16px' }}>
                        {item.lastError && (
                          <div style={{ marginBottom: 8, color: '#f87171', fontSize: 12 }}>
                            <strong>Error:</strong> {item.lastError}
                          </div>
                        )}
                        <div style={{ color: '#64748b', fontSize: 12, marginBottom: 4 }}>Sale payload:</div>
                        <pre style={{
                          background: '#060e1c',
                          borderRadius: 6,
                          padding: '10px',
                          fontSize: 11,
                          color: '#a5b4c8',
                          overflow: 'auto',
                          maxHeight: 240,
                          margin: 0,
                        }}>
                          {JSON.stringify(item.payload, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
