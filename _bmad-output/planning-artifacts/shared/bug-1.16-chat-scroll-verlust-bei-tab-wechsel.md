# Bug 1.16 — Chat-Scroll-Position geht bei Tab-Wechsel verloren

**Gefunden**: 2026-04-25
**Status**: ✅ Gefixt
**Priorität**: 🟡 Mittel (UX-Verlust, kein Datenverlust)
**Kategorie**: Frontend (`ChatLayout.tsx`)
**Session**: Party-Mode-Analyse 25.04.2026 — Diskussion mit Amelia (Dev), Sally (UX), Quinn (QA)

---

## Beobachtetes Fehlverhalten

Bei längeren Konversationen scrollt der Chat nach dem Zurückwechseln aus dem Tab „Daten" oder
„Artefakte & Steps" wieder ganz nach oben, statt an der zuletzt besuchten Position zu verbleiben.

**Reproduktion:**

1. Mindestens ~8–10 Messages senden, sodass die Nachrichtenliste scrollbar wird
2. Zum Ende der Konversation scrollen (neuester Stand sichtbar)
3. Tab „Daten" oder „Artefakte & Steps" anklicken
4. Zurück zu „Chat" wechseln
5. **Ergebnis:** Chat startet bei Message 1 oben — Erwartung: neuester Stand / letzte Position

---

## Technische Ursache

In [`ChatLayout.tsx`](../../../../frontend/src/components/ChatLayout.tsx) wurde der Tab-Inhalt
per **conditional rendering** gesteuert:

```tsx
{activeTab === 'chat' ? children : activeTab === 'data' ? dataPane : infoPane}
```

Beim Tab-Wechsel wird der Chat-Subtree vollständig aus dem DOM entfernt (`unmount`) und beim
Zurückwechseln neu eingehängt (`remount`). Ein neu gemountetes DOM-Element hat keine gespeicherte
Scroll-Position — der Browser setzt sie auf `0` zurück.

---

## Verworfene Alternativen

### Option B — `useEffect`-basierter Bottom-Scroll

Beim Aktivieren des Chat-Tabs via `useEffect` zum letzten Element scrollen.

**Verworfen weil:**

- Nimmt dem User die Scroll-Kontrolle weg (bevormundend)
- Race condition möglich: `useEffect` feuert bevor neugerenderte Liste messbar ist
- Erzwingt immer Bottom-Scroll, auch wenn der User absichtlich oben gelesen hat

### Option A (vollständig) — Alle Tabs persistiert per `display: none`

Alle drei Panels (Chat, Daten, Info) immer im DOM, nur per CSS versteckt.

**Verworfen weil:**

- DataViewPanel und InfoPanel machen API-Calls beim Mount
- Würde unnötige Backend-Requests beim ersten Seitenload auslösen
- Höhere DOM-Komplexität ohne zusätzlichen Nutzen

---

## Gewählter Fix — Hybrid (Option A nur für Chat-Tab)

Nur der Chat-Tab wird persistent im DOM gehalten. Data- und Info-Panel bleiben conditional
gerendert (lazy), da nur der Chat-Tab von Scroll-Verlust betroffen ist.

**Geändertes File:** [`frontend/src/components/ChatLayout.tsx`](../../../../frontend/src/components/ChatLayout.tsx)

**Vorher:**

```tsx
<div className="tabContent">
  {activeTab === 'chat' ? children : activeTab === 'data' ? dataPane : infoPane}
</div>
```

**Nachher:**

```tsx
{/* Chat bleibt immer im DOM – verhindert Scroll-Verlust bei Tab-Wechsel (bug-1.16) */}
<div className="tabContent" style={{ display: activeTab === 'chat' ? undefined : 'none' }}>
  {children}
</div>
{activeTab === 'data' && <div className="tabContent">{dataPane}</div>}
{activeTab === 'info' && <div className="tabContent">{infoPane}</div>}
```

---

## Bewertung

| Kriterium | Bewertung |
| --- | --- |
| Severity | Mittel — kein Datenverlust, UX-Unterbrechung |
| Priority | Hoch — trifft bei jedem Tab-Wechsel in langen Sessions |
| Risiko des Fixes | Niedrig — nur Chat-Tab betroffen, Data/Info unverändert lazy |
| Regressions-Risiko | Niedrig — no API-Call-Änderungen, nur Rendering-Strategie |
| Testbarkeit | Manuell reproduzierbar, kein automatisierter Test nötig |
