/**
 * Customer Analytics Page — Phase D.
 * Retention KPIs, consent rates, churn funnel, top customers, and product affinity.
 * Visible in online_pos mode only (Customers nav group).
 */
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import {
  FiActivity,
  FiAlertTriangle,
  FiAward,
  FiMessageSquare,
  FiRefreshCw,
  FiTrendingDown,
  FiTrendingUp,
  FiUser,
  FiUserCheck,
  FiUserX,
} from 'react-icons/fi'
import { api } from '../services/api'

interface AnalyticsSummary {
  organization_id: number
  branch_id?: number
  period_days: number
  generated_at: string
  total_customers: number
  new_customers_in_period: number
  repeat_customers: number
  repeat_rate_pct: number
  at_risk_customers: number
  churned_customers: number
  consent_stats: {
    sms_granted: number
    whatsapp_granted: number
    sms_rate_pct: number
  }
  follow_up_stats: {
    sent: number
    pending: number
    failed: number
  }
  top_customers: Array<{
    customer_id: number
    full_name: string
    phone: string
    purchase_count: number
    total_spend: number
    last_purchase_at?: string
  }>
  top_products_by_customer_reach: Array<{
    product_id: number
    product_name: string
    distinct_customers: number
    total_units_sold: number
  }>
}

const PERIOD_OPTS = [
  { label: '7 days',  value: 7 },
  { label: '30 days', value: 30 },
  { label: '60 days', value: 60 },
  { label: '90 days', value: 90 },
]

function KpiCard({
  label, value, sub, icon: Icon, color, trend,
}: {
  label: string
  value: string | number
  sub?: string
  icon: React.ElementType
  color: string
  trend?: 'up' | 'down' | 'neutral'
}) {
  return (
    <div className="card" style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <p style={{ margin: 0, fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#9ca3af' }}>{label}</p>
          <p style={{ margin: '6px 0 0', fontSize: 28, fontWeight: 700, color }}>{value}</p>
          {sub && <p style={{ margin: '2px 0 0', fontSize: 12, color: '#9ca3af' }}>{sub}</p>}
        </div>
        <div style={{ width: 44, height: 44, borderRadius: 10, background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Icon style={{ width: 20, height: 20, color }} />
        </div>
      </div>
      {trend && (
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
          {trend === 'up' && <FiTrendingUp style={{ width: 12, height: 12, color: '#16a34a' }} />}
          {trend === 'down' && <FiTrendingDown style={{ width: 12, height: 12, color: '#dc2626' }} />}
        </div>
      )}
    </div>
  )
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div style={{ height: 6, background: '#e5e7eb', borderRadius: 99, overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 99, transition: 'width 0.5s ease' }} />
    </div>
  )
}

export default function CustomerAnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [periodDays, setPeriodDays] = useState(30)

  useEffect(() => {
    load()
  }, [periodDays])

  const load = async () => {
    setIsLoading(true)
    try {
      const result = await api.getCustomerAnalytics(periodDays)
      setData(result)
    } catch {
      toast.error('Failed to load customer analytics')
    } finally {
      setIsLoading(false)
    }
  }

  const healthy = data ? data.total_customers - data.at_risk_customers - data.churned_customers : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div className="card" style={{ padding: '18px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }} className="text-gray-900 dark:text-gray-100">
              Customer Analytics
            </h1>
            <p style={{ margin: '4px 0 0', fontSize: 13 }} className="text-gray-500 dark:text-gray-400">
              Retention, churn, and engagement metrics
              {data && <> · Generated {new Date(data.generated_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}</>}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <div style={{ display: 'flex', background: '#f3f4f6', borderRadius: 8, padding: 3, gap: 2 }}>
              {PERIOD_OPTS.map(o => (
                <button
                  key={o.value}
                  onClick={() => setPeriodDays(o.value)}
                  style={{
                    padding: '4px 12px', borderRadius: 6, border: 'none', cursor: 'pointer',
                    fontWeight: 600, fontSize: 12,
                    background: periodDays === o.value ? '#4f46e5' : 'transparent',
                    color: periodDays === o.value ? 'white' : '#6b7280',
                  }}
                >
                  {o.label}
                </button>
              ))}
            </div>
            <button onClick={load} disabled={isLoading} className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <FiRefreshCw style={{ width: 13, height: 13, animation: isLoading ? 'spin 1s linear infinite' : undefined }} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {isLoading && !data ? (
        <div className="card" style={{ padding: '60px 0', textAlign: 'center', color: '#9ca3af' }}>Loading analytics…</div>
      ) : data ? (
        <>
          {/* KPI tiles row 1 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
            <KpiCard label="Total Customers" value={data.total_customers} icon={FiUser} color="#4f46e5" />
            <KpiCard label={`New (${periodDays}d)`} value={data.new_customers_in_period} icon={FiUserCheck} color="#0ea5e9" sub="registered this period" />
            <KpiCard label="Repeat Rate" value={`${data.repeat_rate_pct.toFixed(1)}%`} icon={FiActivity} color="#16a34a" sub={`${data.repeat_customers} repeat buyers`} trend="up" />
            <KpiCard label="At-Risk" value={data.at_risk_customers} icon={FiAlertTriangle} color="#d97706" sub="no purchase 30–89 days" trend="down" />
            <KpiCard label="Churned" value={data.churned_customers} icon={FiUserX} color="#dc2626" sub="silent 90+ days" trend="down" />
          </div>

          {/* Engagement + Consent row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {/* Customer lifecycle funnel */}
            <div className="card" style={{ padding: '20px' }}>
              <h2 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 700 }} className="text-gray-800 dark:text-gray-200">
                Customer Lifecycle
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[
                  { label: 'Active customers', value: healthy, color: '#16a34a' },
                  { label: 'At-risk customers', value: data.at_risk_customers, color: '#d97706' },
                  { label: 'Churned customers', value: data.churned_customers, color: '#dc2626' },
                ].map(row => (
                  <div key={row.label}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 13 }} className="text-gray-600 dark:text-gray-400">{row.label}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: row.color }}>{row.value}</span>
                    </div>
                    <ProgressBar value={row.value} max={data.total_customers} color={row.color} />
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 20, borderTop: '1px solid #e5e7eb', paddingTop: 14 }}>
                <p style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 600 }} className="text-gray-700 dark:text-gray-300">Follow-up Delivery</p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                  {[
                    { label: 'Sent', value: data.follow_up_stats.sent, color: '#16a34a' },
                    { label: 'Pending', value: data.follow_up_stats.pending, color: '#d97706' },
                    { label: 'Failed', value: data.follow_up_stats.failed, color: '#dc2626' },
                  ].map(s => (
                    <div key={s.label} style={{ textAlign: 'center', background: `${s.color}11`, borderRadius: 8, padding: '8px 4px' }}>
                      <p style={{ margin: 0, fontSize: 20, fontWeight: 700, color: s.color }}>{s.value}</p>
                      <p style={{ margin: 0, fontSize: 11, color: s.color }}>{s.label}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Consent panel */}
            <div className="card" style={{ padding: '20px' }}>
              <h2 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 700 }} className="text-gray-800 dark:text-gray-200">
                Communication Consent
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {[
                  { label: 'SMS consent', value: data.consent_stats.sms_granted, pct: data.consent_stats.sms_rate_pct, color: '#4f46e5', icon: FiMessageSquare },
                  { label: 'WhatsApp consent', value: data.consent_stats.whatsapp_granted, pct: Math.round(data.consent_stats.whatsapp_granted / Math.max(data.total_customers, 1) * 100), color: '#16a34a', icon: FiMessageSquare },
                ].map(row => (
                  <div key={row.label}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <row.icon style={{ width: 14, height: 14, color: row.color }} />
                        <span style={{ fontSize: 13, fontWeight: 600 }} className="text-gray-700 dark:text-gray-300">{row.label}</span>
                      </div>
                      <span style={{ fontSize: 13, fontWeight: 700, color: row.color }}>{row.value} <span style={{ fontWeight: 400, color: '#9ca3af' }}>({row.pct.toFixed(1)}%)</span></span>
                    </div>
                    <ProgressBar value={row.value} max={data.total_customers} color={row.color} />
                  </div>
                ))}
              </div>

              {data.total_customers > 0 && data.consent_stats.sms_rate_pct < 50 && (
                <div style={{ marginTop: 16, background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: '10px 12px' }}>
                  <p style={{ margin: 0, fontSize: 12, color: '#92400e' }}>
                    <strong>Tip:</strong> Less than 50% of customers have granted SMS consent. Train cashiers to request consent at registration to improve reach.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Top customers + Product affinity */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {/* Top customers */}
            <div className="card" style={{ padding: '20px' }}>
              <h2 style={{ margin: '0 0 14px', fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }} className="text-gray-800 dark:text-gray-200">
                <FiAward style={{ width: 16, height: 16, color: '#d97706' }} />
                Top Customers by Spend
              </h2>
              {data.top_customers.length === 0 ? (
                <p style={{ fontSize: 13, color: '#9ca3af' }}>No customer purchase data yet.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {data.top_customers.map((c, i) => (
                    <div key={c.customer_id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 24, fontSize: 13, fontWeight: 700, color: i === 0 ? '#d97706' : '#9ca3af', textAlign: 'center', flexShrink: 0 }}>#{i + 1}</div>
                      <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'linear-gradient(135deg, #4f46e5, #7c3aed)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 14, flexShrink: 0 }}>
                        {c.full_name.charAt(0).toUpperCase()}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ margin: 0, fontSize: 13, fontWeight: 600 }} className="text-gray-900 dark:text-gray-100 truncate">{c.full_name}</p>
                        <p style={{ margin: 0, fontSize: 11 }} className="text-gray-500">{c.purchase_count} purchase(s)</p>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: '#16a34a' }}>GHS {c.total_spend.toFixed(2)}</p>
                        {c.last_purchase_at && (
                          <p style={{ margin: 0, fontSize: 10, color: '#9ca3af' }}>
                            Last: {new Date(c.last_purchase_at).toLocaleDateString('en-GB')}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Product affinity */}
            <div className="card" style={{ padding: '20px' }}>
              <h2 style={{ margin: '0 0 14px', fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }} className="text-gray-800 dark:text-gray-200">
                <FiActivity style={{ width: 16, height: 16, color: '#0ea5e9' }} />
                Products by Customer Reach
              </h2>
              <p style={{ margin: '0 0 12px', fontSize: 11, color: '#9ca3af' }}>Products purchased by the most distinct registered customers (last {periodDays} days)</p>
              {data.top_products_by_customer_reach.length === 0 ? (
                <p style={{ fontSize: 13, color: '#9ca3af' }}>No data — make sure customers are linked to sales at the POS.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {data.top_products_by_customer_reach.slice(0, 8).map((p, i) => (
                    <div key={p.product_id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 22, fontSize: 12, fontWeight: 700, color: '#9ca3af', flexShrink: 0 }}>#{i + 1}</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ margin: '0 0 3px', fontSize: 13, fontWeight: 600 }} className="text-gray-800 dark:text-gray-200 truncate">{p.product_name}</p>
                        <ProgressBar value={p.distinct_customers} max={data.top_products_by_customer_reach[0].distinct_customers} color="#0ea5e9" />
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <p style={{ margin: 0, fontSize: 12, fontWeight: 700, color: '#0ea5e9' }}>{p.distinct_customers} customers</p>
                        <p style={{ margin: 0, fontSize: 10, color: '#9ca3af' }}>{p.total_units_sold} units</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
