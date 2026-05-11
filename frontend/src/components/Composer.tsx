import { useCallback, useRef } from 'react'

type ComposerProps = {
  disabled: boolean
  onSend: (text: string) => void
  value: string
  onChange: (text: string) => void
  suggestions?: string[]
}

export function Composer({ disabled, onSend, value, onChange, suggestions }: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const send = useCallback(() => {
    const trimmed = value.trim()
    if (disabled || trimmed.length === 0) return

    onSend(value)
    queueMicrotask(() => textareaRef.current?.focus())
  }, [disabled, onSend, value])

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key !== 'Enter') return
      if (e.shiftKey) return
      e.preventDefault()
      send()
    },
    [send],
  )

  const onSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      send()
    },
    [send],
  )

  return (
    <form className="composer" onSubmit={onSubmit}>
      {suggestions && suggestions.length > 0 && (
        <div className="composerSuggestions" aria-label="Vorschläge">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              className="composerSuggestionChip"
              disabled={disabled}
              onClick={() => onSend(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}
      <div className="composerRow">
        <textarea
          ref={textareaRef}
          className="composerTextarea"
          aria-label="Composer"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Nachricht…"
          autoFocus
        />
        <button
          type="submit"
          className="sendButton"
          disabled={disabled || value.trim().length === 0}
          aria-label="Send"
        >
          {disabled ? 'Senden…' : 'Senden'}
        </button>
      </div>
      <div className="composerHint">Enter = senden, Shift+Enter = neue Zeile</div>
    </form>
  )
}
