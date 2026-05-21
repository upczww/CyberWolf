import { useEffect } from 'react'

interface Props {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  /** 'danger' = red destructive confirm button; 'gold' = primary; default = neutral. */
  tone?: 'default' | 'danger' | 'gold'
  onConfirm: () => void
  onCancel: () => void
}

/**
 * In-app replacement for `window.confirm`. Themed to match the rest of
 * the UI (matches .info-dialog chrome), backdrop click + Escape both
 * cancel, Enter confirms.
 */
export default function ConfirmDialog({
  title,
  message,
  confirmLabel = '确定',
  cancelLabel = '取消',
  tone = 'default',
  onConfirm,
  onCancel,
}: Props) {
  // Keyboard: Esc cancels, Enter confirms.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCancel()
      } else if (e.key === 'Enter') {
        e.preventDefault()
        onConfirm()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel, onConfirm])

  return (
    <section className="confirm-backdrop" onClick={onCancel} role="dialog" aria-modal="true">
      <article className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        <p>{message}</p>
        <div className="confirm-actions">
          <button className="confirm-btn ghost" onClick={onCancel}>{cancelLabel}</button>
          <button className={`confirm-btn ${tone}`} onClick={onConfirm} autoFocus>
            {confirmLabel}
          </button>
        </div>
      </article>
    </section>
  )
}
