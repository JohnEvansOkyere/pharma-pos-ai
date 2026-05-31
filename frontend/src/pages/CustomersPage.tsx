/**
 * Customers page — registered customer list with profile drill-down.
 * Only meaningful in online_pos mode.
 */
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import {
  FiCheck,
  FiChevronRight,
  FiMessageSquare,
  FiSearch,
  FiUser,
  FiUserPlus,
  FiX,
} from 'react-icons/fi'
import { api } from '../services/api'

interface Customer {
  id: number
  full_name: string
  phone: string
  email?: string
  date_of_birth?: string
  gender?: string
  town?: string
  region?: string
  known_allergies?: string
  chronic_conditions?: string
  notes?: string
  sms_consent: string
  whatsapp_consent: string
  preferred_channel: string
  is_active: boolean
  created_at: string
  total_purchases?: number
}

interface FollowUp {
  id: number
  sale_id: number
  scheduled_at: string
  channel: string
  status: string
  sent_at?: string
  message_text?: string
}

const CONSENT_COLOR: Record<string, string> = {
  granted: '#16a34a',
  declined: '#dc2626',
  pending: '#d97706',
}
const CONSENT_LABEL: Record<string, string> = {
  granted: 'Granted',
  declined: 'Declined',
  pending: 'Pending',
}

function ConsentBadge({ value }: { value: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999,
      background: `${CONSENT_COLOR[value] || '#6b7280'}22`,
      color: CONSENT_COLOR[value] || '#6b7280',
    }}>
      {value === 'granted' && <FiCheck style={{ width: 10, height: 10 }} />}
      {value === 'declined' && <FiX style={{ width: 10, height: 10 }} />}
      {CONSENT_LABEL[value] || value}
    </span>
  )
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selected, setSelected] = useState<Customer | null>(null)
  const [followUps, setFollowUps] = useState<FollowUp[]>([])
  const [isLoadingFollowUps, setIsLoadingFollowUps] = useState(false)

  useEffect(() => {
    loadCustomers()
  }, [])

  const loadCustomers = async () => {
    setIsLoading(true)
    try {
      const data = await api.getCustomers({ limit: 200 })
      setCustomers(data)
    } catch {
      toast.error('Failed to load customers')
    } finally {
      setIsLoading(false)
    }
  }

  const openProfile = async (c: Customer) => {
    setSelected(c)
    setIsLoadingFollowUps(true)
    try {
      const data = await api.getCustomerFollowUps(c.id)
      setFollowUps(data)
    } catch {
      setFollowUps([])
    } finally {
      setIsLoadingFollowUps(false)
    }
  }

  const filtered = customers.filter(c =>
    c.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.phone.includes(searchQuery)
  )

  const totalGrantedSMS = customers.filter(c => c.sms_consent === 'granted').length
  const totalGrantedWA  = customers.filter(c => c.whatsapp_consent === 'granted').length

  return (
    <div style={{ display: 'flex', gap: 20, height: 'calc(100vh - 9rem)', minHeight: 600 }}>
      {/* ── Left: customer list ─────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
        <div className="card" style={{ padding: '18px 20px', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }} className="text-gray-900 dark:text-gray-100">
                Customers
              </h1>
              <p style={{ margin: '4px 0 0', fontSize: 13 }} className="text-gray-500 dark:text-gray-400">
                {customers.length} registered · {totalGrantedSMS} SMS consent · {totalGrantedWA} WhatsApp consent
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {[
                { label: 'Total', value: customers.length, color: '#4f46e5' },
                { label: 'SMS ✓', value: totalGrantedSMS, color: '#16a34a' },
                { label: 'WA ✓', value: totalGrantedWA, color: '#0ea5e9' },
              ].map(s => (
                <div key={s.label} style={{ textAlign: 'center', background: `${s.color}11`, border: `1px solid ${s.color}33`, borderRadius: 8, padding: '8px 16px' }}>
                  <p style={{ margin: 0, fontSize: 18, fontWeight: 700, color: s.color }}>{s.value}</p>
                  <p style={{ margin: 0, fontSize: 11, color: s.color, opacity: 0.8 }}>{s.label}</p>
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 14, position: 'relative' }}>
            <FiSearch style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#9ca3af', width: 16, height: 16 }} />
            <input
              className="input"
              style={{ paddingLeft: 38 }}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search by name or phone…"
            />
          </div>
        </div>

        <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {isLoading ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }} className="text-gray-400">
              Loading…
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8 }} className="text-gray-400">
              <FiUser style={{ width: 40, height: 40 }} />
              <p style={{ margin: 0, fontSize: 14, fontWeight: 500 }} className="text-gray-700 dark:text-gray-300">No customers found</p>
              <p style={{ margin: 0, fontSize: 13 }}>Register customers from the POS screen during a sale.</p>
            </div>
          ) : (
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {filtered.map(c => (
                <button
                  key={c.id}
                  onClick={() => openProfile(c)}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: 14,
                    padding: '12px 20px', borderBottom: '1px solid #e5e7eb',
                    background: selected?.id === c.id ? '#ede9fe' : 'transparent',
                    cursor: 'pointer', textAlign: 'left', border: 'none',
                  }}
                  className={`hover:bg-gray-50 dark:hover:bg-gray-700/40 ${selected?.id === c.id ? 'dark:bg-indigo-900/20' : ''}`}
                >
                  <div style={{
                    width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
                    background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
                    color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: 16,
                  }}>
                    {c.full_name.charAt(0).toUpperCase()}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ margin: 0, fontWeight: 600, fontSize: 14 }} className="text-gray-900 dark:text-gray-100 truncate">
                      {c.full_name}
                    </p>
                    <p style={{ margin: 0, fontSize: 12 }} className="text-gray-500 dark:text-gray-400">
                      {c.phone}{c.town ? ` · ${c.town}` : ''}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexShrink: 0, alignItems: 'center' }}>
                    <ConsentBadge value={c.sms_consent} />
                    {c.total_purchases !== undefined && (
                      <span style={{ fontSize: 12, color: '#9ca3af' }}>{c.total_purchases} sales</span>
                    )}
                    <FiChevronRight style={{ color: '#9ca3af', width: 16 }} />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Right: customer profile panel ───────────────────────────────── */}
      {selected ? (
        <div className="card" style={{ width: 360, flexShrink: 0, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
          <div style={{ padding: '18px 20px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }} className="text-gray-900 dark:text-gray-100">
              Profile
            </h2>
            <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af' }}>
              <FiX />
            </button>
          </div>

          <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 18 }}>
            {/* Identity */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'linear-gradient(135deg, #4f46e5, #7c3aed)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 22, flexShrink: 0 }}>
                {selected.full_name.charAt(0).toUpperCase()}
              </div>
              <div>
                <p style={{ margin: 0, fontWeight: 700, fontSize: 17 }} className="text-gray-900 dark:text-gray-100">{selected.full_name}</p>
                <p style={{ margin: 0, fontSize: 13 }} className="text-gray-500">{selected.phone}</p>
                {selected.email && <p style={{ margin: 0, fontSize: 12 }} className="text-gray-400">{selected.email}</p>}
              </div>
            </div>

            {/* Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div style={{ background: '#f5f3ff', borderRadius: 8, padding: '10px 14px', textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: 22, fontWeight: 700, color: '#4f46e5' }}>{selected.total_purchases ?? '—'}</p>
                <p style={{ margin: 0, fontSize: 11, color: '#7c3aed' }}>Total Purchases</p>
              </div>
              <div style={{ background: '#f0fdf4', borderRadius: 8, padding: '10px 14px', textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: 22, fontWeight: 700, color: '#16a34a' }}>{followUps.filter(f => f.status === 'sent' || f.status === 'delivered').length}</p>
                <p style={{ margin: 0, fontSize: 11, color: '#16a34a' }}>Follow-ups Sent</p>
              </div>
            </div>

            {/* Consent */}
            <div>
              <p style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 600 }} className="text-gray-700 dark:text-gray-300">Communication Consent</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { label: 'SMS', value: selected.sms_consent },
                  { label: 'WhatsApp', value: selected.whatsapp_consent },
                ].map(row => (
                  <div key={row.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }} className="text-gray-600 dark:text-gray-400">{row.label}</span>
                    <ConsentBadge value={row.value} />
                  </div>
                ))}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 13 }} className="text-gray-600 dark:text-gray-400">Preferred channel</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#4f46e5', textTransform: 'capitalize' }}>{selected.preferred_channel}</span>
                </div>
              </div>
            </div>

            {/* Health notes */}
            {(selected.known_allergies || selected.chronic_conditions) && (
              <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: 12 }}>
                <p style={{ margin: '0 0 6px', fontSize: 12, fontWeight: 700, color: '#c2410c' }}>⚠ Health Notes</p>
                {selected.known_allergies && <p style={{ margin: '0 0 4px', fontSize: 12, color: '#7c2d12' }}><strong>Allergies:</strong> {selected.known_allergies}</p>}
                {selected.chronic_conditions && <p style={{ margin: 0, fontSize: 12, color: '#7c2d12' }}><strong>Conditions:</strong> {selected.chronic_conditions}</p>}
              </div>
            )}

            {/* Follow-ups */}
            <div>
              <p style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }} className="text-gray-700 dark:text-gray-300">
                <FiMessageSquare style={{ width: 14, height: 14 }} />
                Follow-up History
              </p>
              {isLoadingFollowUps ? (
                <p style={{ fontSize: 13, color: '#9ca3af' }}>Loading…</p>
              ) : followUps.length === 0 ? (
                <p style={{ fontSize: 13, color: '#9ca3af' }}>No follow-ups yet.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {followUps.slice(0, 10).map(f => (
                    <div key={f.id} style={{
                      border: '1px solid #e5e7eb', borderRadius: 8, padding: '8px 12px',
                      borderLeft: `3px solid ${f.status === 'sent' || f.status === 'delivered' ? '#16a34a' : f.status === 'failed' ? '#dc2626' : f.status === 'skipped' ? '#9ca3af' : '#d97706'}`,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 12, fontWeight: 600, textTransform: 'capitalize', color: '#374151' }}>{f.status}</span>
                        <span style={{ fontSize: 11, color: '#9ca3af' }}>{f.channel}</span>
                      </div>
                      <p style={{ margin: '4px 0 0', fontSize: 11, color: '#6b7280' }}>
                        Scheduled: {new Date(f.scheduled_at).toLocaleDateString('en-GB')}
                        {f.sent_at && ` · Sent: ${new Date(f.sent_at).toLocaleDateString('en-GB')}`}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ width: 360, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10 }}>
          <FiUserPlus style={{ width: 40, height: 40, color: '#d1d5db' }} />
          <p style={{ margin: 0, fontSize: 14, color: '#9ca3af' }}>Select a customer to view their profile</p>
        </div>
      )}
    </div>
  )
}
