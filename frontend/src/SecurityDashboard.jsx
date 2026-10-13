import { useEffect, useState } from 'react'
import { createSubscription, downloadEventExport, getDashboardSession, getSecurityDashboard, loginDashboard, logoutDashboard, setCapture, simulateBillingWebhook } from './api'
import './SecurityDashboard.css'

const numberFormat = new Intl.NumberFormat('en-US')
const shortTime = new Intl.DateTimeFormat('en-US', { hour: '2-digit', minute: '2-digit' })

function Sparkline({ points = [], field, color, label }) {
  const width = 660
  const height = 180
  const pad = 8
  const values = points.map((point) => Number(point[field]) || 0)
  const maximum = Math.max(1, ...values)
  const coordinates = values.map((value, index) => ({
    x: pad + (index * (width - pad * 2)) / Math.max(1, values.length - 1),
    y: height - pad - (value / maximum) * (height - pad * 2),
  }))
  const line = coordinates.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ')
  const fill = `${line} L ${width - pad} ${height - pad} L ${pad} ${height - pad} Z`

  return (
    <svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      {[0.25, 0.5, 0.75].map((fraction) => (
        <line key={fraction} x1={pad} x2={width - pad} y1={height * fraction} y2={height * fraction} className="chart-gridline" />
      ))}
      {values.some(Boolean) && <path d={fill} fill={color} opacity="0.1" />}
      {values.some(Boolean) && <path d={line} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />}
      {coordinates.filter((_, index) => values[index] > 0).map((point, index) => (
        <circle key={`${point.x}-${index}`} cx={point.x} cy={point.y} r="3" fill={color} />
      ))}
    </svg>
  )
}

function Metric({ label, value, note, accent }) {
  return (
    <article className={`metric ${accent || ''}`}>
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
      <span className="metric-note">{note}</span>
    </article>
  )
}

function NetworkChart({ points }) {
  const packets = points.reduce((sum, point) => sum + (Number(point.packets) || 0), 0)
  const alerts = points.reduce((sum, point) => sum + (Number(point.alerts) || 0), 0)

  return (
    <section className="surface chart-panel">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">Traffic telemetry</span>
          <h2>Network activity</h2>
        </div>
        <div className="chart-legend">
          <span><i className="legend-dot packets" /> Packets <b>{numberFormat.format(packets)}</b></span>
          <span><i className="legend-dot alerts" /> Alerts <b>{numberFormat.format(alerts)}</b></span>
        </div>
      </div>
      <div className="chart-area">
        <div className="chart-scale"><span>HIGH</span><span>MED</span><span>LOW</span></div>
        <div className="chart-lines">
          <Sparkline points={points} field="packets" color="#67d6aa" label="Packet volume during the last hour" />
          <div className="alert-chart-overlay"><Sparkline points={points} field="alerts" color="#f0a34a" label="Threshold alerts during the last hour" /></div>
        </div>
      </div>
      <div className="chart-axis">
        {points.filter((_, index) => index % 3 === 0).map((point) => (
          <span key={point.time}>{shortTime.format(new Date(point.time * 1000))}</span>
        ))}
      </div>
      <div className="chart-caption"><span>Rolling 60 minutes</span><span>5-minute buckets</span></div>
    </section>
  )
}

function ActivityTable({ events }) {
  return (
    <section className="surface activity-panel">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">Packet journal</span>
          <h2>Recent activity</h2>
        </div>
        <span className="live-label"><i /> LIVE</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Event</th><th>Source</th><th>Destination</th><th>Time</th></tr></thead>
          <tbody>
            {events.length ? events.slice(0, 12).map((event, index) => (
              <tr key={`${event.id}-${index}`} className={event.event_type === 'threshold_alert' ? 'alert-row' : ''}>
                <td><span className={`event-pill ${event.event_type === 'threshold_alert' ? 'event-alert' : 'event-packet'}`}>{event.event_type === 'threshold_alert' ? 'Threshold' : 'Packet'}</span></td>
                <td className="mono">{event.source_ip || '—'}</td>
                <td className="mono">{event.destination_ip || '—'}</td>
                <td className="time-cell">{new Date(event.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
              </tr>
            )) : (
              <tr><td colSpan="4" className="empty-state">No traffic recorded. Start capture to populate the journal.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function DashboardLogin({ ready, error, onLogin }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [loginError, setLoginError] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setLoginError('')
    try {
      await loginDashboard(password)
      setPassword('')
      onLogin()
    } catch (requestError) {
      setLoginError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="dashboard-root">
      <header className="app-header"><a className="brand" href={import.meta.env.BASE_URL}><span className="brand-symbol">V</span><span>VERCYRA <small>SECURITY</small></span></a><span className="header-environment">SECURE ACCESS</span></header>
      <section className="offline-state login-state">
        <span className="section-kicker">Dashboard access</span>
        <h1>Sign in to Vercyra.</h1>
        {error && <p>{error}</p>}
        {!ready ? (
          <p>Dashboard authentication is not configured on the cPanel Python app.</p>
        ) : (
          <form className="dashboard-login-form" onSubmit={handleSubmit}>
            <label htmlFor="dashboard-password">Dashboard password</label>
            <input id="dashboard-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
            {loginError && <p className="auth-error" role="alert">{loginError}</p>}
            <button className="button-capture" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
          </form>
        )}
      </section>
    </main>
  )
}

function BillingPanel({ billing, onSubscribe, onCancel, busyTier }) {
  const simulatorProviders = billing.simulation_providers || []
  const simulatedActive = billing.status === 'SIMULATED_ACTIVE'

  return (
    <section className="surface billing-panel">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">Account</span>
          <h2>Plan & billing</h2>
        </div>
        <span className="billing-source">{simulatorProviders.length ? 'LOCAL TEST MODE' : billing.provider?.toUpperCase() || 'PAYPAL'}</span>
      </div>
      <div className="current-plan">
        <div className="plan-initial">{billing.tier_name?.slice(0, 1) || 'C'}</div>
        <div className="plan-copy"><span>Current plan</span><strong>{billing.tier_name || 'Community'}</strong></div>
        <span className={`status-tag ${billing.status === 'ACTIVE' ? 'status-active' : simulatedActive ? 'status-simulated' : billing.status === 'SIMULATED_CANCELLED' ? 'status-cancelled' : 'status-trial'}`}>{(billing.status || 'TRIAL').replaceAll('_', ' ')}</span>
      </div>
      <div className="plan-features">
        {(billing.features || []).map((feature) => <span key={feature}><i>+</i>{feature.replaceAll('_', ' ')}</span>)}
      </div>
      <div className="plan-options">
        {(billing.plans || []).map((plan) => (
          <div className="plan-option" key={plan.id}>
            <div><strong>{plan.name}</strong><span>{plan.available ? 'PayPal plan ready' : 'Plan ID not configured'}</span></div>
            <div className="plan-actions">
              {simulatorProviders.map((provider) => {
                const actionId = `${provider}:${plan.id}`
                return <button className="test-plan-button" type="button" key={provider} onClick={() => onSubscribe(plan.id, provider, true)} disabled={busyTier === actionId} aria-label={`Simulate ${provider} ${plan.name} checkout`}>
                  {busyTier === actionId ? 'Testing…' : `${provider === 'paypal' ? 'PayPal' : 'Stripe'} test`}
                </button>
              })}
              {billing.paypal_ready && plan.available && <button type="button" onClick={() => onSubscribe(plan.id, 'paypal', false)} disabled={busyTier === `paypal:${plan.id}`} aria-label={`Subscribe to ${plan.name}`}>
                {busyTier === `paypal:${plan.id}` ? 'Opening…' : 'PayPal'}
              </button>}
            </div>
          </div>
        ))}
      </div>
      {simulatorProviders.length > 0 && <p className="setup-note simulation-note">Local simulation only. No PayPal or Stripe requests are made and no payment is taken.</p>}
      {!billing.paypal_ready && simulatorProviders.length === 0 && <p className="setup-note">{billing.environment === 'live' ? 'Live checkout is locked until real PayPal API credentials, live plan IDs, and public HTTPS return/webhook URLs are configured.' : 'Sandbox checkout requires PayPal API credentials, webhook ID, and plan IDs in `.env`.'}</p>}
      {simulatedActive && <button className="cancel-test-button" type="button" onClick={() => onCancel(billing.provider)} disabled={busyTier === `cancel:${billing.provider}`}>{busyTier === `cancel:${billing.provider}` ? 'Applying…' : 'Cancel simulated subscription'}</button>}
      {billing.subscription_id && <p className="subscription-id">Subscription <span>{billing.subscription_id}</span></p>}
    </section>
  )
}

export default function SecurityDashboard() {
  const [dashboard, setDashboard] = useState(null)
  const [loadingError, setLoadingError] = useState('')
  const [authenticated, setAuthenticated] = useState(!import.meta.env.PROD)
  const [authReady, setAuthReady] = useState(!import.meta.env.PROD)
  const [authConfigured, setAuthConfigured] = useState(true)
  const [busy, setBusy] = useState(false)
  const [busyTier, setBusyTier] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let mounted = true
    if (!import.meta.env.PROD) return () => { mounted = false }

    getDashboardSession()
      .then((session) => {
        if (mounted) {
          setAuthenticated(session.authenticated)
          setAuthConfigured(session.ready)
          setLoadingError('')
        }
      })
      .catch((error) => {
        if (mounted) setLoadingError(error.message)
      })
      .finally(() => {
        if (mounted) setAuthReady(true)
      })

    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (!authenticated) return undefined
    let mounted = true
    const refresh = async () => {
      try {
        const payload = await getSecurityDashboard()
        if (mounted) {
          setDashboard(payload)
          setLoadingError('')
        }
      } catch (error) {
        if (mounted) setLoadingError(error.message)
      }
    }
    refresh()
    const interval = window.setInterval(refresh, 2500)
    return () => {
      mounted = false
      window.clearInterval(interval)
    }
  }, [authenticated])

  const handleLogin = () => {
    setAuthenticated(true)
    setLoadingError('')
  }

  const handleLogout = async () => {
    try {
      await logoutDashboard()
    } finally {
      setAuthenticated(false)
      setDashboard(null)
    }
  }

  const toggleCapture = async () => {
    if (!dashboard) return
    setBusy(true)
    setNotice('')
    try {
      const capture = await setCapture(!dashboard.capture.active)
      setDashboard((current) => ({ ...current, capture }))
      if (capture.error) setNotice(capture.error)
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusy(false)
    }
  }

  const subscribe = async (tier, provider = 'paypal', simulated = false) => {
    const actionId = `${provider}:${tier}`
    setBusyTier(actionId)
    setNotice('')
    try {
      if (simulated) {
        await simulateBillingWebhook(provider, tier)
        setDashboard(await getSecurityDashboard())
        setNotice(`${provider === 'paypal' ? 'PayPal' : 'Stripe'} test event accepted. No payment was made.`)
      } else {
        const result = await createSubscription(tier)
        window.location.assign(result.approval_url)
      }
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusyTier('')
    }
  }

  const cancelSimulatedSubscription = async (provider) => {
    const actionId = `cancel:${provider}`
    setBusyTier(actionId)
    setNotice('')
    try {
      await simulateBillingWebhook(provider, billing.tier, 'cancel')
      setDashboard(await getSecurityDashboard())
      setNotice('Simulated cancellation accepted. No payment provider was contacted.')
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusyTier('')
    }
  }

  const exportEvents = async () => {
    setNotice('')
    try {
      await downloadEventExport()
    } catch (error) {
      setNotice(error.message)
    }
  }

  if (import.meta.env.PROD && !authReady) {
    return <main className="dashboard-root"><section className="offline-state"><p className="section-kicker">Dashboard access</p><h1>Checking session…</h1></section></main>
  }

  if (import.meta.env.PROD && !authenticated) {
    return <DashboardLogin ready={authConfigured} error={loadingError} onLogin={handleLogin} />
  }

  if (!dashboard && loadingError) {
    return (
      <main className="dashboard-root">
        <header className="app-header"><a className="brand" href={import.meta.env.BASE_URL}><span className="brand-symbol">V</span><span>VERCYRA <small>SECURITY</small></span></a><span className="header-environment">LOCAL OPERATIONS</span></header>
        <section className="offline-state"><span className="offline-icon">!</span><p className="section-kicker">API unavailable</p><h1>Security console is offline.</h1><p>{loadingError}</p><code>Start the API with: py vercyra_security_api.py</code><button className="button-secondary" type="button" onClick={() => window.location.reload()}>Retry connection</button></section>
      </main>
    )
  }

  const capture = dashboard?.capture || { active: false }
  const metrics = dashboard?.metrics || {}
  const billing = dashboard?.billing || {}

  return (
    <main className="dashboard-root">
      <header className="app-header">
        <a className="brand" href={import.meta.env.BASE_URL}><span className="brand-symbol">V</span><span>VERCYRA <small>SECURITY</small></span></a>
        <div className="header-center"><span className="environment-mark" /> LOCAL OPERATIONS CONSOLE <span className="header-separator">/</span> NODE 01</div>
        <div className="header-right"><span className={`capture-state ${capture.active ? 'is-capturing' : ''}`}><i />{capture.active ? 'CAPTURING' : 'STANDBY'}</span><time>{dashboard ? new Date(dashboard.generated_at * 1000).toLocaleTimeString() : '--:--'}</time>{import.meta.env.PROD && <button type="button" className="signout-button" onClick={handleLogout}>Sign out</button>}</div>
      </header>

      <div className="dashboard-content">
        <section className="page-heading">
          <div><p className="section-kicker">Threat observability / overview</p><h1>Security <em>operations</em></h1><p className="page-subtitle">Network telemetry, threshold activity, and billing state in one view.</p></div>
          <div className="heading-actions">
            <button type="button" className="button-secondary" onClick={exportEvents} disabled={!billing.features?.includes('exports')} title={!billing.features?.includes('exports') ? 'Active Pro or Business license required' : 'Download CSV'}>↓ <span>Export CSV</span></button>
            <button type="button" className={`button-capture ${capture.active ? 'stop-capture' : ''}`} onClick={toggleCapture} disabled={busy}>{busy ? 'Connecting…' : capture.active ? '■ Stop capture' : '▶ Start capture'}</button>
          </div>
        </section>

        {notice && <div className="notice-banner" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Dismiss">×</button></div>}
        {loadingError && <div className="notice-banner warning-banner" role="status">API refresh failed: {loadingError}</div>}
        {capture.error && <div className="notice-banner warning-banner" role="status">Packet capture error: {capture.error}</div>}

        <section className="metrics-grid" aria-label="Network metrics">
          <Metric label="Packets observed · 24H" value={numberFormat.format(metrics.packets_24h || 0)} note="Stored packet metadata" />
          <Metric label="Unique source IPs" value={numberFormat.format(metrics.unique_sources_24h || 0)} note="Rolling 24-hour window" accent="metric-lime" />
          <Metric label="Threshold alerts · 24H" value={numberFormat.format(metrics.alerts_24h || 0)} note={`${numberFormat.format(metrics.packets_10s || 0)} packets in last 10 seconds`} accent="metric-amber" />
          <Metric label="Detection rule" value="100 / 10s" note="Per source address" accent="metric-red" />
        </section>

        <div className="main-grid">
          <NetworkChart points={dashboard?.chart || []} />
          <BillingPanel billing={billing} onSubscribe={subscribe} onCancel={cancelSimulatedSubscription} busyTier={busyTier} />
        </div>

        <ActivityTable events={dashboard?.events || []} />
        <footer className="dashboard-footer"><span><i /> SQLITE · LOCAL METADATA ONLY</span><span>{dashboard?.database || 'vercyra_security.db'} <b>·</b> 30 DAY RETENTION</span><button type="button" onClick={() => getSecurityDashboard().then(setDashboard).catch((error) => setNotice(error.message))}>Refresh data</button></footer>
      </div>
    </main>
  )
}
