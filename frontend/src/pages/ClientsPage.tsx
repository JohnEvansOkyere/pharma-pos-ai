import { useEffect, useState } from 'react'
import {
  FiActivity,
  FiAlertTriangle,
  FiCheckCircle,
  FiChevronDown,
  FiChevronRight,
  FiClock,
  FiCopy,
  FiDollarSign,
  FiKey,
  FiPackage,
  FiPlus,
  FiRefreshCw,
  FiServer,
  FiShield,
  FiToggleLeft,
  FiToggleRight,
  FiUsers,
  FiWifi,
  FiWifiOff,
  FiX,
} from 'react-icons/fi'
import toast from 'react-hot-toast'
import { api } from '../services/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface OrgDetail {
  id: number
  name: string
  legal_name: string | null
  contact_phone: string | null
  contact_email: string | null
  is_active: boolean
  created_at: string
  branch_count: number
  device_count: number
}

interface BranchDetail {
  id: number
  organization_id: number
  name: string
  code: string
  phone: string | null
  address: string | null
  is_active: boolean
  created_at: string
  device_count: number
}

interface DeviceDetail {
  id: number
  organization_id: number
  branch_id: number
  device_uid: string
  name: string
  status: 'active' | 'disabled' | 'retired'
  last_seen_at: string | null
  created_at: string
  organization_name: string | null
  branch_name: string | null
}

interface DeviceProvisionResponse extends DeviceDetail {
  raw_token: string
  env_block: string
}

interface CommandCenterTotals {
  total_pharmacies: number
  active_pharmacies: number
  total_branches: number
  active_branches: number
  total_devices: number
  active_devices: number
  disabled_devices: number
  retired_devices: number
  synced_last_24h: number
  stale_devices: number
  never_synced_devices: number
  branches_without_devices: number
  branches_without_healthy_device: number
  heartbeat_ready_devices: number
  heartbeat_warning_devices: number
  heartbeat_critical_devices: number
  heartbeat_stale_devices: number
  heartbeat_missing_devices: number
}

interface CommandCenterDataTrust {
  status: 'fresh' | 'delayed' | 'stale' | 'unsafe' | 'unknown'
  last_event_received_at: string | null
  last_projected_at: string | null
  projection_lag_minutes: number | null
  ingested_event_count: number
  projected_event_count: number
  unprojected_event_count: number
  projection_failed_count: number
  duplicate_delivery_count: number
}

interface CommandCenterMoneyPulse {
  today_revenue: number
  yesterday_revenue: number
  trailing_7d_revenue: number
  today_sales_count: number
  yesterday_sales_count: number
  trailing_7d_sales_count: number
}

interface CommandCenterStockRisk {
  out_of_stock_products: number
  low_stock_products: number
  expired_batches: number
  near_expiry_batches: number
  quantity_on_hand: number
  value_at_risk: number
  expiry_warning_days: number
}

interface CommandCenterAttentionItem {
  severity: 'critical' | 'high' | 'medium' | 'low'
  kind: string
  title: string
  detail: string
  organization_id: number | null
  organization_name: string | null
  branch_id: number | null
  branch_name: string | null
  device_id: number | null
  device_name: string | null
  last_seen_at: string | null
}

interface CommandCenterOrganizationSummary {
  organization_id: number
  organization_name: string
  branch_count: number
  device_count: number
  active_device_count: number
  stale_device_count: number
  never_synced_device_count: number
  last_seen_at: string | null
  today_revenue: number
  trailing_7d_revenue: number
  projection_failed_count: number
  sync_status: 'fresh' | 'delayed' | 'stale' | 'never' | 'unknown'
  readiness_status: 'ready' | 'warning' | 'critical' | 'unknown'
  last_heartbeat_at: string | null
  heartbeat_critical_count: number
  heartbeat_warning_count: number
  heartbeat_stale_count: number
  heartbeat_missing_count: number
}

interface AdminCommandCenter {
  generated_at: string
  totals: CommandCenterTotals
  data_trust: CommandCenterDataTrust
  last_heartbeat_at: string | null
  money: CommandCenterMoneyPulse
  stock_risk: CommandCenterStockRisk
  attention: CommandCenterAttentionItem[]
  organizations: CommandCenterOrganizationSummary[]
}

type WizardStep = 'org' | 'branch' | 'device' | 'done'

// ── Helpers ───────────────────────────────────────────────────────────────────

function syncAge(lastSeen: string | null): { label: string; healthy: boolean } {
  if (!lastSeen) return { label: 'Never synced', healthy: false }
  const diffMs = Date.now() - new Date(lastSeen).getTime()
  const diffH = diffMs / 3_600_000
  if (diffH < 1) return { label: `${Math.round(diffH * 60)}m ago`, healthy: true }
  if (diffH < 24) return { label: `${Math.round(diffH)}h ago`, healthy: true }
  return { label: `${Math.round(diffH / 24)}d ago`, healthy: false }
}

function formatCurrency(value: number) {
  return `GH₵${Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function formatNumber(value: number) {
  return Number(value || 0).toLocaleString()
}

function formatDateTime(value: string | null) {
  if (!value) return 'Never'
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function trustTone(status: string) {
  if (status === 'fresh' || status === 'ready') return 'text-green-700 bg-green-100 border-green-200 dark:text-green-300 dark:bg-green-900/30 dark:border-green-800'
  if (status === 'delayed' || status === 'warning') return 'text-amber-700 bg-amber-100 border-amber-200 dark:text-amber-300 dark:bg-amber-900/30 dark:border-amber-800'
  if (status === 'unsafe') return 'text-red-700 bg-red-100 border-red-200 dark:text-red-300 dark:bg-red-900/30 dark:border-red-800'
  if (status === 'stale' || status === 'critical') return 'text-red-700 bg-red-100 border-red-200 dark:text-red-300 dark:bg-red-900/30 dark:border-red-800'
  return 'text-gray-700 bg-gray-100 border-gray-200 dark:text-gray-300 dark:bg-gray-800 dark:border-gray-700'
}

function severityTone(severity: string) {
  if (severity === 'critical') return 'border-red-500 bg-red-50 dark:bg-red-950/30'
  if (severity === 'high') return 'border-amber-500 bg-amber-50 dark:bg-amber-950/30'
  if (severity === 'medium') return 'border-blue-500 bg-blue-50 dark:bg-blue-950/30'
  return 'border-gray-300 bg-gray-50 dark:bg-gray-800'
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).then(() => toast.success('Copied to clipboard'))
}

// ── Stats bar ─────────────────────────────────────────────────────────────────

function StatsBar({ orgs, devices }: { orgs: OrgDetail[]; devices: DeviceDetail[] }) {
  const activeDevices = devices.filter(d => d.status === 'active').length
  const syncedToday = devices.filter(d => {
    if (!d.last_seen_at) return false
    return Date.now() - new Date(d.last_seen_at).getTime() < 86_400_000
  }).length

  const stats = [
    { label: 'Pharmacies', value: orgs.length, icon: FiUsers },
    { label: 'Total Devices', value: devices.length, icon: FiServer },
    { label: 'Active Devices', value: activeDevices, icon: FiCheckCircle },
    { label: 'Synced Today', value: syncedToday, icon: FiActivity },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-6">
      {stats.map(s => (
        <div key={s.label} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 flex items-center gap-3">
          <s.icon className="text-blue-600 dark:text-blue-400 shrink-0" size={20} />
          <div>
            <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{s.value}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">{s.label}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Owner command center ─────────────────────────────────────────────────────

function CommandCenterCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = 'blue',
}: {
  label: string
  value: string | number
  detail: string
  icon: any
  tone?: 'blue' | 'green' | 'amber' | 'red' | 'slate'
}) {
  const toneClass = {
    blue: 'text-blue-600 dark:text-blue-400',
    green: 'text-green-600 dark:text-green-400',
    amber: 'text-amber-600 dark:text-amber-400',
    red: 'text-red-600 dark:text-red-400',
    slate: 'text-slate-600 dark:text-slate-400',
  }[tone]

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</div>
          <div className="mt-2 text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</div>
          <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{detail}</div>
        </div>
        <Icon className={`${toneClass} shrink-0`} size={21} />
      </div>
    </div>
  )
}

function CommandCenterOverview({ command }: { command: AdminCommandCenter }) {
  const attentionCount =
    command.totals.stale_devices +
    command.totals.never_synced_devices +
    command.totals.branches_without_healthy_device +
    command.data_trust.projection_failed_count +
    command.totals.heartbeat_warning_devices +
    command.totals.heartbeat_critical_devices

  return (
    <div className="space-y-4 mb-6">
      <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <FiShield className="text-blue-600 dark:text-blue-400" size={20} />
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Owner Command Center</h2>
            </div>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Admin-only fleet intelligence: reachability, data freshness, money pulse, and stock risk.
            </p>
          </div>
          <div className={`inline-flex items-center gap-2 self-start rounded-full border px-3 py-1 text-xs font-semibold ${trustTone(command.data_trust.status)}`}>
            Data trust: {command.data_trust.status}
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <CommandCenterCard
            label="Fleet Coverage"
            value={`${command.totals.synced_last_24h}/${command.totals.active_devices}`}
            detail={`${command.totals.branches_without_healthy_device} branches need a healthy device`}
            icon={FiWifi}
            tone={command.totals.branches_without_healthy_device ? 'amber' : 'green'}
          />
          <CommandCenterCard
            label="Needs Attention"
            value={attentionCount}
            detail={`${command.totals.never_synced_devices} never synced · ${command.totals.stale_devices} stale`}
            icon={FiAlertTriangle}
            tone={attentionCount ? 'red' : 'green'}
          />
          <CommandCenterCard
            label="Install Health"
            value={`${command.totals.heartbeat_ready_devices}/${command.totals.active_devices}`}
            detail={`${command.totals.heartbeat_critical_devices} critical · ${command.totals.heartbeat_warning_devices} warning`}
            icon={FiServer}
            tone={command.totals.heartbeat_critical_devices ? 'red' : command.totals.heartbeat_warning_devices ? 'amber' : 'green'}
          />
          <CommandCenterCard
            label="Today Revenue"
            value={formatCurrency(command.money.today_revenue)}
            detail={`${formatNumber(command.money.today_sales_count)} sales · 7d ${formatCurrency(command.money.trailing_7d_revenue)}`}
            icon={FiDollarSign}
            tone="blue"
          />
          <CommandCenterCard
            label="Stock At Risk"
            value={formatCurrency(command.stock_risk.value_at_risk)}
            detail={`${command.stock_risk.out_of_stock_products} out · ${command.stock_risk.near_expiry_batches} near expiry`}
            icon={FiPackage}
            tone={(command.stock_risk.expired_batches || command.stock_risk.out_of_stock_products) ? 'red' : 'slate'}
          />
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <DataTrustPanel command={command} />
        <AttentionQueue items={command.attention} />
      </div>
    </div>
  )
}

function DataTrustPanel({ command }: { command: AdminCommandCenter }) {
  const rows = [
    ['Last event received', formatDateTime(command.data_trust.last_event_received_at)],
    ['Last projected', formatDateTime(command.data_trust.last_projected_at)],
    ['Projection lag', command.data_trust.projection_lag_minutes == null ? 'Unknown' : `${command.data_trust.projection_lag_minutes}m`],
    ['Accepted / projected', `${formatNumber(command.data_trust.ingested_event_count)} / ${formatNumber(command.data_trust.projected_event_count)}`],
    ['Backlog / failures', `${formatNumber(command.data_trust.unprojected_event_count)} / ${formatNumber(command.data_trust.projection_failed_count)}`],
    ['Duplicate deliveries', formatNumber(command.data_trust.duplicate_delivery_count)],
    ['Last heartbeat', formatDateTime(command.last_heartbeat_at)],
  ]

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
      <div className="flex items-center gap-2 mb-3">
        <FiClock className="text-blue-600 dark:text-blue-400" size={17} />
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Sync & Data Freshness</h3>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="rounded-lg bg-gray-50 dark:bg-gray-900/60 p-3">
            <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
            <div className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100">{value}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
        Cloud data is downstream of local pharmacy installs. A device being seen is not the same as a fully healthy local till.
      </p>
    </div>
  )
}

function AttentionQueue({ items }: { items: CommandCenterAttentionItem[] }) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
      <div className="flex items-center gap-2 mb-3">
        <FiAlertTriangle className="text-amber-500" size={17} />
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Needs Attention Now</h3>
      </div>
      {items.length === 0 ? (
        <div className="rounded-lg bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 p-3 text-sm text-green-700 dark:text-green-300">
          No urgent fleet issues detected from current cloud data.
        </div>
      ) : (
        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {items.map((item, index) => (
            <div key={`${item.kind}-${item.device_id || item.branch_id || index}`} className={`border-l-4 rounded-lg p-3 ${severityTone(item.severity)}`}>
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{item.title}</div>
                <span className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{item.severity}</span>
              </div>
              <div className="mt-1 text-xs text-gray-600 dark:text-gray-300">{item.detail}</div>
              {(item.organization_name || item.branch_name) && (
                <div className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
                  {[item.organization_name, item.branch_name].filter(Boolean).join(' · ')}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function OrganizationPulse({ organizations }: { organizations: CommandCenterOrganizationSummary[] }) {
  if (!organizations.length) return null
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden mb-6">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Pharmacy Pulse</h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Revenue and sync posture by client from cloud-projected data.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900/60 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            <tr>
              <th className="text-left font-medium px-4 py-2">Pharmacy</th>
              <th className="text-left font-medium px-4 py-2">Sync</th>
              <th className="text-left font-medium px-4 py-2">Install</th>
              <th className="text-right font-medium px-4 py-2">Devices</th>
              <th className="text-right font-medium px-4 py-2">Today</th>
              <th className="text-right font-medium px-4 py-2">7 Days</th>
              <th className="text-right font-medium px-4 py-2">Issues</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {organizations.map(org => (
              <tr key={org.organization_id} className="hover:bg-gray-50 dark:hover:bg-gray-700/40">
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-900 dark:text-gray-100">{org.organization_name}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{org.branch_count} branches · last seen {formatDateTime(org.last_seen_at)}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${trustTone(org.sync_status)}`}>
                    {org.sync_status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${trustTone(org.readiness_status)}`}>
                    {org.readiness_status}
                  </span>
                  <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{formatDateTime(org.last_heartbeat_at)}</div>
                </td>
                <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-300">
                  {org.active_device_count}/{org.device_count}
                  {(org.stale_device_count || org.never_synced_device_count) ? (
                    <div className="text-xs text-red-500">{org.stale_device_count + org.never_synced_device_count} attention</div>
                  ) : null}
                  {(org.heartbeat_critical_count || org.heartbeat_warning_count || org.heartbeat_stale_count || org.heartbeat_missing_count) ? (
                    <div className="text-xs text-amber-600">
                      {org.heartbeat_critical_count + org.heartbeat_warning_count + org.heartbeat_stale_count + org.heartbeat_missing_count} health
                    </div>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-gray-100">{formatCurrency(org.today_revenue)}</td>
                <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-300">{formatCurrency(org.trailing_7d_revenue)}</td>
                <td className="px-4 py-3 text-right">
                  <span className={org.projection_failed_count ? 'text-red-500 font-semibold' : 'text-gray-500 dark:text-gray-400'}>
                    {org.projection_failed_count}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Device row ────────────────────────────────────────────────────────────────

function DeviceRow({
  device,
  onStatusToggle,
  onRotateToken,
}: {
  device: DeviceDetail
  onStatusToggle: (d: DeviceDetail) => void
  onRotateToken: (d: DeviceDetail) => void
}) {
  const age = syncAge(device.last_seen_at)
  const isActive = device.status === 'active'

  return (
    <div className="flex items-center gap-3 py-2 pl-12 pr-3 text-sm border-b border-gray-100 dark:border-gray-700 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/40">
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {age.healthy ? (
          <FiWifi size={14} className="text-green-500 shrink-0" />
        ) : (
          <FiWifiOff size={14} className="text-red-400 shrink-0" />
        )}
        <span className="font-medium text-gray-800 dark:text-gray-200 truncate">{device.name}</span>
        <span className="text-gray-400 dark:text-gray-500 text-xs truncate hidden sm:block">{device.device_uid.slice(0, 8)}…</span>
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${
        isActive
          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
          : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
      }`}>
        {device.status}
      </span>
      <span className={`text-xs shrink-0 ${age.healthy ? 'text-gray-500 dark:text-gray-400' : 'text-red-500 dark:text-red-400 font-medium'}`}>
        {age.label}
      </span>
      <button
        onClick={() => onStatusToggle(device)}
        title={isActive ? 'Disable device' : 'Enable device'}
        className="text-gray-400 hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-300 shrink-0"
      >
        {isActive ? <FiToggleRight size={18} className="text-green-500" /> : <FiToggleLeft size={18} />}
      </button>
      <button
        onClick={() => onRotateToken(device)}
        title="Rotate token"
        className="text-gray-400 hover:text-yellow-600 dark:text-gray-500 dark:hover:text-yellow-500 shrink-0"
      >
        <FiKey size={14} />
      </button>
    </div>
  )
}

// ── Client tree ───────────────────────────────────────────────────────────────

function ClientTree({
  orgs,
  devices,
  onStatusToggle,
  onRotateToken,
  onAddBranch,
  onAddDevice,
}: {
  orgs: OrgDetail[]
  devices: DeviceDetail[]
  onStatusToggle: (d: DeviceDetail) => void
  onRotateToken: (d: DeviceDetail) => void
  onAddBranch: (org: OrgDetail) => void
  onAddDevice: (org: OrgDetail) => void
}) {
  const [expandedOrgs, setExpandedOrgs] = useState<Set<number>>(new Set())

  function toggleOrg(id: number) {
    setExpandedOrgs(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  if (orgs.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400 dark:text-gray-500">
        No pharmacies provisioned yet. Click "Provision New Client" to get started.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {orgs.map(org => {
        const orgDevices = devices.filter(d => d.organization_id === org.id)
        const expanded = expandedOrgs.has(org.id)
        const hasStale = orgDevices.some(d => !syncAge(d.last_seen_at).healthy && d.status === 'active')

        return (
          <div key={org.id} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            {/* Org header */}
            <div
              className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 select-none"
              onClick={() => toggleOrg(org.id)}
            >
              {expanded
                ? <FiChevronDown size={14} className="text-gray-500 dark:text-gray-400 shrink-0" />
                : <FiChevronRight size={14} className="text-gray-500 dark:text-gray-400 shrink-0" />}
              <FiUsers size={16} className="text-blue-600 dark:text-blue-400 shrink-0" />
              <span className="font-semibold text-gray-900 dark:text-gray-100 flex-1">{org.name}</span>
              {hasStale && <FiAlertTriangle size={14} className="text-amber-500 shrink-0" title="One or more devices haven't synced in 24h" />}
              {!org.is_active && (
                <span className="text-xs bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-2 py-0.5 rounded-full">inactive</span>
              )}
              <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0">{org.branch_count}B · {org.device_count}D</span>
              <button
                onClick={e => { e.stopPropagation(); onAddDevice(org) }}
                className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 flex items-center gap-1 shrink-0 font-medium"
                title="Add device to this pharmacy"
              >
                <FiPlus size={12} /> Device
              </button>
            </div>

            {/* Devices */}
            {expanded && (
              <div className="bg-white dark:bg-gray-900">
                {orgDevices.length === 0 ? (
                  <div className="py-3 pl-12 text-sm text-gray-400 dark:text-gray-500">No devices provisioned</div>
                ) : (
                  orgDevices.map(d => (
                    <DeviceRow
                      key={d.id}
                      device={d}
                      onStatusToggle={onStatusToggle}
                      onRotateToken={onRotateToken}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Provision wizard ──────────────────────────────────────────────────────────

function ProvisionWizard({
  orgs,
  onClose,
  onDone,
}: {
  orgs: OrgDetail[]
  onClose: () => void
  onDone: () => void
}) {
  const [step, setStep] = useState<WizardStep>('org')
  const [loading, setLoading] = useState(false)

  // org step
  const [orgChoice, setOrgChoice] = useState<'existing' | 'new'>('new')
  const [selectedOrgId, setSelectedOrgId] = useState<number | ''>('')
  const [orgName, setOrgName] = useState('')
  const [orgPhone, setOrgPhone] = useState('')
  const [orgEmail, setOrgEmail] = useState('')

  // branch step
  const [branches, setBranches] = useState<BranchDetail[]>([])
  const [branchChoice, setBranchChoice] = useState<'existing' | 'new'>('new')
  const [selectedBranchId, setSelectedBranchId] = useState<number | ''>('')
  const [branchName, setBranchName] = useState('')
  const [branchCode, setBranchCode] = useState('')
  const [branchAddress, setBranchAddress] = useState('')

  // device step
  const [deviceName, setDeviceName] = useState('Main Till')

  // result
  const [provisioned, setProvisioned] = useState<DeviceProvisionResponse | null>(null)
  const [resolvedOrgId, setResolvedOrgId] = useState<number | null>(null)
  const [resolvedBranchId, setResolvedBranchId] = useState<number | null>(null)

  async function handleOrgNext() {
    setLoading(true)
    try {
      if (orgChoice === 'existing') {
        if (!selectedOrgId) { toast.error('Select an organization'); return }
        const orgId = Number(selectedOrgId)
        const branches = await api.getAdminBranches(orgId)
        setBranches(branches)
        setResolvedOrgId(orgId)
        setStep('branch')
      } else {
        if (!orgName.trim()) { toast.error('Organization name is required'); return }
        const org = await api.createAdminOrganization({
          name: orgName.trim(),
          contact_phone: orgPhone || null,
          contact_email: orgEmail || null,
        })
        setResolvedOrgId(org.id)
        setBranches([])
        setStep('branch')
      }
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Failed to create organization')
    } finally {
      setLoading(false)
    }
  }

  async function handleBranchNext() {
    setLoading(true)
    try {
      if (branchChoice === 'existing') {
        if (!selectedBranchId) { toast.error('Select a branch'); return }
        setResolvedBranchId(Number(selectedBranchId))
        setStep('device')
      } else {
        if (!branchName.trim() || !branchCode.trim()) { toast.error('Branch name and code are required'); return }
        const branch = await api.createAdminBranch(resolvedOrgId!, {
          name: branchName.trim(),
          code: branchCode.trim().toUpperCase(),
          address: branchAddress || null,
        })
        setResolvedBranchId(branch.id)
        setStep('device')
      }
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Failed to create branch')
    } finally {
      setLoading(false)
    }
  }

  async function handleProvisionDevice() {
    if (!deviceName.trim()) { toast.error('Device name is required'); return }
    setLoading(true)
    try {
      const device = await api.provisionAdminDevice(resolvedOrgId!, resolvedBranchId!, { name: deviceName.trim() })
      setProvisioned(device)
      setStep('done')
      onDone()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Failed to provision device')
    } finally {
      setLoading(false)
    }
  }

  const selectCls = 'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500'
  const backBtnCls = 'flex-1 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg py-2 text-sm'

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">Provision New Client</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-300">
            <FiX size={18} />
          </button>
        </div>

        {/* Step indicator */}
        {step !== 'done' && (
          <div className="flex gap-1 px-5 pt-4">
            {(['org', 'branch', 'device'] as const).map((s, i) => (
              <div key={s} className={`flex-1 h-1 rounded-full ${
                ['org', 'branch', 'device'].indexOf(step) >= i ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700'
              }`} />
            ))}
          </div>
        )}

        <div className="p-5 space-y-4">

          {/* Step 1: Organization */}
          {step === 'org' && (
            <>
              <p className="text-sm text-gray-500 dark:text-gray-400">Step 1 of 3 — Organization</p>
              {orgs.length > 0 && (
                <div className="flex gap-4 text-sm text-gray-700 dark:text-gray-300">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" checked={orgChoice === 'new'} onChange={() => setOrgChoice('new')} />
                    New pharmacy
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" checked={orgChoice === 'existing'} onChange={() => setOrgChoice('existing')} />
                    Add to existing
                  </label>
                </div>
              )}
              {orgChoice === 'existing' ? (
                <select
                  className={selectCls}
                  value={selectedOrgId}
                  onChange={e => setSelectedOrgId(Number(e.target.value))}
                >
                  <option value="">Select organization…</option>
                  {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              ) : (
                <>
                  <input
                    className="input text-sm"
                    placeholder="Pharmacy / organization name *"
                    value={orgName}
                    onChange={e => setOrgName(e.target.value)}
                  />
                  <input
                    className="input text-sm"
                    placeholder="Contact phone (optional)"
                    value={orgPhone}
                    onChange={e => setOrgPhone(e.target.value)}
                  />
                  <input
                    className="input text-sm"
                    placeholder="Contact email (optional)"
                    value={orgEmail}
                    onChange={e => setOrgEmail(e.target.value)}
                  />
                </>
              )}
              <button
                onClick={handleOrgNext}
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-60"
              >
                {loading ? 'Saving…' : 'Next →'}
              </button>
            </>
          )}

          {/* Step 2: Branch */}
          {step === 'branch' && (
            <>
              <p className="text-sm text-gray-500 dark:text-gray-400">Step 2 of 3 — Branch / Location</p>
              {branches.length > 0 && (
                <div className="flex gap-4 text-sm text-gray-700 dark:text-gray-300">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" checked={branchChoice === 'new'} onChange={() => setBranchChoice('new')} />
                    New branch
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" checked={branchChoice === 'existing'} onChange={() => setBranchChoice('existing')} />
                    Existing branch
                  </label>
                </div>
              )}
              {branchChoice === 'existing' && branches.length > 0 ? (
                <select
                  className={selectCls}
                  value={selectedBranchId}
                  onChange={e => setSelectedBranchId(Number(e.target.value))}
                >
                  <option value="">Select branch…</option>
                  {branches.map(b => <option key={b.id} value={b.id}>{b.name} ({b.code})</option>)}
                </select>
              ) : (
                <>
                  <input
                    className="input text-sm"
                    placeholder="Branch name (e.g. Main Branch) *"
                    value={branchName}
                    onChange={e => setBranchName(e.target.value)}
                  />
                  <input
                    className="input text-sm"
                    placeholder="Branch code (e.g. MAIN) *"
                    value={branchCode}
                    onChange={e => setBranchCode(e.target.value.toUpperCase())}
                  />
                  <input
                    className="input text-sm"
                    placeholder="Address (optional)"
                    value={branchAddress}
                    onChange={e => setBranchAddress(e.target.value)}
                  />
                </>
              )}
              <div className="flex gap-3">
                <button onClick={() => setStep('org')} className={backBtnCls}>
                  ← Back
                </button>
                <button
                  onClick={handleBranchNext}
                  disabled={loading}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-60"
                >
                  {loading ? 'Saving…' : 'Next →'}
                </button>
              </div>
            </>
          )}

          {/* Step 3: Device */}
          {step === 'device' && (
            <>
              <p className="text-sm text-gray-500 dark:text-gray-400">Step 3 of 3 — Device / Till</p>
              <input
                className="input text-sm"
                placeholder="Device name (e.g. Main Till) *"
                value={deviceName}
                onChange={e => setDeviceName(e.target.value)}
              />
              <div className="flex gap-3">
                <button onClick={() => setStep('branch')} className={backBtnCls}>
                  ← Back
                </button>
                <button
                  onClick={handleProvisionDevice}
                  disabled={loading}
                  className="flex-1 bg-green-600 hover:bg-green-700 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-60"
                >
                  {loading ? 'Provisioning…' : 'Provision Device'}
                </button>
              </div>
            </>
          )}

          {/* Done: show env block */}
          {step === 'done' && provisioned && (
            <>
              <div className="flex items-center gap-2 text-green-700 dark:text-green-400 font-medium text-sm">
                <FiCheckCircle size={16} /> Device provisioned successfully
              </div>
              <p className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-3">
                The sync token below is shown <strong>once only</strong> and is not stored server-side.
                Copy the env block and paste it into <code>backend\.env</code> on the client machine.
              </p>
              <div className="relative">
                <pre className="bg-gray-900 text-green-400 text-xs rounded-lg p-4 overflow-x-auto whitespace-pre-wrap">
                  {provisioned.env_block}
                </pre>
                <button
                  onClick={() => copyToClipboard(provisioned.env_block)}
                  className="absolute top-2 right-2 bg-gray-700 hover:bg-gray-600 text-white rounded p-1.5"
                  title="Copy env block"
                >
                  <FiCopy size={13} />
                </button>
              </div>
              <button
                onClick={onClose}
                className="w-full bg-gray-800 hover:bg-gray-900 text-white rounded-lg py-2 text-sm font-medium"
              >
                Done
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Rotate token dialog ───────────────────────────────────────────────────────

function RotateTokenDialog({
  device,
  onClose,
}: {
  device: DeviceDetail
  onClose: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DeviceProvisionResponse | null>(null)

  async function handleRotate() {
    setLoading(true)
    try {
      const result = await api.rotateAdminDeviceToken(device.id)
      setResult(result)
      toast.success('Token rotated — update the client machine')
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Failed to rotate token')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">Rotate Token — {device.name}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-300">
            <FiX size={18} />
          </button>
        </div>
        {!result ? (
          <>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              This will immediately invalidate the current token. The client machine will fail to sync
              until you update <code className="text-xs bg-gray-100 dark:bg-gray-700 dark:text-gray-300 px-1 rounded">backend\.env</code> with the new token.
            </p>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="flex-1 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg py-2 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleRotate}
                disabled={loading}
                className="flex-1 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-60"
              >
                {loading ? 'Rotating…' : 'Rotate Token'}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-3">
              Token rotated. Copy the new env block and restart the backend on the client machine.
            </p>
            <div className="relative">
              <pre className="bg-gray-900 text-green-400 text-xs rounded-lg p-4 overflow-x-auto whitespace-pre-wrap">
                {result.env_block}
              </pre>
              <button
                onClick={() => copyToClipboard(result.env_block)}
                className="absolute top-2 right-2 bg-gray-700 hover:bg-gray-600 text-white rounded p-1.5"
                title="Copy"
              >
                <FiCopy size={13} />
              </button>
            </div>
            <button onClick={onClose} className="w-full bg-gray-800 hover:bg-gray-900 text-white rounded-lg py-2 text-sm font-medium">
              Done
            </button>
          </>
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ClientsPage() {
  const [orgs, setOrgs] = useState<OrgDetail[]>([])
  const [devices, setDevices] = useState<DeviceDetail[]>([])
  const [commandCenter, setCommandCenter] = useState<AdminCommandCenter | null>(null)
  const [loading, setLoading] = useState(true)
  const [showWizard, setShowWizard] = useState(false)
  const [rotateTarget, setRotateTarget] = useState<DeviceDetail | null>(null)

  async function loadData() {
    setLoading(true)
    try {
      const [orgs, devices, command] = await Promise.all([
        api.getAdminOrganizations(),
        api.getAdminDevices(),
        api.getAdminCommandCenter(),
      ])
      setOrgs(orgs)
      setDevices(devices)
      setCommandCenter(command)
    } catch {
      toast.error('Failed to load client data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  async function handleStatusToggle(device: DeviceDetail) {
    const newStatus = device.status === 'active' ? 'disabled' : 'active'
    const label = newStatus === 'disabled' ? 'Disable' : 'Enable'
    if (!confirm(`${label} device "${device.name}"?`)) return
    try {
      await api.updateAdminDeviceStatus(device.id, newStatus)
      toast.success(`Device ${newStatus}`)
      await loadData()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Failed to update device status')
    }
  }

  function handleAddDevice(_org: OrgDetail) {
    setShowWizard(true)
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Client Command Center</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Admin-only view for provisioning, monitoring, and fleet intelligence</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 border border-gray-300 dark:border-gray-600 rounded-lg"
            title="Refresh"
          >
            <FiRefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setShowWizard(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            <FiPlus size={15} /> Provision New Client
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500 text-sm">Loading…</div>
      ) : (
        <>
          {commandCenter && <CommandCenterOverview command={commandCenter} />}
          {commandCenter && <OrganizationPulse organizations={commandCenter.organizations} />}
          <StatsBar orgs={orgs} devices={devices} />
          <ClientTree
            orgs={orgs}
            devices={devices}
            onStatusToggle={handleStatusToggle}
            onRotateToken={d => setRotateTarget(d)}
            onAddBranch={() => setShowWizard(true)}
            onAddDevice={handleAddDevice}
          />
        </>
      )}

      {showWizard && (
        <ProvisionWizard
          orgs={orgs}
          onClose={() => setShowWizard(false)}
          onDone={loadData}
        />
      )}

      {rotateTarget && (
        <RotateTokenDialog
          device={rotateTarget}
          onClose={() => { setRotateTarget(null); loadData() }}
        />
      )}
    </div>
  )
}
