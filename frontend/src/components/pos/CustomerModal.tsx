/**
 * Customer registration and search modal for the POS.
 *
 * Shown in online_pos mode only. The cashier can:
 *   - Search for existing customers by name or phone
 *   - Register a new customer on the spot
 *   - Capture SMS/WhatsApp consent at registration time
 *   - Link the selected customer to the current sale
 */
import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import {
  FiCheck,
  FiSearch,
  FiUser,
  FiUserPlus,
  FiX,
} from 'react-icons/fi'
import { api } from '../../services/api'

export interface LinkedCustomer {
  id: number
  full_name: string
  phone: string
  sms_consent: string
  whatsapp_consent: string
}

interface Props {
  onLink: (customer: LinkedCustomer | null) => void
  linked: LinkedCustomer | null
  onClose: () => void
}

type Mode = 'search' | 'register'

const CONSENT_OPTS = [
  { value: 'granted', label: 'Yes, I agree' },
  { value: 'declined', label: 'No thanks' },
  { value: 'pending', label: 'Ask later' },
]

export default function CustomerModal({ onLink, linked, onClose }: Props) {
  const [mode, setMode] = useState<Mode>('search')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<LinkedCustomer[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Registration form state
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [smsConsent, setSmsConsent] = useState('pending')
  const [whatsappConsent, setWhatsappConsent] = useState('pending')
  const [preferredChannel, setPreferredChannel] = useState('sms')

  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    searchRef.current?.focus()
  }, [mode])

  useEffect(() => {
    const id = window.setTimeout(async () => {
      const q = searchQuery.trim()
      if (q.length < 2) {
        setSearchResults([])
        return
      }
      setIsSearching(true)
      try {
        const results = await api.searchCustomers(q)
        setSearchResults(results)
      } catch {
        setSearchResults([])
      } finally {
        setIsSearching(false)
      }
    }, 250)
    return () => window.clearTimeout(id)
  }, [searchQuery])

  const handleSelect = (c: LinkedCustomer) => {
    onLink(c)
    toast.success(`${c.full_name} linked to this sale`)
    onClose()
  }

  const handleRegister = async () => {
    if (!fullName.trim()) { toast.error('Full name required'); return }
    if (!phone.trim()) { toast.error('Phone required'); return }
    setIsSaving(true)
    try {
      const customer = await api.registerCustomer({
        full_name: fullName.trim(),
        phone: phone.trim(),
        sms_consent: smsConsent,
        whatsapp_consent: whatsappConsent,
        preferred_channel: preferredChannel,
      })
      onLink({ id: customer.id, full_name: customer.full_name, phone: customer.phone, sms_consent: customer.sms_consent, whatsapp_consent: customer.whatsapp_consent })
      toast.success(`${customer.full_name} registered and linked`)
      onClose()
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error('A customer with this phone is already registered — try searching.')
      } else {
        toast.error(err?.response?.data?.detail || 'Registration failed')
      }
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        style={{
          background: 'white', borderRadius: 14, width: '100%', maxWidth: 500,
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          overflow: 'hidden',
        }}
        className="dark:bg-gray-800"
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 20px', borderBottom: '1px solid #e5e7eb' }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => setMode('search')}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px',
                borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 14,
                background: mode === 'search' ? '#4f46e5' : 'transparent',
                color: mode === 'search' ? 'white' : '#6b7280',
              }}
            >
              <FiSearch style={{ width: 14, height: 14 }} />
              Search
            </button>
            <button
              onClick={() => setMode('register')}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px',
                borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 14,
                background: mode === 'register' ? '#4f46e5' : 'transparent',
                color: mode === 'register' ? 'white' : '#6b7280',
              }}
            >
              <FiUserPlus style={{ width: 14, height: 14 }} />
              Register New
            </button>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af' }}>
            <FiX style={{ width: 20, height: 20 }} />
          </button>
        </div>

        <div style={{ padding: '20px' }}>
          {/* ── Search mode ────────────────────────────────────── */}
          {mode === 'search' && (
            <>
              {linked && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '10px 14px', marginBottom: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <FiUser style={{ color: '#16a34a', flexShrink: 0 }} />
                    <div>
                      <p style={{ fontSize: 14, fontWeight: 600, color: '#15803d', margin: 0 }}>{linked.full_name}</p>
                      <p style={{ fontSize: 12, color: '#4ade80', margin: 0 }}>{linked.phone} · Linked</p>
                    </div>
                  </div>
                  <button
                    onClick={() => { onLink(null); toast('Customer unlinked') }}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', fontSize: 13 }}
                  >
                    Unlink
                  </button>
                </div>
              )}

              <label style={{ position: 'relative', display: 'block' }}>
                <FiSearch style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#9ca3af', width: 16, height: 16 }} />
                <input
                  ref={searchRef}
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder="Search by name or phone…"
                  className="input"
                  style={{ paddingLeft: 38 }}
                />
              </label>

              <div style={{ marginTop: 12, maxHeight: 280, overflowY: 'auto' }}>
                {isSearching && <p style={{ color: '#9ca3af', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>Searching…</p>}
                {!isSearching && searchQuery.length >= 2 && searchResults.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '24px 0' }}>
                    <p style={{ color: '#374151', fontSize: 14, fontWeight: 500 }}>No customers found</p>
                    <button onClick={() => setMode('register')} style={{ marginTop: 8, color: '#4f46e5', background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
                      Register new customer →
                    </button>
                  </div>
                )}
                {searchResults.map(c => (
                  <button
                    key={c.id}
                    onClick={() => handleSelect(c)}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 12px', borderRadius: 8, border: '1px solid #e5e7eb', marginBottom: 6,
                      background: linked?.id === c.id ? '#ede9fe' : 'white', cursor: 'pointer', textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#4f46e5', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 14, flexShrink: 0 }}>
                        {c.full_name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p style={{ margin: 0, fontWeight: 600, fontSize: 14, color: '#111827' }}>{c.full_name}</p>
                        <p style={{ margin: 0, fontSize: 12, color: '#6b7280' }}>{c.phone}</p>
                      </div>
                    </div>
                    {linked?.id === c.id && <FiCheck style={{ color: '#4f46e5', flexShrink: 0 }} />}
                  </button>
                ))}
              </div>
            </>
          )}

          {/* ── Register mode ───────────────────────────────────── */}
          {mode === 'register' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <label>
                  <span className="label">Full Name *</span>
                  <input className="input" value={fullName} onChange={e => setFullName(e.target.value)} placeholder="e.g. Kofi Mensah" />
                </label>
                <label>
                  <span className="label">Phone *</span>
                  <input className="input" value={phone} onChange={e => setPhone(e.target.value)} placeholder="e.g. 0244123456" />
                </label>
              </div>

              <div style={{ background: '#f9fafb', borderRadius: 10, padding: '14px', border: '1px solid #e5e7eb' }}>
                <p style={{ margin: '0 0 10px', fontWeight: 600, fontSize: 13, color: '#374151' }}>
                  Communication Consent
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <label>
                    <span className="label" style={{ fontSize: 12 }}>SMS updates</span>
                    <select className="input" value={smsConsent} onChange={e => setSmsConsent(e.target.value)}>
                      {CONSENT_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </label>
                  <label>
                    <span className="label" style={{ fontSize: 12 }}>WhatsApp</span>
                    <select className="input" value={whatsappConsent} onChange={e => setWhatsappConsent(e.target.value)}>
                      {CONSENT_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </label>
                </div>
                <label style={{ marginTop: 10, display: 'block' }}>
                  <span className="label" style={{ fontSize: 12 }}>Preferred channel</span>
                  <select className="input" value={preferredChannel} onChange={e => setPreferredChannel(e.target.value)}>
                    <option value="sms">SMS</option>
                    <option value="whatsapp">WhatsApp</option>
                  </select>
                </label>
                <p style={{ marginTop: 8, fontSize: 11, color: '#9ca3af' }}>
                  By selecting "Yes, I agree" the customer consents to receive purchase receipts and health follow-up messages from this pharmacy. They may opt out at any time by replying STOP.
                </p>
              </div>

              <button
                onClick={handleRegister}
                disabled={isSaving}
                className="btn-primary"
                style={{ width: '100%', height: 44, fontSize: 15 }}
              >
                {isSaving ? 'Registering…' : 'Register & Link to Sale'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
