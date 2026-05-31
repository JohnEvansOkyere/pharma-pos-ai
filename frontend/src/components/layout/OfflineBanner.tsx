/**
 * OfflineBanner — visible only in online_pos mode when connectivity is lost.
 *
 * Shows:
 *   - Red banner when offline with queue count
 *   - Amber banner when flushing queued transactions
 *   - Green flash banner when reconnected and queue was flushed
 */
import { useEffect, useState } from 'react'
import { FiAlertTriangle, FiCheckCircle, FiRefreshCw, FiWifiOff } from 'react-icons/fi'
import { isOnlinePosMode } from '../../config/appMode'
import type { OnlineStatus } from '../../hooks/useOnlineStatus'
import { clearFailed, flush, pendingCount } from '../../services/offlineQueue'
import { api } from '../../services/api'

interface Props {
  onlineStatus: OnlineStatus
}

type BannerState = 'hidden' | 'offline' | 'flushing' | 'flushed'

export default function OfflineBanner({ onlineStatus }: Props) {
  const { isOnline, isChecking, recheckNow } = onlineStatus
  const [bannerState, setBannerState] = useState<BannerState>('hidden')
  const [queueSize, setQueueSize] = useState(0)
  const [flushedCount, setFlushedCount] = useState(0)
  const [failedCount, setFailedCount] = useState(0)

  // Not relevant in local_pos mode
  if (!isOnlinePosMode) return null

  // Update queue size whenever visibility changes
  useEffect(() => {
    const update = async () => {
      const count = await pendingCount()
      setQueueSize(count)
    }
    update()
    const interval = setInterval(update, 5000)
    return () => clearInterval(interval)
  }, [])

  // React to connectivity changes
  useEffect(() => {
    if (!isOnline) {
      setBannerState('offline')
      return
    }

    // We're back online — check if there's anything to flush
    pendingCount().then(async (count) => {
      if (count === 0) {
        setBannerState('hidden')
        return
      }

      // Flush the queue
      setBannerState('flushing')
      try {
        const result = await flush(
          (payload) => api.createSale(payload as any),
          async () => {
            const remaining = await pendingCount()
            setQueueSize(remaining)
          },
        )
        setFlushedCount(result.flushed)
        setFailedCount(result.failed)
        setQueueSize(result.remaining)
        setBannerState('flushed')
        // Auto-hide after 6 seconds if no failures remain
        if (result.failed === 0) {
          setTimeout(() => setBannerState('hidden'), 6000)
        }
      } catch {
        setBannerState('offline')
      }
    })
  }, [isOnline])

  if (bannerState === 'hidden') return null

  // ── Offline banner ─────────────────────────────────────────────────────────
  if (bannerState === 'offline') {
    return (
      <div
        role="alert"
        aria-live="assertive"
        style={{
          background: 'linear-gradient(90deg, #7f1d1d, #991b1b)',
          color: '#fecaca',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 20px',
          gap: 12,
          fontSize: 14,
          fontWeight: 500,
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          zIndex: 1000,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <FiWifiOff style={{ flexShrink: 0, width: 18, height: 18 }} />
          <span>
            <strong>No internet connection.</strong>
            {queueSize > 0
              ? ` ${queueSize} sale${queueSize === 1 ? '' : 's'} queued — will sync automatically when reconnected.`
              : ' Sales will be queued locally until reconnected.'}
          </span>
        </div>
        <button
          onClick={recheckNow}
          disabled={isChecking}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(255,255,255,0.12)',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 6,
            color: '#fecaca',
            padding: '5px 12px',
            cursor: isChecking ? 'wait' : 'pointer',
            fontSize: 13,
            whiteSpace: 'nowrap',
          }}
        >
          <FiRefreshCw
            style={{
              width: 14,
              height: 14,
              animation: isChecking ? 'spin 1s linear infinite' : undefined,
            }}
          />
          {isChecking ? 'Checking…' : 'Check now'}
        </button>
      </div>
    )
  }

  // ── Flushing banner ────────────────────────────────────────────────────────
  if (bannerState === 'flushing') {
    return (
      <div
        role="status"
        aria-live="polite"
        style={{
          background: 'linear-gradient(90deg, #78350f, #92400e)',
          color: '#fde68a',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 20px',
          fontSize: 14,
          fontWeight: 500,
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          zIndex: 1000,
        }}
      >
        <FiRefreshCw
          style={{ flexShrink: 0, width: 18, height: 18, animation: 'spin 1s linear infinite' }}
        />
        <span>
          Reconnected — syncing {queueSize} queued{' '}
          {queueSize === 1 ? 'sale' : 'sales'}…
        </span>
      </div>
    )
  }

  // ── Flushed / success banner ───────────────────────────────────────────────
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        background: 'linear-gradient(90deg, #064e3b, #065f46)',
        color: '#a7f3d0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 10,
        padding: '10px 20px',
        fontSize: 14,
        fontWeight: 500,
        boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
        zIndex: 1000,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <FiCheckCircle style={{ flexShrink: 0, width: 18, height: 18 }} />
        <span>
          Back online.{' '}
          {flushedCount > 0
            ? `${flushedCount} queued sale${flushedCount === 1 ? '' : 's'} synced successfully.`
            : 'Queue is clear.'}
          {failedCount > 0 && (
            <span style={{ color: '#fca5a5', marginLeft: 8 }}>
              {failedCount} failed — please contact support.
            </span>
          )}
        </span>
      </div>
      {failedCount > 0 && (
        <button
          onClick={async () => {
            await clearFailed()
            setFailedCount(0)
            setBannerState('hidden')
          }}
          style={{
            background: 'rgba(255,255,255,0.12)',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 6,
            color: '#a7f3d0',
            padding: '5px 12px',
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Clear failed
        </button>
      )}
      {failedCount === 0 && (
        <button
          onClick={() => setBannerState('hidden')}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#6ee7b7',
            cursor: 'pointer',
            padding: '4px 8px',
            fontSize: 18,
            lineHeight: 1,
          }}
          aria-label="Dismiss"
        >
          ×
        </button>
      )}
    </div>
  )
}
