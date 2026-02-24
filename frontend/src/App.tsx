import { useEffect, useMemo, useState } from 'react'
import './App.css'

type LeadListItem = {
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

type Caller = {
  id: string
  name: string
  role: string | null
  languages: string[]
  daily_limit: number
  assigned_states: string[]
  leads_assigned_today: number
  status: string
}

type AssignmentEvent = {
  type: 'assignment'
  payload: {
    lead_id: string
    caller_id: string | null
    assignment_status: string
    assignment_reason: string
    timestamp: string
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws/dashboard'

function App() {
  const [leads, setLeads] = useState<LeadListItem[]>([])
  const [callers, setCallers] = useState<Caller[]>([])
  const [stateFilter, setStateFilter] = useState<string>('')
  const [callerFilter, setCallerFilter] = useState<string>('')
  const [search, setSearch] = useState<string>('')

  useEffect(() => {
    void Promise.all([
      fetch(
        `${API_BASE_URL}/api/leads?limit=100` +
          (stateFilter ? `&state=${encodeURIComponent(stateFilter)}` : '') +
          (callerFilter ? `&caller_id=${encodeURIComponent(callerFilter)}` : '') +
          (search ? `&search=${encodeURIComponent(search)}` : ''),
      ).then((r) => r.json()),
      fetch(`${API_BASE_URL}/api/callers`).then((r) => r.json()),
    ]).then(([leadsRes, callersRes]) => {
      setLeads(leadsRes ?? [])
      setCallers(callersRes ?? [])
    })
  }, [stateFilter, callerFilter, search])

  useEffect(() => {
    const ws = new WebSocket(WS_URL)
    ws.onmessage = (event) => {
      const data: AssignmentEvent = JSON.parse(event.data)
      if (data.type === 'assignment') {
        setLeads((prev) =>
          prev.map((l) =>
            l.id === data.payload.lead_id
              ? {
                  ...l,
                  assignment_status: data.payload.assignment_status,
                  assignment_reason: data.payload.assignment_reason,
                  assigned_at: data.payload.timestamp,
                }
              : l,
          ),
        )
      }
    }
    return () => {
      ws.close()
    }
  }, [])

  const states = useMemo(
    () => Array.from(new Set(leads.map((l) => l.state).filter(Boolean))) as string[],
    [leads],
  )

  return (
    <div className="app-root">
      <header className="app-header">
        <h1>Sales CRM Dashboard</h1>
      </header>
      <main className="app-layout">
        <section className="panel">
          <h2>Live Leads</h2>
          <div className="filters">
            <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}>
              <option value="">All states</option>
              {states.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <select
              value={callerFilter}
              onChange={(e) => setCallerFilter(e.target.value)}
            >
              <option value="">All callers</option>
              {callers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or phone"
            />
          </div>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>State</th>
                  <th>Source</th>
                  <th>Caller</th>
                  <th>Status</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id}>
                    <td>{lead.assigned_at ? new Date(lead.assigned_at).toLocaleString() : ''}</td>
                    <td>{lead.name}</td>
                    <td>{lead.phone}</td>
                    <td>{lead.state}</td>
                    <td>{lead.lead_source}</td>
                    <td>{lead.assigned_caller_name}</td>
                    <td>{lead.assignment_status}</td>
                    <td>{lead.assignment_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="panel">
          <h2>Callers</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>States</th>
                  <th>Daily limit</th>
                  <th>Assigned today</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {callers.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td>
                    <td>{c.assigned_states.join(', ')}</td>
                    <td>{c.daily_limit === 0 ? 'Unlimited' : c.daily_limit}</td>
                    <td>{c.leads_assigned_today}</td>
                    <td>{c.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
