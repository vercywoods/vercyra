import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { apiFetch, getActivity, getDashboard, getProjects, signIn, signOut, signUp } from './api'
import './App.css'

const metricsSeed = [
  { value: '12k+', label: 'daily actions tracked' },
  { value: '3.4x', label: 'faster handoff cycles' },
  { value: '99.9%', label: 'workflow uptime' },
]

const features = [
  { icon: '⚡', title: 'Realtime orchestration', text: 'Coordinate tasks, approvals, and signals in one place without switching tools.' },
  { icon: '🧠', title: 'Smart summaries', text: 'Turn scattered notes and activity into focused decisions with AI-ready context.' },
  { icon: '🔒', title: 'Trust-first operations', text: 'Keep every step visible, auditable, and aligned to the right team owner.' },
  { icon: '📈', title: 'Lean performance', text: 'Spot blockers early and keep momentum with a clear operating rhythm.' },
]

const workflow = [
  'Capture requests from product, ops, and customer teams',
  'Route work into a single source of truth',
  'Measure progress across every milestone and decision',
]

function AppShell({ user, onLogout, children }) {
  return (
    <div className="vercyra-shell">
      <header className="topbar">
        <div className="brand-wrap">
          <div className="brand-mark">V</div>
          <span>Vercyra</span>
        </div>

        <nav className="nav" aria-label="Main navigation">
          {user ? (
            <>
              <NavLink to="/dashboard">Dashboard</NavLink>
              <NavLink to="/projects">Projects</NavLink>
              <NavLink to="/activity">Activity</NavLink>
            </>
          ) : (
            <>
              <a href="#platform">Platform</a>
              <a href="#solutions">Solutions</a>
              <a href="#insights">Insights</a>
              <a href="#pricing">Pricing</a>
            </>
          )}
        </nav>

        {user ? (
          <button type="button" className="primary-button small-button" onClick={onLogout}>
            Sign out
          </button>
        ) : (
          <NavLink to="/login" className="primary-button small-button nav-cta">
            Book demo
          </NavLink>
        )}
      </header>

      {children}
    </div>
  )
}

function LandingPage() {
  return (
    <main>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Built for faster execution</p>
          <h1>Move work from chaos to clarity.</h1>
          <p className="lead">
            Vercyra helps teams plan, prioritize, and deliver with shared context,
            clear ownership, and real-time visibility.
          </p>

          <div className="hero-actions">
            <NavLink to="/login" className="primary-button">
              Get started
            </NavLink>
            <NavLink to="/dashboard" className="secondary-button">
              View demo
            </NavLink>
          </div>

          <div className="mini-proof">
            <span>Trusted by teams shipping every week</span>
            <div className="avatars" aria-label="Customer avatars">
              <span>AL</span>
              <span>MK</span>
              <span>RT</span>
            </div>
          </div>
        </div>

        <div className="hero-panel" aria-label="Product overview">
          <div className="panel-header">
            <span className="status-dot" />
            <span>Operations overview</span>
          </div>

          <div className="chart-card">
            <div className="chart-labels">
              <span>Delivery health</span>
              <strong>89%</strong>
            </div>
            <div className="bars" aria-hidden="true">
              <span style={{ height: '32%' }} />
              <span style={{ height: '52%' }} />
              <span style={{ height: '65%' }} />
              <span style={{ height: '78%' }} />
              <span style={{ height: '92%' }} />
              <span style={{ height: '100%' }} />
            </div>
          </div>

          <div className="stack-card">
            <div>
              <small>Active initiatives</small>
              <strong>24</strong>
            </div>
            <div>
              <small>Blocked items</small>
              <strong>03</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="stats" aria-label="Key metrics">
        {metricsSeed.map((metric) => (
          <div key={metric.label} className="stat-box">
            <strong>{metric.value}</strong>
            <span>{metric.label}</span>
          </div>
        ))}
      </section>

      <section className="feature-section" id="platform">
        <div className="section-heading">
          <p className="eyebrow">Why Vercyra</p>
          <h2>One operating layer for your whole workflow.</h2>
        </div>

        <div className="feature-grid">
          {features.map((feature) => (
            <article key={feature.title} className="feature-card">
              <div className="feature-icon" aria-hidden="true">{feature.icon}</div>
              <h3>{feature.title}</h3>
              <p>{feature.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="workflow-section" id="solutions">
        <div className="workflow-copy">
          <p className="eyebrow">Built for momentum</p>
          <h2>Keep every project moving without losing context.</h2>
          <ul>
            {workflow.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="workflow-card">
          <div className="signal-row">
            <span>Launch plan</span>
            <span className="signal-pill success">On track</span>
          </div>
          <div className="signal-row">
            <span>Team sync</span>
            <span className="signal-pill warning">2 reviews</span>
          </div>
          <div className="signal-row">
            <span>Dependencies</span>
            <span className="signal-pill neutral">6 pending</span>
          </div>
        </div>
      </section>
    </main>
  )
}

function DashboardPage() {
  const [dashboard, setDashboard] = useState(null)

  useEffect(() => {
    getDashboard()
      .then((payload) => setDashboard(payload))
      .catch(() => setDashboard(null))
  }, [])

  if (!dashboard) {
    return <div className="panel loading-panel">Loading dashboard…</div>
  }

  return (
    <main className="dashboard-grid">
      <section className="panel highlight-panel">
        <p className="eyebrow">Welcome back</p>
        <h2>{dashboard.user.name}</h2>
        <p>{dashboard.user.email}</p>
      </section>

      <section className="panel stats-panel">
        {dashboard.metrics.map((item) => (
          <div key={item.label} className="metric-box">
            <strong>{item.value}</strong>
            <span>{item.label}</span>
          </div>
        ))}
      </section>

      <section className="panel">
        <div className="section-title-row">
          <h3>Active projects</h3>
          <span className="pill">{dashboard.projects.length}</span>
        </div>

        <div className="project-list">
          {dashboard.projects.map((project) => (
            <div key={project.name} className="project-row">
              <div>
                <strong>{project.name}</strong>
                <small>{project.owner}</small>
              </div>
              <span className={`status ${project.status.toLowerCase().replace(/\s+/g, '-')}`}>
                {project.status}
              </span>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}

function ProjectsPage() {
  const [projects, setProjects] = useState([])

  useEffect(() => {
    getProjects().then((payload) => setProjects(payload.projects || []))
  }, [])

  return (
    <main className="content-page">
      <section className="panel full-width-panel">
        <div className="section-title-row">
          <h2>Portfolio</h2>
          <button type="button" className="primary-button small-button">New project</button>
        </div>

        <div className="project-table">
          {projects.map((project) => (
            <div key={project.name} className="table-row">
              <div>
                <strong>{project.name}</strong>
                <small>{project.owner}</small>
              </div>
              <span>{project.phase}</span>
              <span>{project.progress}%</span>
              <span className={`status ${project.status.toLowerCase().replace(/\s+/g, '-')}`}>{project.status}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}

function ActivityPage() {
  const [activity, setActivity] = useState([])

  useEffect(() => {
    getActivity().then((payload) => setActivity(payload.activity || []))
  }, [])

  return (
    <main className="content-page">
      <section className="panel full-width-panel">
        <div className="section-title-row">
          <h2>Activity</h2>
        </div>

        <div className="activity-list">
          {activity.map((item) => (
            <div key={`${item.user}-${item.time}`} className="activity-item">
              <span className="activity-badge">{item.type}</span>
              <div>
                <strong>{item.user}</strong>
                <p>{item.message}</p>
              </div>
              <time>{item.time}</time>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}

function LoginPage({ onLogin }) {
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')

  const handleChange = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')

    try {
      const result = mode === 'login'
        ? await signIn({ email: form.email, password: form.password })
        : await signUp({ name: form.name, email: form.email, password: form.password })

      onLogin(result.user)
      navigate('/dashboard')
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card panel">
        <div className="auth-header">
          <p className="eyebrow">Access Vercyra</p>
          <h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'register' && (
            <label>
              <span>Name</span>
              <input type="text" name="name" value={form.name} onChange={handleChange} placeholder="Alex Morgan" required />
            </label>
          )}

          <label>
            <span>Email</span>
            <input type="email" name="email" value={form.email} onChange={handleChange} placeholder="you@example.com" required />
          </label>

          <label>
            <span>Password</span>
            <input type="password" name="password" value={form.password} onChange={handleChange} placeholder="At least 12 characters" required />
          </label>

          {error && <p className="auth-error">{error}</p>}

          <button type="submit" className="primary-button auth-button">
            {mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <button type="button" className="inline-toggle" onClick={() => setMode((current) => current === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Need an account? Create one' : 'Already have an account? Sign in'}
        </button>
      </section>
    </main>
  )
}

function App() {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    apiFetch('/api/me')
      .then((payload) => setUser(payload.user))
      .catch(() => setUser(null))
      .finally(() => setReady(true))
  }, [])

  const handleLogout = async () => {
    try {
      await signOut()
    } finally {
      setUser(null)
    }
  }

  if (!ready) {
    return (
      <div className="vercyra-shell loading-shell">
        <div className="panel loading-panel">Checking your session…</div>
      </div>
    )
  }

  return (
    <BrowserRouter>
      <AppShell user={user} onLogout={handleLogout}>
        <Routes>
          <Route path="/" element={user ? <Navigate to="/dashboard" replace /> : <LandingPage />} />
          <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <LoginPage onLogin={setUser} />} />
          <Route path="/dashboard" element={user ? <DashboardPage /> : <Navigate to="/login" replace />} />
          <Route path="/projects" element={user ? <ProjectsPage /> : <Navigate to="/login" replace />} />
          <Route path="/activity" element={user ? <ActivityPage /> : <Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}

export default App
