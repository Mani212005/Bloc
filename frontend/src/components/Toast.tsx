import { useEffect, useState } from 'react'

export type ToastType = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  message: string
  type: ToastType
}

let _setToasts: React.Dispatch<React.SetStateAction<Toast[]>> | null = null
let _counter = 0

export function showToast(message: string, type: ToastType = 'success') {
  _setToasts?.((prev) => [...prev, { id: ++_counter, message, type }])
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([])
  _setToasts = setToasts

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDone={() => setToasts((p) => p.filter((x) => x.id !== t.id))} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onDone }: { toast: Toast; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 3500)
    return () => clearTimeout(timer)
  }, [onDone])

  return (
    <div className={`toast toast--${toast.type}`}>
      <span>{toast.message}</span>
      <button className="toast__close" onClick={onDone}>✕</button>
    </div>
  )
}
