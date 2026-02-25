import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { listLeads, listCallers } from './api'
import type { AssignmentEvent, Caller, LeadListItem } from './api'
import { CallerPanel } from './components/CallerPanel'
import { LeadsPanel } from './components/LeadsPanel'
import { ToastContainer, showToast } from './components/Toast'
import './index.css'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws/dashboard'
const WS_RECONNECT_DELAY_MS = 3000

function App() {
  const [leads, setLeads] = useState<LeadListItem[]>([])
  const [callers, setCallers] = useState<Caller[]>([])
  const [loadingLeads, setLoadingLeads] = useState(false)
  const [loadingCallers, setLoadingCallers] = useState(false)

  const [stateFilter, setStateFilter] = useState('')
  const [callerFilter, setCallerFilter] = useState('')
  const [search, setSearch] = useState('')

  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Data fetching ────────────────────────────────────────────────────────
  const fetchLeads = useCallback(async () => {
    setLoadingLeads(true)
    try {
      const data = await listLeads({
        state: stateFilter || undefined,
        caller_id: callerFilter || undefined,
        search: search || undefined,
        limit: 100,
      })
      setLeads(data)
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to load leads.', 'error')
    } finally {
      setLoadingLeads(false)
    }
  }, [stateFilter, callerFilter, search])

  const fetchCallers = useCallback(async () => {
    setLoadingCallers(true)
    try {
      const data = await listCallers()
      setCallers(data)
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to load callers.', 'error')
    } finally {
      setLoadingCallers(false)
    }
  }, [])

  const refreshAll = useCallback(() => {
    void fetchLeads()
    void fetchCallers()
  }, [fetchLeads, fetchCallers])

  useEffect(() => { void fetchLeads() }, [fetchLeads])
  useEffect(() => { void fetchCallers() }, [fetchCallers])

  // ── WebSocket with auto-reconnect ────────────────────────────────────────
  useEffect(() => {
    function connect() {
      setWsStatus('connecting')
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => setWsStatus('connected')

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data: AssignmentEvent = JSON.parse(event.data as string)
          if (data.type === 'assignment') {
            const p = data.payload
            setLeads((prev) => {
              const exists = prev.find((l) => l.id === p.lead_id)
              if (exists) {
                return prev.map((l) =>
                  l.id === p.lead_id
                    ? { ...l, assignment_status: p.assignment_status, assignment_reason: p.assignment_reason, assigned_at: p.timestamp }
                    : l,
                )
              }
              void fetchLeads()
              return prev
            })
            void fetchCallers()
          }
        } catch { /* ignore malformed */ }
      }

      ws.onclose = () => {
        setWsStatus('disconnected')
        reconnectTimerRef.current = setTimeout(connect, WS_RECONNECT_DELAY_MS)
      }
      ws.onerror = () => ws.close()
    }

    connect()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [fetchLeads, fetchCallers])

  // ── Derived state ────────────────────────────────────────────────────────
  const states = useMemo(
    () => Array.from(new Set(leads.map((l) => l.state).filter(Boolean))) as string[],
    [leads],
  )

  const unassignedCount = leads.filter((l) => l.assignment_status === 'unassigned').length

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <>
      <ToastContainer />
      <div className="app-root">
        <header className="app-header">
          <div className="app-header__brand">
            <span className="app-header__logo">⚡</span>
            <h1 className="app-header__title">Bloc CRM</h1>
          </div>
          <div className="app-header__meta">
            {unassignedCount > 0 && (
              <span className="header-badge header-badge--warn">
                {unassignedCount} unassigned
              </span>
            )}
            <span className={`ws-indicator ws-indicator--${wsStatus}`} title={`WebSocket: ${wsStatus}`}>
              {wsStatus === 'connected' ? '● Live' : wsStatus === 'connecting' ? '○ Connecting…' : '○ Reconnecting…'}
            </span>
          </div>
        </header>

        <main className="app-layout">
          <LeadsPanel
            leads={leads}
            callers={callers}
            stateFilter={stateFilter}
            callerFilter={callerFilter}
            search={search}
            onStateFilter={setStateFilter}
            onCallerFilter={setCallerFilter}
            onSearch={setSearch}
            states={states}
            onRefresh={refreshAll}
          />
          <CallerPanel callers={callers} onRefresh={refreshAll} />
        </main>

        {(loadingLeads || loadingCallers) && (
          <div className="global-loading" aria-live="polite">Loading…</div>
        )}
      </div>
    </>
  )
}

export default App
