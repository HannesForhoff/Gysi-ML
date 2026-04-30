# Bug 1.13 — Composer-Draft geht bei Tab-Wechsel verloren

**Gefunden**: 2026-04-25
**Status**: ✅ Gefixt (2026-04-30)
**Priorität**: 🟠 Mittel-Hoch (betrifft primäre Zielgruppe im Hauptarbeitsfluss)
**Kategorie**: Frontend (`Composer.tsx`, `App.tsx`, `ChatLayout.tsx`)
**Analysiert von**: Party-Mode Session (Sally/John/Winston), 2026-04-25

---

## Beobachtetes Fehlverhalten

| Aktion | Erwartetes Verhalten | Tatsächliches Verhalten |
|---|---|---|
| Text in Composer eingeben, dann zu „Daten"-Tab wechseln, zurückkehren | Eingetippter Text ist noch vorhanden | Textarea ist leer — Text verloren |
| Text in Composer eingeben, dann zu „Artefakte & Steps"-Tab wechseln, zurückkehren | Eingetippter Text ist noch vorhanden | Textarea ist leer — Text verloren |

**Reproduktionsschritte:**

1. App öffnen, Chat-Tab aktiv
2. Beliebigen Text in die Composer-Textarea tippen (nicht absenden)
3. Auf Tab „Daten" oder „Artefakte & Steps" klicken
4. Zurück zu „Chat" klicken
5. → Textarea ist leer

---

## Warum ist das für die Zielgruppe besonders problematisch?

Die primäre Zielgruppe sind **unerfahrene Studierende ohne ML-Vorwissen**. Diese Nutzer:innen:

- müssen beim Formulieren ihrer Anfrage häufig zwischen Tabs wechseln, um Spaltennamen, Datentypen oder bereits ausgeführte Steps nachzuschlagen
- bauen Kontext schrittweise auf, bevor sie eine vollständige Anfrage formulieren können
- sind auf ein exploratives Hin-und-Her angewiesen — genau dieses Verhalten wird durch den Bug bestraft

Der Verlust des Drafts unterbricht den Denkfluss, erzwingt das erneute Eintippen und führt zu schlechter formulierten Anfragen — was die Qualität der ML-Pipeline-Ergebnisse direkt negativ beeinflusst.

---

## Technische Ursachenanalyse

**Datei:** `frontend/src/components/Composer.tsx`

**Ursache:** Der Draft-Text wird als lokaler `useState` in `Composer.tsx` gehalten:

```tsx
// Composer.tsx
export function Composer({ disabled, onSend }: ComposerProps) {
  const [text, setText] = useState('')  // ← lokaler State
  ...
}
```

**Datei:** `frontend/src/components/ChatLayout.tsx`

`ChatLayout.tsx` rendert die Tabs exklusiv per bedingtem Rendering:

```tsx
// ChatLayout.tsx
{activeTab === 'chat' ? children : activeTab === 'data' ? dataPane : infoPane}
```

Beim Tab-Wechsel von `'chat'` zu einem anderen Tab wird `children` (welches `Composer` enthält) vollständig **unmountet**. React verwirft die Komponente und damit deren lokalen `useState`. Bei Rückkehr zum Chat-Tab wird `Composer` neu gemountet — mit dem Initialwert `''`.

---

## Empfohlener Fix — Option A: State hochziehen (Lift State Up)

**Strategie:** Den `draftText`-State von `Composer.tsx` in `App.tsx` hochziehen. `Composer` erhält `value` und `onChange` als Props und wird zur controlled component. Da `App.tsx` über Tab-Wechsel hinweg persistiert, überlebt der Draft-Text jeden Tab-Wechsel.

**Änderungsumfang:** Zwei Dateien, minimaler Eingriff — kein neues Konzept, kein neues Pattern, kein Risiko.

### Schritt 1 — `App.tsx`: `draftText`-State hinzufügen

```tsx
// App.tsx — neuer State (direkt neben den übrigen useState-Calls)
const [draftText, setDraftText] = useState('')
```

`handleSend` anpassen, sodass der Draft nach dem Senden geleert wird:

```tsx
const handleSend = useCallback(
  async (text: string) => {
    if (state.ui.type === 'sending_message') return
    setDraftText('')  // ← Draft leeren nach Absenden
    // ... restlicher handleSend-Code unverändert
  },
  [state.sessionId, state.ui.type],
)
```

`Composer` in der JSX mit den neuen Props aufrufen:

```tsx
<Composer
  disabled={isSending}
  onSend={handleSend}
  value={draftText}           // ← neu
  onChange={setDraftText}     // ← neu
/>
```

### Schritt 2 — `Composer.tsx`: Auf controlled component umstellen

Props-Interface erweitern und lokalen State entfernen:

```tsx
type ComposerProps = {
  disabled: boolean
  onSend: (text: string) => void
  value: string               // ← neu (controlled)
  onChange: (text: string) => void  // ← neu
}

export function Composer({ disabled, onSend, value, onChange }: ComposerProps) {
  // const [text, setText] = useState('')  ← ENTFERNEN

  const send = useCallback(() => {
    const trimmed = value.trim()
    if (disabled || trimmed.length === 0) return
    onSend(value)
    // setText('') ← ENTFERNEN (App.tsx übernimmt das Leeren)
  }, [disabled, onSend, value])

  // onChange im textarea:
  // onChange={(e) => onChange(e.target.value)}  ← statt setText
}
```

---

## Verworfene Alternativen

| Option | Beschreibung | Bewertung |
|---|---|---|
| **B — CSS `display:none`** | Alle Tabs immer im DOM, per CSS versteckt | Löst das Problem, aber rendert `DataViewPanel` und `InfoPanel` beim initialen Load — erzeugt unnötige API-Calls. ⚠️ Overhead ohne Mehrwert. |
| **C — `localStorage`/`sessionStorage`** | Draft persistent im Browser speichern | Overkill, Edge Cases bei mehreren Tabs offen, kein echtes User-Need für Browser-übergreifende Persistenz. ❌ Nicht empfohlen. |

---

## Akzeptanzkriterien

- [ ] Text, der im Composer eingetippt wurde, überlebt einen Tab-Wechsel zu „Daten" und zurück zu „Chat" vollständig
- [ ] Text, der im Composer eingetippt wurde, überlebt einen Tab-Wechsel zu „Artefakte & Steps" und zurück zu „Chat" vollständig
- [ ] Nach dem Absenden einer Nachricht ist die Textarea leer (Verhalten unverändert)
- [ ] Bestehende Tests für `Composer` und `App` laufen weiterhin grün

---

## Nice-to-Have (nicht Bestandteil des Fixes)

**Draft-Indikator im Chat-Tab:** Wenn `draftText.trim().length > 0` und der aktive Tab nicht `'chat'` ist, könnte ein kleiner visueller Indikator am Chat-Tab-Button signalisieren, dass ein unfertiger Draft wartet. Niedriger Aufwand, erhöht Transparenz für Nutzer:innen. Als separates Ticket einzuplanen.
