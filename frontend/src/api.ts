const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export interface Caller {
  id: string
  name: string
  role: string | null
  languages: string[]
  daily_limit: number
  assigned_states: string[]
  leads_assigned_today: number
  status: 'active' | 'paused'
}

export interface CallerCreate {
  name: string
  role?: string
  languages: string[]
  daily_limit: number
  assigned_states: string[]
  status: 'active' | 'paused'
}

export interface CallerUpdate {
  role?: string
  languages?: string[]
  daily_limit?: number
  assigned_states?: string[]
  status?: 'active' | 'paused'
}

export interface LeadListItem {
  id: string
  name: string | null
  phone: string
  state: string | null
  lead_source: string | null
  assigned_caller_name: string | null
  assignment_status: string | null
  assignment_reason: string | null
  assigned_at: string | null
}

export interface AssignmentEvent {
  type: 'assignment'
  payload: {
    lead_id: string
    caller_id: string | null
    assignment_status: string
    assignment_reason: string
    timestamp: string
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail?.detail ?? res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// ── Callers ────────────────────────────────────────────────────────────────
export const listCallers = (): Promise<Caller[]> => request('/api/callers')

export const createCaller = (data: CallerCreate): Promise<Caller> =>
  request('/api/callers', { method: 'POST', body: JSON.stringify(data) })

export const updateCaller = (id: string, data: CallerUpdate): Promise<Caller> =>
  request(`/api/callers/${id}`, { method: 'PUT', body: JSON.stringify(data) })

export const patchCallerStatus = (id: string, status: 'active' | 'paused'): Promise<Caller> =>
  request(`/api/callers/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })

export const deleteCaller = (id: string): Promise<void> =>
  request(`/api/callers/${id}`, { method: 'DELETE' })

// ── Leads ──────────────────────────────────────────────────────────────────
export interface ListLeadsParams {
  state?: string
  caller_id?: string
  search?: string
  limit?: number
  offset?: number
}

export const listLeads = (params: ListLeadsParams = {}): Promise<LeadListItem[]> => {
  const qs = new URLSearchParams()
  if (params.state) qs.set('state', params.state)
  if (params.caller_id) qs.set('caller_id', params.caller_id)
  if (params.search) qs.set('search', params.search)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const q = qs.toString()
  return request(`/api/leads${q ? `?${q}` : ''}`)
}

export const reassignLead = (leadId: string, callerId: string | null): Promise<unknown> =>
  request(`/api/leads/${leadId}/reassign`, {
    method: 'PATCH',
    body: JSON.stringify({ caller_id: callerId }),
  })
