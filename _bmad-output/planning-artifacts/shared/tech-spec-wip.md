---
title: 'Rollback-Nachricht: Quell- und Zielversion anzeigen'
slug: 'rollback-nachricht-quell-zielversion'
created: '2026-05-09'
status: 'in-progress'
stepsCompleted: [1]
tech_stack: ['TypeScript', 'React']
files_to_modify: ['frontend/src/App.tsx']
code_patterns: ['handleRollback callback', 'state.specHistory.versions lookup']
test_patterns: []
---

# Tech-Spec: Rollback-Nachricht: Quell- und Zielversion anzeigen

**Created:** 2026-05-09

## Overview

### Problem Statement

Die Rollback-Bestätigungsnachricht zeigt dem Nutzer nur die neu erstellte Version (z.B. `v5`), nicht die Version auf die zurückgekehrt wurde (z.B. `v1`). Das ist irreführend: Der Nutzer sieht nicht, welchen Stand die Pipeline jetzt hat.

Aktuell: `"Rollback zu v5 abgeschlossen. Die Pipeline wurde auf diesen Stand zurückgesetzt."`

Erwartet: `"Rollback zu v1 (neu: v5) abgeschlossen. Die Pipeline wurde auf den Stand von v1 zurückgesetzt und läuft auf v5 weiter."`

### Solution

In `handleRollback` (`App.tsx`) wird vor dem API-Call die `version` des Ziel-Nodes (`targetSpecId`) aus `state.specHistory` aufgelöst. Nach erfolgreichem Rollback werden beide Versionsnummern (Quelle + Neu) in der Bestätigungsnachricht angezeigt.

### Scope

**In Scope:**
- Änderung der Rollback-Bestätigungsnachricht in `frontend/src/App.tsx`
- Prüfen und ggf. Anpassen bestehender Tests (`chatReducer.rollback.test.ts`)

**Out of Scope:**
- Backend-Logik oder API-Rückgabewert (`new_version`)
- Neue Testfälle schreiben

## Context for Development

### Codebase Patterns

- `handleRollback` ist ein `useCallback` in `App.tsx`
- `state.specHistory` ist vom Typ `VersionTree` mit `versions: VersionNode[]`
- `VersionNode` hat das Feld `version: string` und `spec_id: string`
- Nach dem API-Call wird `treeForLookup` gebaut – die Quellversion muss **vor dem Call** aus dem alten State aufgelöst werden, da der Tree danach neu geladen wird

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `frontend/src/App.tsx` | Enthält `handleRollback` – hier ist der Fix |
| `frontend/src/types.ts` | `VersionNode`, `VersionTree` Typen |
| `frontend/src/api/healthApi.ts` | `performRollback` gibt `{ ok: true, newVersion: string }` zurück |
| `frontend/src/state/chatReducer.rollback.test.ts` | Bestehende Tests für Rollback-Nachrichten |

### Technical Decisions

- Quellversion wird **vor** `performRollback` aus `state.specHistory` aufgelöst (nicht nach dem Reload)
- Fallback: Wenn Version nicht gefunden → `targetSpecId` als Rohtext oder `'unbekannt'`

## Implementation Plan

### Tasks

*(wird in Step 3 ausgefüllt)*

### Acceptance Criteria

*(wird in Step 3 ausgefüllt)*
