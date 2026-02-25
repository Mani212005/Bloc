import { useState } from 'react'
import type { Caller, LeadListItem } from '../api'
import { reassignLead } from '../api'
import { Modal } from './Modal'
import { showToast } from './Toast'

interface Props {
  leads: LeadListItem[]
  callers: Caller[]
  stateFilter: string
  callerFilter: string
  search: string
  onStateFilter: (v: string) => void
  onCallerFilter: (v: string) => void
  onSearch: (v: string) => void
  states: string[]
  onRefresh: () => void
}

const REASON_LABELS: Record<string, string> = {
  state_round_robin: 'State RR',
  global_round_robin: 'Global RR',
  manual_reassign: 'Manual',
  unassigned_cap_reached: 'Cap reached',
  unassigned_no_eligible: 'No eligible',
}

export function LeadsPanel({
  leads,
  callers,
  stateFilter,
  callerFilter,
  search,
  onStateFilter,
  onCallerFilter,
  onSearch,
  states,
  onRefresh,
}: Props) {
  const [reassigning, setReassigning] = useState<LeadListItem | null>(null)
  const [selectedCaller, setSelectedCaller] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)

  function openReassign(lead: LeadListItem) {
    setReassigning(lead)
    setSelectedCaller(
      callers.find((c) => c.name === lead.assigned_caller_name)?.id ?? '',
    )
  }

  async function handleReassign() {
    if (!reassigning) return
    setSubmitting(true)
    try {
      await reassignLead(reassigning.id, selectedCaller || null)
      showToast(`Lead reassigned successfully.`)
      setReassigning(null)
      onRefresh()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Reassignment failed.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Live Leads</h2>
        <span className="badge badge--count">{leads.length}</span>
      </div>

      <div className="filters">
        <select value={stateFilter} onChange={(e) => onStateFilter(e.target.value)}>
          <option value="">All states</option>
          {states.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select value={callerFilter} onChange={(e) => onCallerFilter(e.target.value)}>
          <option value="">All callers</option>
          {callers.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        <input
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search name or phone…"
          className="filters__search"
        />
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Assigned At</th>
              <th>Name</th>
              <th>Phone</th>
              <th>State</th>
              <th>Source</th>
              <th>Caller</th>
              <th>Status</th>
              <th>Reason</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {leads.length === 0 && (
              <tr>
                <td colSpan={9} className="empty-row">No leads yet.</td>
              </tr>
            )}
            {leads.map((lead) => (
              <tr
                key={lead.id}
                className={lead.assignment_status === 'unassigned' ? 'row--warning' : ''}
              >
                <td className="td--mono">
                  {lead.assigned_at
                    ? new Date(lead.assigned_at).toLocaleString('en-IN', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : <span className="muted">—</span>}
                </td>
                <td className="td--bold">{lead.name ?? <span className="muted">—</span>}</td>
                <td className="td--mono">{lead.phone}</td>
                <td>
                  {lead.state
                    ? <span className="badge badge--state">{lead.state}</span>
                    : <span className="muted">—</span>}
                </td>
                <td>{lead.lead_source ?? <span className="muted">—</span>}</td>
                <td>{lead.assigned_caller_name ?? <span className="muted">Unassigned</span>}</td>
                <td>
                  <span className={`status-pill status-pill--${lead.assignment_status ?? 'none'}`}>
                    {lead.assignment_status ?? '—'}
                  </span>
                </td>
                <td>
                  {lead.assignment_reason
                    ? <span title={lead.assignment_reason}>{REASON_LABELS[lead.assignment_reason] ?? lead.assignment_reason}</span>
                    : <span className="muted">—</span>}
                </td>
                <td className="td--actions">
                  <button
                    className="btn btn--ghost btn--xs"
                    onClick={() => openReassign(lead)}
                  >
                    Reassign
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {reassigning && (
        <Modal title="Reassign Lead" onClose={() => setReassigning(null)} width={420}>
          <div className="form">
            <div className="reassign-lead-info">
              <div><span className="muted">Lead:</span> <strong>{reassigning.name ?? reassigning.phone}</strong></div>
              <div><span className="muted">Phone:</span> {reassigning.phone}</div>
              <div><span className="muted">State:</span> {reassigning.state ?? '—'}</div>
              <div><span className="muted">Current caller:</span> {reassigning.assigned_caller_name ?? 'Unassigned'}</div>
            </div>

            <div className="form__row" style={{ marginTop: '1rem' }}>
              <label className="form__label" htmlFor="reassign-caller">Assign to</label>
              <select
                id="reassign-caller"
                className="form__select"
                value={selectedCaller}
                onChange={(e) => setSelectedCaller(e.target.value)}
              >
                <option value="">— Auto-assign (round robin) —</option>
                {callers
                  .filter((c) => c.status === 'active')
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                      {c.daily_limit > 0
                        ? ` (${c.leads_assigned_today}/${c.daily_limit} today)`
                        : ` (${c.leads_assigned_today} today)`}
                    </option>
                  ))}
              </select>
            </div>

            <div className="form__actions">
              <button className="btn btn--ghost" onClick={() => setReassigning(null)} disabled={submitting}>
                Cancel
              </button>
              <button className="btn btn--primary" onClick={handleReassign} disabled={submitting}>
                {submitting ? 'Assigning…' : 'Confirm Reassign'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </section>
  )
}
