const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api').replace(/\/$/, '')
const ACCESS_KEY = 'eso_access_token'
const REFRESH_KEY = 'eso_refresh_token'

export const session = {
  get access() { return localStorage.getItem(ACCESS_KEY) },
  get refresh() { return localStorage.getItem(REFRESH_KEY) },
  save({ access, refresh }) {
    if (access) localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const fieldError = Object.values(data).flat().find(Boolean)
    throw new Error(data.detail || fieldError || 'Something went wrong. Please try again.')
  }
  return data
}

async function refreshAccessToken() {
  if (!session.refresh) return false
  const response = await fetch(`${API_URL}/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: session.refresh }),
  })
  if (!response.ok) {
    session.clear()
    return false
  }
  session.save(await response.json())
  return true
}

async function request(path, options = {}, retry = true) {
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers }
  if (session.access) headers.Authorization = `Bearer ${session.access}`
  let response
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers })
  } catch {
    throw new Error(`Cannot reach the Eso API at ${API_URL}. Start the Django server and try again.`)
  }
  if (response.status === 401 && retry && await refreshAccessToken()) {
    return request(path, options, false)
  }
  return parseResponse(response)
}

export const api = {
  async login(credentials) {
    const tokens = await request('/auth/login/', { method: 'POST', body: JSON.stringify(credentials) })
    session.save(tokens)
    return request('/auth/me/')
  },
  async register(details) {
    const result = await request('/auth/register/', { method: 'POST', body: JSON.stringify(details) })
    session.save(result)
    return result.user
  },
  me: () => request('/auth/me/'),
  paymentPinStatus: () => request('/auth/payment-pin/'),
  setPaymentPin: (details) => request('/auth/payment-pin/', {
    method: 'POST', body: JSON.stringify(details),
  }),
  baseline: () => request('/me/baseline/'),
  ledger: () => request('/me/ledger/'),
  transaction: (id) => request(`/transactions/${id}/`),
  createTransaction: (payload) => request('/transactions/', { method: 'POST', body: JSON.stringify(payload) }),
  decideTransaction: (id, decision) => request(`/transactions/${id}/decision/`, {
    method: 'POST', body: JSON.stringify({ decision }),
  }),
  submitReflection: (id, answer) => request(`/transactions/${id}/reflection/`, {
    method: 'POST', body: JSON.stringify({ answer }),
  }),
  reportRecipient: (id, report) => request(`/transactions/${id}/report/`, {
    method: 'POST', body: JSON.stringify(report),
  }),
  requestSecurityReview: (id) => request(`/transactions/${id}/review-request/`, { method: 'POST' }),
  securityReviews: () => request('/security-reviews/'),
  decideSecurityReview: (id, decision, note = '') => request(`/security-reviews/${id}/decision/`, {
    method: 'POST', body: JSON.stringify({ decision, note }),
  }),
}

export async function getLedgerWithTransactions() {
  const entries = await api.ledger()
  const ids = [...new Set(entries.map((entry) => entry.transaction))]
  const transactions = await Promise.all(ids.map((id) => api.transaction(id)))
  const byId = Object.fromEntries(transactions.map((item) => [item.id, item]))
  return entries.map((entry) => ({ ...entry, transactionDetail: byId[entry.transaction] }))
}
