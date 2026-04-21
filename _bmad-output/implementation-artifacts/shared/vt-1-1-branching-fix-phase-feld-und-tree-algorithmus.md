# Story VT-1.1: Branching-Fix, Phase-Feld und Tree-Algorithmus (Fundament)

Status: done

## Story

Als Nutzer,
möchte ich im Versionsbaum echte Abzweigungen sehen wenn ich einen Rollback mache und danach weiterarbeite,
damit ich klar erkennen kann welche Änderungen auf welchem Ast entstanden sind — und nicht einer falschen linearen Liste folge.

## Acceptance Criteria

1. **[Branching-Fix: echter Fork bei Rollback]** Nach einem Rollback auf vX und anschließender Arbeit zweigt der Baum korrekt bei vX ab: die neue Rollback-Version hat `parent_spec_id = target_spec_id` (also die ID der Version auf die zurückgerollt wurde) — nicht die ID der zuletzt aktiven Version vor dem Rollback.

2. **[Phase-Feld im Tree-Response]** `GET /v1/sessions/{id}/spec/tree` liefert pro `VersionNode` ein `phase`-Feld: `"modeling"` wenn mindestens ein enabled Step vom Typ `train_decision_tree`, `train_ebm` oder `catboost_feature_selection` enthalten ist — sonst `"preprocessing"`.

3. **[Phase im Frontend-Typ]** `VersionNode` in `types.ts` hat `phase: string`, `parseVersionNode()` in `healthApi.ts` parst das Feld (Fallback: `"preprocessing"` wenn Feld fehlt).

4. **[Tree-Algorithmus]** Neue Utility-Funktion `buildVersionTree(versions: VersionNode[]): DisplayNode[]` in `frontend/src/utils/buildVersionTree.ts`. Gibt Nodes in Pre-Order-DFS-Reihenfolge zurück, jeder mit zusätzlichem `depth: number` (Abstand von der Wurzel, root = 0). Bei mehreren Root-Nodes (lückenhafte parent_spec_id) werden alle als depth=0 behandelt.

5. **[Interim-Darstellung: eingerückter Baum]** `SpecHistoryPanel` nutzt `buildVersionTree()` und zeigt Nodes in Baumreihenfolge, eingerückt per `depth × 12px` linker Margin. Phase-Badge (`Preprocessing` / `Modeling`) wird pro Node angezeigt. Rollback-Nodes (change_summary beginnt mit "Rollback") erhalten ein `↩`-Icon. Alle anderen Funktionen (Rollback-Button, Aktiv-Badge, Run-Dot) bleiben erhalten.

6. **[historyPane breiter]** Grid-Spalte in `App.css` von `200px` auf `260px` verbreitert (`.layout` grid-template-columns).

7. **[Test: Branching-Fix]** Bestehender Test `test_rollback_correct_parent_spec_id` in `backend/tests/integration/test_rollback.py` an neue Semantik angepasst: `parent_spec_id` der neuen Version == `v1["spec_id"]` (Rollback-Ziel), nicht `v3["spec_id"]`.

8. **[Test: Phase-Feld]** Integrations-Test in `test_spec_tree.py`: Spec mit `train_decision_tree`-Step → `phase == "modeling"`, Spec ohne Modeling-Step → `phase == "preprocessing"`.

9. **[Test: buildVersionTree]** Unit-Tests in `frontend/src/utils/buildVersionTree.test.ts`: eine lineare Kette, ein echter Branch (Rollback), mehrere Branches — jeweils korrekte `depth`- und Reihenfolge-Prüfung.

## Tasks / Subtasks

- [x] **T1 — Backend: `rollback_to()` Branching-Fix** (AC: 1, 7)
  - [x] Datei: `backend/src/gysi_ml/persistence/spec_repository.py`
  - [x] In `rollback_to()`: `parent_spec_id = current_row["spec_id"]` → `parent_spec_id = target_spec_id`
  - [x] Der separate Query für `current_row` (der nach `parent_spec_id` sucht) kann entfallen — `new_version` für die Versionsnummer weiterhin aus dem letzten Eintrag ableiten (Query für `current_row` nur für Versionsnummer-Berechnung behalten)
  - [x] Test `test_rollback_correct_parent_spec_id`: Assertion anpassen: `new_entry["parent_spec_id"] == v1["spec_id"]` (statt `v3["spec_id"]`)

- [x] **T2 — Backend: `phase`-Feld im Tree-Endpoint** (AC: 2, 8)
  - [x] Datei: `backend/src/gysi_ml/persistence/spec_repository.py`
  - [x] `get_all_specs_for_session()` — `spec_json` zur SELECT-Liste hinzufügen (war bisher nicht dabei)
  - [x] Datei: `backend/src/gysi_ml/api/schemas.py`
  - [x] `VersionNodeResponse` um `phase: str = "preprocessing"` ergänzen
  - [x] Datei: `backend/src/gysi_ml/api/routes/specs.py`
  - [x] `get_spec_tree()` — pro Spec `spec_json` parsen, `_derive_phase(spec_dict)` aufrufen
  - [x] Test in `test_spec_tree.py`: vier Phase-Tests hinzugefügt

- [x] **T3 — Frontend: `VersionNode`-Typ und Parser erweitern** (AC: 3)
  - [x] Datei: `frontend/src/types.ts`
  - [x] `VersionNode` um `phase: string` ergänzen
  - [x] Datei: `frontend/src/api/healthApi.ts`
  - [x] `parseVersionNode()` — `phase: typeof item.phase === 'string' ? item.phase : 'preprocessing'` hinzugefügt

- [x] **T4 — Frontend: `buildVersionTree` Utility** (AC: 4, 9)
  - [x] Datei: `frontend/src/utils/buildVersionTree.ts` — erstellt
  - [x] Interface `DisplayNode` exportiert (extends `VersionNode`, fügt `depth: number` hinzu)
  - [x] Funktion `buildVersionTree(versions: VersionNode[]): DisplayNode[]` implementiert
  - [x] Datei: `frontend/src/utils/buildVersionTree.test.ts` — erstellt
  - [x] 7 Tests: leere Liste, einzelner Node, lineare Kette, zwei-Kind-Branch, Rollback-Branch, mehrere Roots, Felder-Erhalt

- [x] **T5 — Frontend: `SpecHistoryPanel` auf Baum-Darstellung umstellen** (AC: 5)
  - [x] Datei: `frontend/src/components/SpecHistoryPanel.tsx`
  - [x] `buildVersionTree()` aufgerufen mit `specHistory.versions`
  - [x] `<ul>` iteriert über `DisplayNode[]` (kein `.reverse()` mehr)
  - [x] Jede `<li>` erhält `style={{ marginLeft: node.depth * 12 }}` als Einzug
  - [x] Phase-Badge hinzugefügt mit Template-Literal-Klasse
  - [x] Rollback-Erkennung über `change_summary?.startsWith('Rollback')` → `↩`-Icon
  - [x] Rollback-Button, Aktiv-Badge, Run-Dot unverändert

- [x] **T6 — Frontend: `historyPane` verbreitern + Phase-Badge CSS** (AC: 6)
  - [x] Datei: `frontend/src/App.css`
  - [x] `.layout` grid-template-columns: `200px` → `260px` (letzte Spalte)
  - [x] Neue CSS-Klassen `.historyPhaseBadge`, `.historyPhaseBadge--preprocessing`, `.historyPhaseBadge--modeling` ans Ende des History-Panel-Abschnitts angefügt

## Dev Notes

### Warum der Branching-Fix notwendig ist

Story 8.3 AC2 definierte `parent_spec_id = aktuelle Spec-ID vor Rollback`. Das war korrekt für eine lineare Ansicht, macht echtes Branching aber unmöglich. Wenn man z.B. v4 hat, auf v2 zurückrollt (→ v5) und dann weiterarbeitet (→ v6), soll der Baum zeigen:

```
v1 → v2 → v3 → v4
      ↘
       v5 → v6
```

Mit dem alten Code entsteht stattdessen eine lange lineare Kette: `v1→v2→v3→v4→v5→v6`. Story VT-1.1 löst das. Story 8.3 AC2 ist damit **überschrieben**.

### Scope: nur was der Tree-Algo braucht

`get_all_specs_for_session()` gibt bisher KEIN `spec_json` zurück. Das ist der einzige Backend-Query der angepasst werden muss. Kein neuer Endpunkt, kein neues Schema außer den Ergänzungen.

### `buildVersionTree` — Algorithmus-Skizze

```typescript
export interface DisplayNode extends VersionNode {
  depth: number
}

export function buildVersionTree(versions: VersionNode[]): DisplayNode[] {
  if (versions.length === 0) return []

  const byId = new Map(versions.map(v => [v.spec_id, v]))
  const children = new Map<string, VersionNode[]>()
  const roots: VersionNode[] = []

  for (const v of versions) {
    if (v.parent_spec_id && byId.has(v.parent_spec_id)) {
      const arr = children.get(v.parent_spec_id) ?? []
      arr.push(v)
      children.set(v.parent_spec_id, arr)
    } else {
      roots.push(v)
    }
  }

  const result: DisplayNode[] = []
  function dfs(node: VersionNode, depth: number) {
    result.push({ ...node, depth })
    const kids = children.get(node.spec_id) ?? []
    for (const child of kids) dfs(child, depth + 1)
  }
  for (const root of roots) dfs(root, 0)
  return result
}
```

### SpecHistoryPanel: Reihenfolge nicht umkehren

Die aktuelle Implementierung macht `.reverse()` auf die Versionen-Liste um neueste oben darzustellen. Mit dem Baum-Algorithmus IST die DFS-Reihenfolge bereits die visuell sinnvolle Reihenfolge (Branches nach ihrer Entstehung). Das `.reverse()` entfernen.

### Zu ändernde Dateien

| Datei | Art |
|---|---|
| `backend/src/gysi_ml/persistence/spec_repository.py` | `rollback_to()` 1 Zeile + `get_all_specs_for_session()` spec_json |
| `backend/src/gysi_ml/api/schemas.py` | `phase` Feld in `VersionNodeResponse` |
| `backend/src/gysi_ml/api/routes/specs.py` | `_derive_phase()` + Verwendung in `get_spec_tree()` |
| `backend/tests/integration/test_rollback.py` | AC2-Test-Assertion anpassen |
| `backend/tests/integration/test_spec_tree.py` | Phase-Test hinzufügen |
| `frontend/src/types.ts` | `phase` in `VersionNode` |
| `frontend/src/api/healthApi.ts` | `phase` in `parseVersionNode()` |
| `frontend/src/utils/buildVersionTree.ts` | NEU: Algorithmus |
| `frontend/src/utils/buildVersionTree.test.ts` | NEU: Tests |
| `frontend/src/components/SpecHistoryPanel.tsx` | Baum-Darstellung |
| `frontend/src/App.css` | Grid-Breite + Phase-Badge CSS |

## Dev Agent Record

### Debug Log

- **Vorbestehender Fehler `test_rollback_creates_new_version`**: Nicht durch VT-1.1 verursacht. Ursache: Windows-Timer-Auflösung (~10ms) → drei schnell aufeinanderfolgende `datetime.now()` Calls in Tests haben identische `created_at`-Werte → `ORDER BY created_at DESC LIMIT 1` nicht deterministisch. Fix: `rowid DESC`-Tiebreaker in `get_latest_spec()` und `rollback_to()` hinzugefügt (korrektives Bugfix).
- **Vorbestehende Frontend-Fehler**: `App.test.tsx`, `chatReducer.tab.test.ts`, `ResultCard.test.tsx`, `realTransport.test.ts` — alle vorbestehend, keiner durch VT-1.1 verursacht.

### Completion Notes

- T1 Branching-Fix umgesetzt: `parent_spec_id = target_spec_id` statt `current_row["spec_id"]`. Echter Git-Graph-Branch entsteht jetzt korrekt bei Rollback.
- Bonus-Fix: `ORDER BY created_at DESC, rowid DESC` als deterministischer Tiebreaker — verhindert flaky Tests bei schnellen DB-Inserts.
- T2 Phase-Ableitung: `_MODELING_STEPS`-Set + `_derive_phase()` in `specs.py`. Disabled Steps werden korrekt ignoriert.
- T4 `buildVersionTree()`: Pre-Order-DFS mit Depth-Tracking. 7 Tests alle grün.
- T5 SpecHistoryPanel: kein `.reverse()` mehr, Phase-Badge mit Template-Literal, Rollback-Icon via `startsWith('Rollback')`.
- TypeScript `--noEmit` ohne Fehler.

### File List

- `backend/src/gysi_ml/persistence/spec_repository.py` — Branch-Fix, rowid-Tiebreaker, spec_json in get_all_specs
- `backend/src/gysi_ml/api/schemas.py` — phase in VersionNodeResponse
- `backend/src/gysi_ml/api/routes/specs.py` — json-Import, _derive_phase(), phase in get_spec_tree()
- `backend/tests/integration/test_rollback.py` — AC2-Assertion korrigiert
- `backend/tests/integration/test_spec_tree.py` — 4 Phase-Tests hinzugefügt
- `frontend/src/types.ts` — phase in VersionNode
- `frontend/src/api/healthApi.ts` — phase in parseVersionNode()
- `frontend/src/App.css` — Grid 260px, Phase-Badge-Klassen
- `frontend/src/utils/buildVersionTree.ts` — NEU
- `frontend/src/utils/buildVersionTree.test.ts` — NEU
- `frontend/src/components/SpecHistoryPanel.tsx` — Baum-Darstellung

## Change Log

| Datum | Änderung |
|---|---|
| 2026-04-21 | Story erstellt |
