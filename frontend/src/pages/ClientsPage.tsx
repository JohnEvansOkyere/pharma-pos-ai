import { useEffect, useState } from 'react'
import {
  FiActivity,
  FiAlertTriangle,
  FiCheckCircle,
  FiChevronDown,
  FiChevronRight,
  FiCopy,
  FiKey,
  FiPlus,
  FiRefreshCw,
  FiServer,
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
  status: 'active' | 'disabled'
  last_seen_at: string | null
  created_at: string
  organization_name: string | null
  branch_name: string | null
}

interface DeviceProvisionResponse extends DeviceDetail {
  raw_token: string
  env_block: string
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
        <div key={s.label} className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-3">
          <s.icon className="text-blue-600 shrink-0" size={20} />
          <div>
            <div className="text-2xl font-bold text-gray-900">{s.value}</div>
            <div className="text-xs text-gray-500">{s.label}</div>
          </div>
        </div>
      ))}
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
    <div className="flex items-center gap-3 py-2 pl-12 pr-3 text-sm border-b border-gray-100 last:border-0 hover:bg-gray-50">
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {age.healthy ? (
          <FiWifi size={14} className="text-green-500 shrink-0" />
        ) : (
          <FiWifiOff size={14} className="text-red-400 shrink-0" />
        )}
        <span className="font-medium text-gray-800 truncate">{device.name}</span>
        <span className="text-gray-400 text-xs truncate hidden sm:block">{device.device_uid.slice(0, 8)}…</span>
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${
        isActive ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
      }`}>
        {device.status}
      </span>
      <span className={`text-xs shrink-0 ${age.healthy ? 'text-gray-500' : 'text-red-500 font-medium'}`}>
        {age.label}
      </span>
      <button
        onClick={() => onStatusToggle(device)}
        title={isActive ? 'Disable device' : 'Enable device'}
        className="text-gray-400 hover:text-gray-700 shrink-0"
      >
        {isActive ? <FiToggleRight size={18} className="text-green-500" /> : <FiToggleLeft size={18} />}
      </button>
      <button
        onClick={() => onRotateToken(device)}
        title="Rotate token"
        className="text-gray-400 hover:text-yellow-600 shrink-0"
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
      <div className="text-center py-12 text-gray-400">
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
          <div key={org.id} className="border border-gray-200 rounded-lg overflow-hidden">
            {/* Org header */}
            <div
              className="flex items-center gap-3 p-3 bg-gray-50 cursor-pointer hover:bg-gray-100 select-none"
              onClick={() => toggleOrg(org.id)}
            >
              {expanded ? <FiChevronDown size={14} className="text-gray-500 shrink-0" /> : <FiChevronRight size={14} className="text-gray-500 shrink-0" />}
              <FiUsers size={16} className="text-blue-600 shrink-0" />
              <span className="font-semibold text-gray-900 flex-1">{org.name}</span>
              {hasStale && <FiAlertTriangle size={14} className="text-amber-500 shrink-0" title="One or more devices haven't synced in 24h" />}
              {!org.is_active && <span className="text-xs bg-gray-200 text-gray-500 px-2 py-0.5 rounded-full">inactive</span>}
              <span className="text-xs text-gray-400 shrink-0">{org.branch_count}B · {org.device_count}D</span>
              <button
                onClick={e => { e.stopPropagation(); onAddDevice(org) }}
                className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 shrink-0 font-medium"
                title="Add device to this pharmacy"
              >
                <FiPlus size={12} /> Device
              </button>
            </div>

            {/* Devices */}
            {expanded && (
              <div>
                {orgDevices.length === 0 ? (
                  <div className="py-3 pl-12 text-sm text-gray-400">No devices provisioned</div>
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

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">Provision New Client</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><FiX size={18} /></button>
        </div>

        {/* Step indicator */}
        {step !== 'done' && (
          <div className="flex gap-1 px-5 pt-4">
            {(['org', 'branch', 'device'] as const).map((s, i) => (
              <div key={s} className={`flex-1 h-1 rounded-full ${
                ['org', 'branch', 'device'].indexOf(step) >= i ? 'bg-blue-600' : 'bg-gray-200'
              }`} />
            ))}
          </div>
        )}

        <div className="p-5 space-y-4">

          {/* Step 1: Organization */}
          {step === 'org' && (
            <>
              <p className="text-sm text-gray-500">Step 1 of 3 — Organization</p>
              {orgs.length > 0 && (
                <div className="flex gap-4 text-sm">
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
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={selectedOrgId}
                  onChange={e => setSelectedOrgId(Number(e.target.value))}
                >
                  <option value="">Select organization…</option>
                  {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              ) : (
                <>
                  <input
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Pharmacy / organization name *"
                    value={orgName}
                    onChange={e => setOrgName(e.target.value)}
                  />
                  <input
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Contact phone (optional)"
                    value={orgPhone}
                    onChange={e => setOrgPhone(e.target.value)}
                  />
                  <input
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              <p className="text-sm text-gray-500">Step 2 of 3 — Branch / Location</p>
              {branches.length > 0 && (
                <div className="flex gap-4 text-sm">
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
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={selectedBranchId}
                  onChange={e => setSelectedBranchId(Number(e.target.value))}
                >
                  <option value="">Select branch…</option>
                  {branches.map(b => <option key={b.id} value={b.id}>{b.name} ({b.code})</option>)}
                </select>
              ) : (
                <>
                  <input
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Branch name (e.g. Main Branch) *"
                    value={branchName}
                    onChange={e => setBranchName(e.target.value)}
                  />
                  <input
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Branch code (e.g. MAIN) *"
                    value={branchCode}
                    onChange={e => setBranchCode(e.target.value.toUpperCase())}
                  />
                  <input
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Address (optional)"
                    value={branchAddress}
                    onChange={e => setBranchAddress(e.target.value)}
                  />
                </>
              )}
              <div className="flex gap-3">
                <button onClick={() => setStep('org')} className="flex-1 border border-gray-300 hover:bg-gray-50 rounded-lg py-2 text-sm">
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
              <p className="text-sm text-gray-500">Step 3 of 3 — Device / Till</p>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Device name (e.g. Main Till) *"
                value={deviceName}
                onChange={e => setDeviceName(e.target.value)}
              />
              <div className="flex gap-3">
                <button onClick={() => setStep('branch')} className="flex-1 border border-gray-300 hover:bg-gray-50 rounded-lg py-2 text-sm">
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
              <div className="flex items-center gap-2 text-green-700 font-medium text-sm">
                <FiCheckCircle size={16} /> Device provisioned successfully
              </div>
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
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
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">Rotate Token — {device.name}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><FiX size={18} /></button>
        </div>
        {!result ? (
          <>
            <p className="text-sm text-gray-600">
              This will immediately invalidate the current token. The client machine will fail to sync
              until you update <code className="text-xs bg-gray-100 px-1 rounded">backend\.env</code> with the new token.
            </p>
            <div className="flex gap-3">
              <button onClick={onClose} className="flex-1 border border-gray-300 hover:bg-gray-50 rounded-lg py-2 text-sm">
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
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
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
  const [loading, setLoading] = useState(true)
  const [showWizard, setShowWizard] = useState(false)
  const [rotateTarget, setRotateTarget] = useState<DeviceDetail | null>(null)

  async function loadData() {
    setLoading(true)
    try {
      const [orgs, devices] = await Promise.all([
        api.getAdminOrganizations(),
        api.getAdminDevices(),
      ])
      setOrgs(orgs)
      setDevices(devices)
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

  function handleAddDevice(org: OrgDetail) {
    setShowWizard(true)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Client Management</h1>
          <p className="text-sm text-gray-500 mt-0.5">Provision and monitor pharmacy installations</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            className="p-2 text-gray-500 hover:text-gray-800 border border-gray-300 rounded-lg"
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
        <div className="text-center py-16 text-gray-400 text-sm">Loading…</div>
      ) : (
        <>
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
