import { useState } from 'react'
import type { Caller, CallerCreate } from '../api'
import { createCaller, updateCaller, patchCallerStatus, deleteCaller } from '../api'
import { Modal } from './Modal'
import { CallerForm } from './CallerForm'
import { showToast } from './Toast'

interface Props {
  callers: Caller[]
  onRefresh: () => void
}

export function CallerPanel({ callers, onRefresh }: Props) {
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<Caller | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<Caller | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [togglingId, setTogglingId] = useState<string | null>(null)

  async function handleCreate(data: CallerCreate) {
    await createCaller(data)
    showToast(`Caller "${data.name}" created.`)
    setShowCreate(false)
    onRefresh()
  }

  async function handleUpdate(data: CallerCreate) {
    if (!editing) return
    await updateCaller(editing.id, {
      role: data.role,
      languages: data.languages,
      daily_limit: data.daily_limit,
      assigned_states: data.assigned_states,
      status: data.status,
    })
    showToast(`Caller "${data.name}" updated.`)
    setEditing(null)
    onRefresh()
  }

  async function handleToggleStatus(caller: Caller) {
    setTogglingId(caller.id)
    try {
      const next = caller.status === 'active' ? 'paused' : 'active'
      await patchCallerStatus(caller.id, next)
      showToast(`${caller.name} is now ${next}.`, 'info')
      onRefresh()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to update status.', 'error')
    } finally {
      setTogglingId(null)
    }
  }

  async function handleDelete() {
    if (!confirmDelete) return
    setDeletingId(confirmDelete.id)
    try {
      await deleteCaller(confirmDelete.id)
      showToast(`Caller "${confirmDelete.name}" removed.`, 'info')
      setConfirmDelete(null)
      onRefresh()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to delete.', 'error')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Callers</h2>
        <button className="btn btn--primary btn--sm" onClick={() => setShowCreate(true)}>
          + Add Caller
        </button>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>States</th>
              <th>Languages</th>
              <th>Daily Limit</th>
              <th>Assigned Today</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {callers.length === 0 && (
              <tr>
                <td colSpan={8} className="empty-row">No callers yet. Add one to get started.</td>
              </tr>
            )}
            {callers.map((c) => (
              <tr key={c.id} className={c.status === 'paused' ? 'row--muted' : ''}>
                <td className="td--bold">{c.name}</td>
                <td>{c.role ?? <span className="muted">—</span>}</td>
                <td>
                  {c.assigned_states.length > 0
                    ? c.assigned_states.map((s) => (
                        <span key={s} className="badge badge--state">{s}</span>
                      ))
                    : <span className="badge badge--global">global</span>}
                </td>
                <td>
                  {c.languages.length > 0
                    ? c.languages.map((l) => (
                        <span key={l} className="badge badge--lang">{l}</span>
                      ))
                    : <span className="muted">—</span>}
                </td>
                <td>{c.daily_limit === 0 ? <span className="muted">∞</span> : c.daily_limit}</td>
                <td>
                  <span className={c.daily_limit > 0 && c.leads_assigned_today >= c.daily_limit ? 'text--danger' : ''}>
                    {c.leads_assigned_today}
                    {c.daily_limit > 0 && ` / ${c.daily_limit}`}
                  </span>
                </td>
                <td>
                  <span className={`status-pill status-pill--${c.status}`}>
                    {c.status}
                  </span>
                </td>
                <td className="td--actions">
                  <button
                    className="btn btn--ghost btn--xs"
                    onClick={() => setEditing(c)}
                    title="Edit caller"
                  >
                    Edit
                  </button>
                  <button
                    className={`btn btn--xs ${c.status === 'active' ? 'btn--warning' : 'btn--success'}`}
                    onClick={() => handleToggleStatus(c)}
                    disabled={togglingId === c.id}
                    title={c.status === 'active' ? 'Pause caller' : 'Activate caller'}
                  >
                    {togglingId === c.id ? '…' : c.status === 'active' ? 'Pause' : 'Activate'}
                  </button>
                  <button
                    className="btn btn--danger btn--xs"
                    onClick={() => setConfirmDelete(c)}
                    title="Remove caller"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <Modal title="Add New Caller" onClose={() => setShowCreate(false)}>
          <CallerForm
            onSubmit={handleCreate}
            onCancel={() => setShowCreate(false)}
            submitLabel="Create Caller"
          />
        </Modal>
      )}

      {editing && (
        <Modal title={`Edit: ${editing.name}`} onClose={() => setEditing(null)}>
          <CallerForm
            initial={editing}
            onSubmit={handleUpdate}
            onCancel={() => setEditing(null)}
            submitLabel="Save Changes"
          />
        </Modal>
      )}

      {confirmDelete && (
        <Modal title="Confirm Removal" onClose={() => setConfirmDelete(null)} width={400}>
          <div className="confirm-dialog">
            <p>
              Remove <strong>{confirmDelete.name}</strong>? This will pause their account.
              Existing assignments will remain intact.
            </p>
            <div className="form__actions">
              <button className="btn btn--ghost" onClick={() => setConfirmDelete(null)}>
                Cancel
              </button>
              <button
                className="btn btn--danger"
                onClick={handleDelete}
                disabled={deletingId === confirmDelete.id}
              >
                {deletingId === confirmDelete.id ? 'Removing…' : 'Remove'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </section>
  )
}
