/**
 * Follow-up Dashboard — pharmacist view of all pending health follow-up messages.
 * Shows queue, status counts, and allows manual review.
 * Only visible in online_pos mode.
 */
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { FiAlertTriangle, FiCheckCircle, FiClock, FiMessageSquare, FiRefreshCw, FiSkipForward } from 'react-icons/fi'
import { api } from '../services/api'

interface FollowUp {
  id: number
  customer_id: number
  sale_id: number
  scheduled_at: string
  channel: string
  status: string
  sent_at?: string
  attempts: number
  last_error?: string
  message_text?: string
  created_at: string
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending:   { label: 'Pending',   color: '#d97706', icon: <FiClock style={{ width: 14, height: 14 }} /> },
  sent:      { label: 'Sent',      color: '#16a34a', icon: <FiCheckCircle style={{ width: 14, height: 14 }} /> },
  delivered: { label: 'Delivered', color: '#0ea5e9', icon: <FiCheckCircle style={{ width: 14, height: 14 }} /> },
  failed:    { label: 'Failed',    color: '#dc2626', icon: <FiAlertTriangle style={{ width: 14, height: 14 }} /> },
  skipped:   { label: 'Skipped',   color: '#9ca3af', icon: <FiSkipForward style={{ width: 14, height: 14 }} /> },
  responded: { label: 'Responded', color: '#7c3aed', icon: <FiMessageSquare style={{ width: 14, height: 14 }} /> },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, color: '#9ca3af', icon: null }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600,
      padding: '2px 8px', borderRadius: 999,
      background: `${cfg.color}22`, color: cfg.color,
    }}>
      {cfg.icon}
      {cfg.label}
    </span>
  )
}

export default function FollowUpDashboard() {
  const [followUps, setFollowUps] = useState<FollowUp[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState<'pending' | 'all'>('pending')

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    setIsLoading(true)
    try {
      const data = await api.getPendingFollowUps()
      setFollowUps(data)
    } catch {
      toast.error('Failed to load follow-ups')
    } finally {
      setIsLoading(false)
    }
  }

  const counts = {
    pending: followUps.filter(f => f.status === 'pending').length,
    sent: followUps.filter(f => f.status === 'sent').length,
    failed: followUps.filter(f => f.status === 'failed').length,
    skipped: followUps.filter(f => f.status === 'skipped').length,
  }

  const displayed = filter === 'pending'
    ? followUps.filter(f => f.status === 'pending')
    : followUps

  const overdue = followUps.filter(
    f => f.status === 'pending' && new Date(f.scheduled_at) < new Date()
  ).length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div className="card" style={{ padding: '18px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }} className="text-gray-900 dark:text-gray-100">
              Follow-up Dashboard
            </h1>
            <p style={{ margin: '4px 0 0', fontSize: 13 }} className="text-gray-500 dark:text-gray-400">
              Scheduled health messages · sent automatically every hour by the system
            </p>
          </div>
          <button onClick={load} disabled={isLoading} className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <FiRefreshCw style={{ width: 14, height: 14, animation: isLoading ? 'spin 1s linear infinite' : undefined }} />
            Refresh
          </button>
        </div>

        {overdue > 0 && (
          <div style={{ marginTop: 14, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <FiAlertTriangle style={{ color: '#dc2626', flexShrink: 0 }} />
            <p style={{ margin: 0, fontSize: 13, color: '#991b1b' }}>
              <strong>{overdue}</strong> follow-up{overdue !== 1 ? 's are' : ' is'} overdue — the system will send them on the next hourly run.
            </p>
          </div>
        )}

        {/* Stat tiles */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginTop: 16 }}>
          {[
            { label: 'Pending', value: counts.pending, color: '#d97706' },
            { label: 'Sent',    value: counts.sent,    color: '#16a34a' },
            { label: 'Failed',  value: counts.failed,  color: '#dc2626' },
            { label: 'Skipped', value: counts.skipped, color: '#9ca3af' },
          ].map(s => (
            <div key={s.label} style={{ background: `${s.color}11`, border: `1px solid ${s.color}33`, borderRadius: 8, padding: '10px 14px', textAlign: 'center' }}>
              <p style={{ margin: 0, fontSize: 24, fontWeight: 700, color: s.color }}>{s.value}</p>
              <p style={{ margin: 0, fontSize: 12, color: s.color, opacity: 0.8 }}>{s.label}</p>
            </div>
          ))}
        </div>

        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          {(['pending', 'all'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
                fontWeight: 600, fontSize: 13,
                background: filter === f ? '#4f46e5' : 'transparent',
                color: filter === f ? 'white' : '#6b7280',
              }}
            >
              {f === 'pending' ? 'Pending Only' : 'All Follow-ups'}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: '60px 0', textAlign: 'center', color: '#9ca3af' }}>Loading…</div>
        ) : displayed.length === 0 ? (
          <div style={{ padding: '60px 0', textAlign: 'center' }}>
            <FiCheckCircle style={{ width: 36, height: 36, color: '#16a34a', margin: '0 auto 10px' }} />
            <p style={{ margin: 0, fontSize: 14, fontWeight: 500 }} className="text-gray-700 dark:text-gray-300">
              {filter === 'pending' ? 'No pending follow-ups — all clear!' : 'No follow-ups recorded yet.'}
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                  {['Customer ID', 'Sale ID', 'Channel', 'Scheduled', 'Status', 'Attempts', 'Error'].map(h => (
                    <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }} className="text-gray-500 dark:text-gray-400">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayed.map(f => (
                  <tr key={f.id} style={{ borderBottom: '1px solid #e5e7eb' }} className="hover:bg-gray-50 dark:hover:bg-gray-800/40">
                    <td style={{ padding: '10px 16px', fontWeight: 600 }} className="text-gray-900 dark:text-gray-100">#{f.customer_id}</td>
                    <td style={{ padding: '10px 16px' }} className="text-gray-600 dark:text-gray-400">#{f.sale_id}</td>
                    <td style={{ padding: '10px 16px', textTransform: 'capitalize' }} className="text-gray-600 dark:text-gray-400">{f.channel}</td>
                    <td style={{ padding: '10px 16px' }} className="text-gray-600 dark:text-gray-400">
                      {new Date(f.scheduled_at).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })}
                      {new Date(f.scheduled_at) < new Date() && f.status === 'pending' && (
                        <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 700, color: '#dc2626', background: '#fee2e2', borderRadius: 4, padding: '1px 5px' }}>OVERDUE</span>
                      )}
                    </td>
                    <td style={{ padding: '10px 16px' }}><StatusBadge status={f.status} /></td>
                    <td style={{ padding: '10px 16px', textAlign: 'center' }} className="text-gray-600 dark:text-gray-400">{f.attempts}</td>
                    <td style={{ padding: '10px 16px', maxWidth: 200 }}>
                      {f.last_error ? (
                        <span style={{ fontSize: 11, color: '#dc2626' }} title={f.last_error}>
                          {f.last_error.slice(0, 60)}{f.last_error.length > 60 ? '…' : ''}
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
