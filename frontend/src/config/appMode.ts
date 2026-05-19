export const APP_MODE = (import.meta.env.VITE_APP_MODE || 'local_pos').trim().toLowerCase()

export const isCloudReportingMode = APP_MODE === 'cloud_reporting'

export function getDefaultAuthenticatedPath(user?: { role?: string; organization_id?: number | null } | null) {
  if (isCloudReportingMode) {
    if (user?.role === 'admin' && !user.organization_id) return '/clients'
    if (user?.role === 'admin' || user?.role === 'manager') return '/cloud-dashboard'
    return '/login'
  }

  return user?.role === 'admin' ? '/dashboard' : '/pos'
}
