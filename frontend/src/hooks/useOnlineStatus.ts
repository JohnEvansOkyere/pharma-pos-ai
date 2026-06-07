/**
 * Hook for detecting backend connectivity when the hosted queue is enabled.
 *
 * Uses two signals:
 *   1. navigator.onLine — instant DOM event (can lie on captive portals)
 *   2. API heartbeat — periodic GET to /api/auth/heartbeat to confirm the
 *      authenticated backend is reachable.
 *
 * The hook exposes:
 *   - isOnline: boolean — true when backend is reachable
 *   - isChecking: boolean — true while a heartbeat is in flight
 *   - lastChecked: Date | null — timestamp of last successful check
 *   - recheckNow: () => void — imperatively trigger a recheck
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { isOfflineQueueEnabled } from '../config/appMode'

const HEARTBEAT_INTERVAL_MS = 15_000   // 15 s
const HEARTBEAT_TIMEOUT_MS  = 8_000    // 8 s timeout per check
const HEARTBEAT_URL = '/api/auth/heartbeat'

async function checkConnectivity(): Promise<boolean> {
  if (!navigator.onLine) return false

  const token = localStorage.getItem('auth_token')
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), HEARTBEAT_TIMEOUT_MS)

  try {
    const res = await fetch(HEARTBEAT_URL, {
      method: 'GET',
      headers,
      signal: controller.signal,
    })
    return res.ok
  } catch {
    return false
  } finally {
    clearTimeout(timeout)
  }
}

export interface OnlineStatus {
  isOnline: boolean
  isChecking: boolean
  lastChecked: Date | null
  recheckNow: () => void
}

/**
 * Returns online status for the current deployment.
 * In offline deployments always returns { isOnline: true } because the backend
 * is on the same machine and offline detection is not meaningful.
 */
export function useOnlineStatus(): OnlineStatus {
  const shouldMonitor = isOfflineQueueEnabled

  const [isOnline, setIsOnline] = useState<boolean>(true)
  const [isChecking, setIsChecking] = useState<boolean>(false)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isMountedRef = useRef(true)

  const doCheck = useCallback(async () => {
    if (!shouldMonitor) return
    if (!isMountedRef.current) return
    setIsChecking(true)
    try {
      const result = await checkConnectivity()
      if (isMountedRef.current) {
        setIsOnline(result)
        setLastChecked(new Date())
      }
    } finally {
      if (isMountedRef.current) setIsChecking(false)
    }
  }, [shouldMonitor])

  const recheckNow = useCallback(() => {
    doCheck()
  }, [doCheck])

  useEffect(() => {
    if (!shouldMonitor) return

    isMountedRef.current = true

    // Immediate check on mount
    doCheck()

    // Browser online/offline events — trigger an immediate re-check when the
    // OS reports connectivity change (don't trust it blindly).
    const onOnline  = () => doCheck()
    const onOffline = () => { if (isMountedRef.current) setIsOnline(false) }
    window.addEventListener('online',  onOnline)
    window.addEventListener('offline', onOffline)

    // Periodic heartbeat
    intervalRef.current = setInterval(doCheck, HEARTBEAT_INTERVAL_MS)

    return () => {
      isMountedRef.current = false
      window.removeEventListener('online',  onOnline)
      window.removeEventListener('offline', onOffline)
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [doCheck, shouldMonitor])

  if (!shouldMonitor) {
    return { isOnline: true, isChecking: false, lastChecked: null, recheckNow: () => {} }
  }

  return { isOnline, isChecking, lastChecked, recheckNow }
}
