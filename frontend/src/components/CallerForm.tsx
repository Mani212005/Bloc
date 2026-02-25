import { useState } from 'react'
import type { Caller, CallerCreate } from '../api'

interface Props {
  initial?: Caller
  onSubmit: (data: CallerCreate) => Promise<void>
  onCancel: () => void
  submitLabel?: string
}

const EMPTY: CallerCreate = {
  name: '',
  role: '',
  languages: [],
  daily_limit: 0,
  assigned_states: [],
  status: 'active',
}

export function CallerForm({ initial, onSubmit, onCancel, submitLabel = 'Save' }: Props) {
  const [form, setForm] = useState<CallerCreate>(
    initial
      ? {
          name: initial.name,
          role: initial.role ?? '',
          languages: initial.languages,
          daily_limit: initial.daily_limit,
          assigned_states: initial.assigned_states,
          status: initial.status,
        }
      : EMPTY,
  )
  const [languagesInput, setLanguagesInput] = useState(form.languages.join(', '))
  const [statesInput, setStatesInput] = useState(form.assigned_states.join(', '))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const parseCSV = (val: string) =>
    val
      .split(',')
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!form.name.trim()) {
      setError('Name is required.')
      return
    }
    if (form.daily_limit < 0) {
      setError('Daily limit must be 0 (unlimited) or a positive number.')
      return
    }

    const payload: CallerCreate = {
      ...form,
      name: form.name.trim(),
      role: form.role?.trim() || undefined,
      languages: parseCSV(languagesInput),
      assigned_states: parseCSV(statesInput),
    }

    setLoading(true)
    try {
      await onSubmit(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate>
      {error && <div className="form__error">{error}</div>}

      <div className="form__row">
        <label className="form__label" htmlFor="cf-name">Name <span className="required">*</span></label>
        <input
          id="cf-name"
          className="form__input"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="e.g. Priya Sharma"
          required
        />
      </div>

      <div className="form__row">
        <label className="form__label" htmlFor="cf-role">Role</label>
        <input
          id="cf-role"
          className="form__input"
          value={form.role ?? ''}
          onChange={(e) => setForm({ ...form, role: e.target.value })}
          placeholder="e.g. Senior Sales Executive"
        />
      </div>

      <div className="form__row">
        <label className="form__label" htmlFor="cf-langs">Languages</label>
        <input
          id="cf-langs"
          className="form__input"
          value={languagesInput}
          onChange={(e) => setLanguagesInput(e.target.value)}
          placeholder="e.g. english, hindi, marathi"
        />
        <span className="form__hint">Comma-separated list</span>
      </div>

      <div className="form__row">
        <label className="form__label" htmlFor="cf-states">Assigned States</label>
        <input
          id="cf-states"
          className="form__input"
          value={statesInput}
          onChange={(e) => setStatesInput(e.target.value)}
          placeholder="e.g. maharashtra, karnataka"
        />
        <span className="form__hint">Comma-separated list. Leave blank for global assignment.</span>
      </div>

      <div className="form__row">
        <label className="form__label" htmlFor="cf-limit">Daily Lead Limit</label>
        <input
          id="cf-limit"
          className="form__input form__input--short"
          type="number"
          min={0}
          value={form.daily_limit}
          onChange={(e) => setForm({ ...form, daily_limit: Number(e.target.value) })}
        />
        <span className="form__hint">Set to 0 for unlimited.</span>
      </div>

      <div className="form__row">
        <label className="form__label" htmlFor="cf-status">Status</label>
        <select
          id="cf-status"
          className="form__select"
          value={form.status}
          onChange={(e) => setForm({ ...form, status: e.target.value as 'active' | 'paused' })}
        >
          <option value="active">Active</option>
          <option value="paused">Paused</option>
        </select>
      </div>

      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onCancel} disabled={loading}>
          Cancel
        </button>
        <button type="submit" className="btn btn--primary" disabled={loading}>
          {loading ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  )
}
