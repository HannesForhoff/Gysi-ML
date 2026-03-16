import { useCallback, useRef, useState } from 'react'

type ComposerProps = {
  disabled: boolean
  onSend: (text: string) => void
}

export function Composer({ disabled, onSend }: ComposerProps) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const send = useCallback(() => {
    const trimmed = text.trim()
    if (disabled || trimmed.length === 0) return

    onSend(text)
    setText('')
    queueMicrotask(() => textareaRef.current?.focus())
  }, [disabled, onSend, text])

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
      <div className="composerRow">
        <textarea
          ref={textareaRef}
          className="composerTextarea"
          aria-label="Composer"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Nachricht…"
          autoFocus
        />
        <button
          type="submit"
          className="sendButton"
          disabled={disabled || text.trim().length === 0}
          aria-label="Send"
        >
          {disabled ? 'Senden…' : 'Senden'}
        </button>
      </div>
      <div className="composerHint">Enter = senden, Shift+Enter = neue Zeile</div>
    </form>
  )
}
