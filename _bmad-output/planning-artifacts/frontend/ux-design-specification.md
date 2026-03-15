---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/prd_frontend.md
---

# UX Design Specification gysi-ml

**Author:** Hannes
**Date:** 2026-03-15

---

<!-- UX design content will be appended sequentially through collaborative workflow steps -->

## Executive Summary

### Project Vision

gysi-ml soll ML-Workflows für den Bike-Datensatz so zugänglich machen, dass Nutzer ihre Absicht in natürlicher Sprache äußern können – und das System daraus nachvollziehbare, reproduzierbare Schritte macht.
Die UX muss das Kernprinzip „LLM als Übersetzer, Backend als deterministischer Executor“ sichtbar machen: Das UI zeigt klar, was nur ein Vorschlag ist und was tatsächlich ausgeführt wurde.

### Target Users

- Hannes (Developer/Builder): will schnell eine Session starten, Prompts testen, Proposal-Flow demonstrieren, Runs vergleichen und Artefakte öffnen – ohne Postman.
- Evaluator (Prof/WiMi): will ohne Tooling-Hürden prüfen, ob das System methodisch sauber und didaktisch sinnvoll wirkt (Proposal statt Raten, Bestätigung vor Ausführung, reproduzierbare Ergebnisse).

**Device Context (bindend):** Desktop/Laptop (kein Mobile-Fokus im MVP).

### Key Design Challenges

- Vertrauen & Klarheit: Proposal vs. Ergebnis müssen visuell und sprachlich eindeutig getrennt sein.
- Zustandsführung ohne Komplexität: Single-Page-UI mit klaren States (idle, sending, proposal_pending, polling, done, failed, validation_error, backend_unreachable).
- Run-Handling: Polling-UX ohne „aggressives Autoscroll“, ohne doppeltes Confirm, mit verständlichem Verhalten bei Long Runs.
- Nachvollziehbarkeit ohne Spec-Editor: Spec nur als Summary (Version + Step-Liste), trotzdem „genug Transparenz“ für Evaluator.
- Fehler robust erklären: Validation-Errors, Run-Fails, Backend down – ohne UI-Deadends.

### Design Opportunities

- Didaktischer „Aha“-Moment: Das UI inszeniert den Ablauf als bewusstes Ritual: Vorschlag → Entscheidung → Ausführung → Beleg (Metriken/Artefakte).
- Transparenz als Differenzierer: Ein klares Status-Panel (Spec-Version, Steps, letzter Run) macht „Reproduzierbarkeit“ greifbar.
- Minimalismus mit Wirkung: Wenige UI-Elemente, aber stark semantisch (Proposal-Card, Confirm-CTA, Run-Status-Chip, Artefakt-Linkliste).

## Core User Experience

### Defining Experience

Die Kern-Erfahrung ist ein bewusstes, nachvollziehbares Ritual:

1. Nutzer formuliert eine Absicht als Chat-Nachricht.
2. Das System antwortet typisiert:
   - `proposal`: zeigt einen konkreten Plan (Steps/Parameter) und verlangt explizite Bestätigung
   - `result`: liefert direkt ein Ergebnis (z.B. wenn sofort fertig)
   - `error`: liefert validierbare Fehlerdetails (ohne die UX zu blockieren)
3. Bei `proposal` entscheidet der Nutzer aktiv via „Bestätigen & Ausführen“.
4. Ein Run startet (oder ist sofort fertig); die UI zeigt Status und pollt nur wenn nötig.
5. Nach Abschluss sind Metriken + Artefakte sichtbar und per Link abrufbar (neuer Tab genügt).
6. Nutzer iteriert: neue Nachricht → ggf. neue Spec-Version → neuer Run.

Das UI kommuniziert jederzeit klar: „Vorschlag“ ≠ „Ausgeführt“.

### Platform Strategy

- Plattform: Desktop/Laptop, Single-Page-Web-App (mouse/keyboard-first).
- Kein Offline-Mode im MVP.
- Artefakte werden als Links geöffnet (neuer Tab).
- Backend-Anbindung:
  - Reachability über `GET /v1/health` (sichtbarer Backend-Status).
  - Backend-Base-URL ist Konfiguration (env/build-time), nicht als User-Setting im MVP.
- Run-Handling:
  - UI unterstützt beide Fälle: sofort terminales Ergebnis ODER `run_id` + Polling bis `done|failed`.

### Effortless Interactions

- Session-Start ist „unsichtbar“: UI ist sofort bereit (Session auto-create oder beim ersten Senden).
- Senden via Enter, neue Zeile via Shift+Enter.
- Während Requests: eindeutiger Ladezustand, kein doppeltes Senden.
- Proposal wird als Card im Chat dargestellt:
  - Step-Liste + Parameter-Summary
  - ein dominanter CTA „Bestätigen & Ausführen“
  - keine extra Formulare: „Ändern“ erfolgt über neue Chat-Nachricht
- Confirm ist idempotent auf UI-Seite: Button disabled während Request.
- Polling aktualisiert Status-Panel (und ggf. eine Run-Zeile), ohne die Message-Liste aggressiv zu scrollen.
- Artefakte sind mit Label + Media-Type erkennbar, ein Klick öffnet.

### Critical Success Moments

- Moment 1 (Vertrauen): Erste `proposal`-Antwort ist sichtbar als Vorschlag markiert + klare Bestätigungspflicht.
- Moment 2 (Kontrolle): Klick auf Confirm führt zu sofort sichtbarem Statuswechsel (`running|queued`).
- Moment 3 (Beleg): Run wird `done` und zeigt Metriken + mindestens ein Artefakt-Link, der wirklich öffnet.
- Moment 4 (Reproduzierbarkeit): Spec-Summary zeigt neue Version/Steps nach einer Änderung (greifbarer Fortschritt).
- Make-or-break: Kein „stiller“ Run ohne Bestätigung; keine UI-Deadends bei Fehlern.

### Experience Principles

- Vorschlag vs. Ausführung immer trennscharf.
- Nutzerentscheidung ist heilig: ohne Confirm keine Ausführung.
- Status ist immer auffindbar (Backend, Spec-Summary, letzter Run).
- Keine Deadends: nach Fehlern sofort weiter chatten können.
- Minimal UI, maximale Semantik (wenige Elemente, aber eindeutig benannt/typisiert).
- Polling ist ruhig und respektiert Lesefluss (keine Scroll-Sprünge).

## Desired Emotional Response

### Primary Emotional Goals

- Vertrauen & Seriosität: „Das System rät nicht – es erklärt, was es tun will, und führt nur nach Bestätigung aus.“
- Kontrolle & Selbstwirksamkeit: Nutzer bleibt Entscheider (Proposal → Confirm), Änderungen sind jederzeit über neue Chat-Nachricht möglich.
- Klarheit & Ruhe: Zustände sind eindeutig, UI bleibt stabil (kein hektisches Springen/Autoscroll, keine versteckten Aktionen).
- Stolz/Erfolgserlebnis: Nach einem Run fühlt sich das Ergebnis „echt“ an (Metriken + Artefakte als Beleg, Spec-Version als Fortschritt).

### Emotional Journey Mapping

- Einstieg (erste Ansicht): ruhig, aufgeräumt, „ich kann einfach loslegen“.
- Erste Nachricht senden: „ich werde verstanden“ (keine Angst, etwas kaputt zu machen).
- Proposal erhalten: „aha – es ist ein Vorschlag“ (Klarheit, Vertrauen).
- Confirm klicken: „ich entscheide“ (Kontrolle).
- Run läuft: „es arbeitet, ich sehe den Status“ (Gelassenheit statt Unsicherheit).
- Run fertig: „ich habe ein Ergebnis, das ich prüfen kann“ (Erfolg + Nachvollziehbarkeit).
- Wenn etwas schiefgeht: „ich weiß warum, und ich kann direkt weitermachen“ (Sicherheit statt Frust).
- Wiederkommen: „iterieren ist leicht“ (Momentum).

### Micro-Emotions

- Confidence statt Confusion: immer klare Typisierung (`proposal|result|error`) und klare Statusanzeige.
- Trust statt Skepticism: keine stillen Runs, keine „magischen“ Änderungen ohne sichtbaren Anlass.
- Calm Focus statt Anxiety: Polling ist leise, UI bleibt lesbar und stabil.
- Accomplishment statt Frustration: Ergebniszusammenfassung + Artefakt-Links sind sofort greifbar.

### Design Implications

- Vertrauen:
  - Proposal visuell eindeutig als „Vorschlag (nicht ausgeführt)“ markieren.
  - Confirm als bewusste Aktion mit eindeutigem CTA; während Request disabled.
  - Nach Run: klarer Übergang zu „Ausgeführt“-Darstellung (Status `done|failed`).
- Kontrolle:
  - „Ändern“ ist immer möglich durch neue Nachricht (kein Zwang zur Bestätigung).
  - Kein doppeltes Confirm (UI-seitig abgesichert).
- Klarheit/Ruhe:
  - Zustände sind sichtbar (`sending`, `proposal_pending`, `polling`, `done`, `failed`, `validation_error`, `backend_unreachable`).
  - Polling aktualisiert Status/Panel ohne Lesefluss zu zerstören.
- Sicherheit bei Fehlern:
  - Validation/Backend down/Run failed werden als verständliche, handlungsfähige Zustände gerendert (keine Sackgassen).

### Emotional Design Principles

- Explain-before-act: erst erklären, dann handeln (Bestätigungsprinzip).
- Always-orient: Nutzer weiß jederzeit „wo wir sind“ (Status + letzter Run + Spec-Summary).
- No-surprises: keine versteckten Aktionen, keine stillen Runs.
- Errors are teachable: Fehler sind klar, kurz und mit nächstem Schritt (weiter chatten) verbunden.
