# Bug 1.11 — Post-Run-Erklärung: LLM gibt kein kontextuelles Feedback nach Ausführung

**Gefunden**: 2026-04-15
**Status**: Dokumentiert — ⚠️ Architekturentscheidungen noch ausstehend, Fix noch nicht planbar
**Priorität**: 🟡 P3 — Hoher UX-Wert, aber hohe Komplexität (separater Architektur-Entscheid nötig)
**Kategorie**: Backend — `services/message_service.py` + LLM-Prompt-Strategie

---

## Beobachtetes Fehlverhalten

### Beispiel 1 — Label-Encoding von `dteday`

**Nutzeranfrage:** "Mach ein Label-Encoding für die Spalte dteday"

**Aktuelle Ausgabe:**

```
Ergebnis
Ich werde die Spalte dteday mit Label-Encoding in numerische Werte umwandeln.
✓ encode_categorical — Kodiert: dteday
```

**Was der Nutzer wissen möchte (aber nicht erfährt):**
- Wie viele unique Werte hatte `dteday`?
- Auf welche Zahlen wurde was gemappt?
- Ist Label-Encoding für eine Datumsspalte fachlich sinnvoll?
- Was wäre die Alternative?

### Beispiel 2 — Correlation Filter

**Aktuelle Ausgabe (direkt nach Bestätigung):**

```
Ergebnis
Run abgeschlossen
correlation_filter_result (application/octet-stream)
```

Der Nutzer sieht: Datei. Keinerlei Erklärung was passiert ist.
Die korrekte Ergebnisanzeige erscheint erst beim nächsten Step (im Step-Log), nicht als
Konversations-Antwort.

### Grundproblem

Das LLM schreibt sein `explanation`-Feld **vor der Ausführung**. Es kennt das Ergebnis nicht.
Es formuliert eine optimistisch-antizipatorische Erklärung: "Ich werde...".

Nach der Ausführung wird die `explanation` direkt angezeigt — aber nie aktualisiert.
Die realen Step-Ergebnisse (aus `get_metadata()`) erscheinen nur im technischen Step-Log
des `StatusPanel`, aber **nicht als sprachliche Rückmeldung** im Chat.

---

## Technische Ursachenanalyse

### Aktuelle Architektur (execute-Pfad)

```
Nutzer-Nachricht
    ↓
message_service.handle_message()
    ↓
LLM-Anfrage → parsed JSON: {action: "execute", explanation: "Ich werde...", spec: {...}}
    ↓
PipelineExecutor.run(spec) → step_results mit Metadata
    ↓
return {"type": "result", "run_id": ..., "explanation": parsed["explanation"]}
```

Das `explanation`-Feld wird direkt aus dem LLM-Output übernommen — **vor** `PipelineExecutor.run()`.
Die `step_results` werden zurückgegeben, aber das LLM sieht sie nie.

### Was fehlt

Eine **retroaktive Erklärungsphase**: Nach der Pipeline-Ausführung werden die `step_results`
(Metadata) zurück an das LLM gegeben, und das LLM generiert eine inhaltliche Nachbesprechung:

- Was konkret wurde gemacht (aus Metadata)
- Fachliche Einordnung (war das sinnvoll?)
- Proaktive nächste Schritte / Warnungen

---

## Lösungsansatz (diskutiert, noch nicht final entschieden)

### Ansatz A — Zweiter LLM-Call nach jedem `execute`

Nach `PipelineExecutor.run()` wird ein zweiter LLM-Call gestartet mit:

```python
post_run_prompt = f"""
Die Pipeline wurde ausgeführt. Hier sind die Step-Ergebnisse:
{json.dumps(step_results, indent=2)}

Erkläre dem Nutzer in 2-4 Sätzen:
1. Was konkret passiert ist (aus den Ergebnissen ablesen)
2. Ob das Ergebnis fachlich sinnvoll ist
3. Welchen nächsten Schritt du empfiehlst
"""
post_explanation = llm_client.ask(post_run_prompt)
```

**Vorteile:**
- Saubere Trennung: LLM generiert Erklärung mit echten Daten
- Keine Änderung an LLM-Response-Schema nötig
- Rückmeldung ist faktenbasiert (nicht antizipatorisch)

**Nachteile:**
- Zweiter LLM-Call pro execute → doppelte Latenz / Kosten
- Komplexere Fehlerbehandlung (was wenn zweiter Call fehlschlägt?)
- Streaming-Verhalten ändert sich (Nutzer wartet länger)

### Ansatz B — Template-basierte Post-Run-Erklärung (kein LLM)

Step-Metadata wird über ein Erklärungstemplate in lesbaren Text umgewandelt.

```python
_STEP_EXPLANATIONS = {
    "encode_categorical": lambda m: (
        f"{len(m['encoded_columns'])} Spalte(n) wurden encodiert: {', '.join(m['encoded_columns'])}. "
        + ("Hinweis: Label-Encoding für Datumsspalten ist selten sinnvoll." if "dteday" in m["encoded_columns"] else "")
    ),
    "impute_missing": lambda m: ...,
    ...
}
```

**Vorteile:**
- Kein zweiter LLM-Call → keine Latenzerhöhung
- Volle Kontrolle über Erklärungsinhalte
- Deterministisch und testbar

**Nachteile:**
- Kein echtes "Lernerlebnis" — Templates sind statisch
- Wartungsaufwand: jeder neue Step braucht Template
- Kann keine kontextuellen Zusammenhänge erkennen (z.B. "diese Spalte solltest du besser mit time_feature_encoding behandeln")

### Ansatz C — Hybrid: Template für Fakten + LLM für Einordnung

Template für die Fakten-Zusammenfassung (schnell, deterministisch).
Optionaler LLM-Call nur für fachliche Einordnung + Empfehlung (asynchron / lazy).

---

## ⚠️ Ausstehende Architekturentscheidungen

**Bevor dieser Bug implementiert werden kann, müssen folgende Entscheidungen getroffen werden:**

### E1 — Welcher Ansatz wird verfolgt? (A / B / C)

Die Wahl bestimmt den gesamten Implementierungsumfang:
- Ansatz A: Latenz-Akzeptanz klären. Wie lange darf ein execute dauern?
- Ansatz B: Template-Vollständigkeit klären. Für welche Steps werden Templates erstellt?
- Ansatz C: Wann wird der LLM-Call ausgelöst? Sofort oder on-demand?

### E2 — Wie wird die Post-Run-Erklärung im UI angezeigt?

**Option E2a:** Als Teil der existierenden Assistent-Nachricht (ersetze "Ich werde..." durch "Folgendes wurde durchgeführt...")
**Option E2b:** Als separate zweite Assistent-Nachricht nach dem Result-Block
**Option E2c:** Als aufklappbarer Bereich ("Mehr Details...") unterhalb des Result-Blocks

### E3 — Welche fachlichen Hinweise soll das System geben?

Beispiele die Hannes aufgezeigt hat:
- "Label-Encoding für dteday ist selten sinnvoll — time_feature_encoding empfohlen"
- "holiday und weathersit haben IQR=0 — Outlier-Handling nicht geeignet"
- "weathersit hat 0 fehlende Werte — Imputation war nicht notwendig"

Reichen Templates (Ansatz B) für diese Hinweise, oder brauchen wir LLM-Intelligenz (Ansatz A/C)?

### E4 — Kosten-/Latenz-Budget

Bei Ansatz A: Jeder execute-Call löst 2 LLM-Calls aus. Ist das im Rahmen des Projekts akzeptabel?

---

## Auswirkung auf bestehende Architektur

| Komponente | Änderung bei Ansatz A | Änderung bei Ansatz B |
| --- | --- | --- |
| `message_service.py` | Zweiter LLM-Call nach execute | Step-Explanation-Templates einbinden |
| `executor.py` | `step_results` in Return-Wert ausreichend | Keine Änderung |
| Frontend `ResultCard.tsx` | Neues Feld für post-run explanation | Neues Feld für template-basierte Erklärung |
| Frontend `chatReducer.ts` | Neue Message-Typen für Post-Run | Neues Feld in result-Message |
| LLM-Prompt | Post-Run-Prompt-Template nötig | Keine Änderung |

---

## Nächste Schritte

1. **Architektur-Session** mit Hannes: Entscheidungen E1–E4 treffen
2. **Quick-Spec** erstellen basierend auf gewähltem Ansatz
3. **Story** erstellen und implementieren

**Dieser Bug kann erst in Sprint-Planning aufgenommen werden, wenn E1 entschieden ist.**

---

## Dringlichkeit

🟡 P3 — Hoher UX-Wert (Lernerlebnis ist Kernversprechen des Assistenten),
aber Architekturentscheidungen ausstehend. Nach Entscheid-Session
ist der Implementierungsaufwand je nach Ansatz 1–3 Tage.
