const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`

  const response = await fetch(url, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};

  if (!response.ok) {
    throw new Error(payload.error || 'Request failed');
  }

  return payload;
}

export function getDashboard() {
  return apiFetch('/api/dashboard');
}

export function getProjects() {
  return apiFetch('/api/projects');
}

export function getActivity() {
  return apiFetch('/api/activity');
}

export function signIn(payload) {
  return apiFetch('/api/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function signUp(payload) {
  return apiFetch('/api/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function signOut() {
  return apiFetch('/api/logout', {
    method: 'POST',
  });
}

export function getSecurityDashboard() {
  return apiFetch('/api/security/dashboard')
}

export function getDashboardSession() {
  return apiFetch('/api/auth/session')
}

export function loginDashboard(password) {
  return apiFetch('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  })
}

export function logoutDashboard() {
  return apiFetch('/api/auth/logout', { method: 'POST' })
}

export function setCapture(active) {
  return apiFetch(`/api/security/capture/${active ? 'start' : 'stop'}`, {
    method: 'POST',
  })
}

export function createSubscription(tier) {
  return apiFetch('/api/billing/subscribe', {
    method: 'POST',
    body: JSON.stringify({ tier }),
  })
}

export function simulateBillingWebhook(provider, tier, action = 'activate') {
  return apiFetch('/api/billing/simulator/webhook', {
    method: 'POST',
    body: JSON.stringify({ provider, tier, action }),
  })
}

export async function downloadEventExport() {
  const response = await fetch(`${API_BASE}/api/security/events.csv`, {
    credentials: 'include',
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.error || 'Could not export events')
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'vercyra-events.csv'
  anchor.click()
  URL.revokeObjectURL(url)
}
