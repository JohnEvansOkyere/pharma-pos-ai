const rawAppMode = (import.meta.env.VITE_APP_MODE || 'operational_pos').trim().toLowerCase()

const normalizedAppMode =
  rawAppMode === 'local_pos' || rawAppMode === 'online_pos'
    ? 'operational_pos'
    : rawAppMode
export const APP_MODE =
  normalizedAppMode === 'cloud_reporting' ? 'cloud_reporting' : 'operational_pos'

export const DEPLOYMENT_PROFILE = (
  import.meta.env.VITE_POS_DEPLOYMENT_PROFILE
  || (rawAppMode === 'online_pos' ? 'hosted' : 'offline')
).trim().toLowerCase()

function envFlag(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined || value.trim() === '') return fallback
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase())
}

export const isCloudReportingMode = APP_MODE === 'cloud_reporting'
export const isPosMode = APP_MODE === 'operational_pos'
export const isHostedDeployment = isPosMode && DEPLOYMENT_PROFILE === 'hosted'
export const isCustomerRetentionEnabled = isPosMode && envFlag(
  import.meta.env.VITE_CUSTOMER_RETENTION_ENABLED,
  isHostedDeployment,
)
export const isOfflineQueueEnabled = isHostedDeployment && envFlag(
  import.meta.env.VITE_OFFLINE_QUEUE_ENABLED,
  true,
)

export function getDefaultAuthenticatedPath(user?: { role?: string; organization_id?: number | null } | null) {
  if (isCloudReportingMode) {
    if (user?.role === 'admin' && !user.organization_id) return '/clients'
    if (user?.role === 'admin' || user?.role === 'manager') return '/cloud-dashboard'
    return '/login'
  }

  return user?.role === 'admin' ? '/dashboard' : '/pos'
}
