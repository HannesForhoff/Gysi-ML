Systemkonzept und Rollenverteilung zwischen LLM und Backend
Das Projekt Gysi wird als konversationelles Assistenzsystem konzipiert, das Nutzerinnen und Nutzern die Erstellung und Anpassung von Machine Learning Pipelines über natürliche Sprache ermöglicht. Der zentrale Entwurfsgedanke ist eine strikte Trennung zwischen Planung und Ausführung. Das Large Language Model übernimmt die Rolle eines Orchestrators und Erklärers, während sämtliche datenverarbeitenden und später auch modellbezogenen Berechnungen ausschließlich in einem Python Backend stattfinden. Das System ist damit bewusst so gestaltet, dass das LLM keine Berechnungen ausführt, keinen Zugriff auf die Laufzeitumgebung besitzt und keine Änderungen am Framework oder am Code vornehmen kann. Ziel ist ein reproduzierbarer, stabiler Prototyp, dessen Verhalten durch klare Schnittstellen, validierbare Aktionen und versionierte Zustände kontrollierbar bleibt.
Interaktionsform und optionale Sprachkomponente
Die primäre Interaktionsform ist ein textbasierter Chat. Nutzer formulieren Anforderungen, Änderungswünsche oder Rückfragen in natürlicher Sprache. Eine Integration von Speech to Text und Text to Speech wird als optionale Erweiterung betrachtet, ist jedoch nicht Kernbestandteil des Projekts, da sie den Implementierungsaufwand deutlich erhöht. Diese Erweiterung wird daher entweder nur prototypisch oder als Randnotiz und Ausblick beschrieben. Der fachliche Kern und die Evaluation fokussieren auf die textbasierte Interaktion und die Zuverlässigkeit der Pipeline Orchestrierung.
Rolle des Menschen
Der Mensch ist Initiator, Zielgeber und letztinstanzlicher Entscheider. Er liefert den Datensatz, definiert das Ziel der Analyse, bewertet Zwischenergebnisse und entscheidet über Änderungen an der Pipeline. Gysi ist nicht als autonomes AutoML System gedacht, sondern als Assistenz, die Vorschläge macht, Konsequenzen erklärt und Änderungen umsetzt, wenn der Nutzer sie beauftragt. Ein wichtiger Bestandteil ist die Möglichkeit, zu früheren Pipeline Zuständen zurückzukehren, um exploratives Arbeiten kontrolliert zu unterstützen.
Rolle des LLM
Das LLM übernimmt drei Aufgabenbereiche.
Erstens die Übersetzung von Nutzerintentionen in strukturierte Aktionen. Aus einer freien Spracheingabe wird eine formal definierte Aktion abgeleitet, etwa das Hinzufügen eines Preprocessing Schritts, das Ändern eines Parameters, das Starten einer Ausführung oder das Zurücksetzen auf einen früheren Zustand. Die Ausgabe des LLM erfolgt als JSON Struktur, wodurch das Backend die Aktion zuverlässig parsen und validieren kann.
Zweitens die Unterstützung bei Entscheidungen durch erklärende Empfehlungen. Das LLM darf kontextbezogene Vorschläge formulieren, beispielsweise welche Missing Value Strategie plausibel ist oder warum Rare Category Bucketing bei hoher Kardinalität sinnvoll sein kann. Diese Empfehlungen sind jedoch stets unverbindlich. Ausgeführt wird nur, was als strukturierte Aktion vom Backend akzeptiert und angewandt wird.
Drittens die verständliche Interpretation von Ergebnissen. Das Backend liefert verdichtete Reports, Kennzahlen und Artefakt Referenzen. Das LLM nutzt diese Informationen, um Ergebnisse zu erklären, Unterschiede zwischen Pipeline Varianten zu erläutern und Nutzerfragen zu beantworten. Damit wirkt das LLM als erklärende Schicht zwischen technischen Ausgaben und menschlicher Interpretation.
Berechtigungen und Grenzen des LLM
Die Berechtigungen des LLM sind bewusst eingeschränkt, um Stabilität und Reproduzierbarkeit sicherzustellen.
Das LLM darf keine ausführbaren Codefragmente erzeugen, die direkt in der Laufzeitumgebung ausgeführt werden.
Das LLM darf keine Bibliotheken installieren, keine Dateisystem Operationen anstoßen und keine Umgebungsvariablen verändern.
Das LLM darf keine neuen Pipeline Bausteine erfinden, die im Backend nicht als Modul implementiert sind.
Das LLM darf ausschließlich Aktionen aus einem vordefinierten Katalog verwenden, der die verfügbaren Schritte und Parameterbereiche beschreibt.
Das LLM darf Empfehlungen und Erklärungen in natürlicher Sprache liefern, diese sind jedoch nie automatisch bindend.
Damit ist Gysi ein System, in dem das LLM die Interaktion und Orchestrierung übernimmt, während die Ausführung vollständig kontrolliert bleibt. Die Möglichkeit, dass das LLM halluziniert oder unpassende Vorschläge macht, wird durch Validierung und Guardrails auf Backend Seite abgefedert.
Rolle des Backends
Das Backend ist die einzige ausführende Instanz. Es wird als modularer Python Dienst realisiert, der logisch wie ein Service über eine API angesprochen wird, aber nicht zwingend deployt werden muss. Praktisch kann er lokal als FastAPI Anwendung laufen und eine klare Schnittstelle bereitstellen, etwa für Nutzeranfragen, Pipeline Änderungen und Ausführungsjobs. Diese Wahl erleichtert die saubere Trennung von Komponenten, die spätere Erweiterbarkeit und die Darstellung im Architekturdiagramm.
Das Backend übernimmt insbesondere die folgenden Aufgaben.
Es verwaltet den Projektzustand, inklusive Datensatzpfaden, Metadaten, Pipeline Spezifikation, Versionen und Artefakten.
Es stellt einen Executor bereit, der Pipeline Schritte deterministisch entsprechend einer Spezifikation ausführt.
Es validiert jede vom LLM vorgeschlagene Aktion strikt, bevor sie angewandt wird.
Es generiert Reports, Kennzahlen und Visualisierungen und legt sie als Artefakte ab.
Es verdichtet Ergebnisse zu kompakten Kontextobjekten, die dem LLM zur Erklärung übergeben werden.
Pipeline Spezifikation als zentrale Schnittstelle
Kern der Architektur ist eine Pipeline Spezifikation als maschinenlesbare Beschreibung des aktuellen Workflows. Diese Spec bildet sämtliche konfigurierbaren Aspekte ab, ohne dass Codeänderungen nötig sind. Für die frühe Projektphase umfasst die Spec primär Vorverarbeitungsschritte auf Basis von pandas und scikit learn, später zusätzlich Modellierung mit Decision Trees und EBM sowie Explainability Ausgaben. 
Beispiele für Inhalte sind: 
-	Datensatz und Zielvariable
-	Liste der aktivierten Preprocessing Schritte mit Parametern und Reihenfolge
-	Encoding Strategien für kategorische Features
-	Time Feature Encoding Konfiguration
-	Feature Selection Methoden, inklusive Filter Methoden und optionaler CatBoost Ausnahme
-	Outlier Regeln und Grenzwerte
-	Splitting Konfiguration wie Train Test Ratio und Stratifikation
Wichtig ist, dass die Spec nicht nur als Konfiguration dient, sondern als Quelle der Wahrheit für den gesamten Systemzustand. Das LLM erhält diese Spec als Kontext, verändert sie über definierte Aktionen und das Backend führt exakt diese Spezifikation aus. Das Backend selbst bleibt stabil und unverändert; die Variation entsteht durch die Spec.









Action Schema und Ausführungsschleife
Die Kopplung zwischen Nutzer, LLM und Backend erfolgt über einen wiederholbaren Interaktionszyklus.
0.	Der Nutzer sendet eine Anfrage im Chat.
1.	Das Backend erstellt daraus einen Kontext, der die aktuelle Spec, letzte Ergebnisse und relevante Reports in komprimierter Form enthält.
2.	Das LLM erzeugt eine JSON-Aktion, die entweder eine Spec Änderung beschreibt, eine Ausführung anfordert oder einen History Befehl enthält.
3.	Das Backend validiert die Aktion gegen ein Schema und gegen semantische Regeln und wendet sie nur bei Gültigkeit an.
4.	Das Backend führt die betroffenen Schritte aus und erzeugt Artefakte und Kennzahlen.
5.	Das Backend sendet eine Ergebniszusammenfassung zurück an das LLM.
6.	Das LLM formuliert daraus eine Erklärung und mögliche nächste Schritte für den Nutzer.
Diese Schleife ist so gestaltet, dass das LLM nie direkt mit Rohdaten arbeiten muss und dass alle numerischen Ergebnisse aus realer Ausführung stammen, nicht aus generativer Schätzung.
Persistenz, Artefakte und hybride Versionierung
Für Nachvollziehbarkeit und die geforderte History Funktion wird ein hybrides Persistenzkonzept verwendet. Die Pipeline Spezifikationen und deren Versionen werden in einer leichtgewichtigen SQLite Datenbank verwaltet, während Artefakte wie Plots, Tabellenexports und Reports im Dateisystem abgelegt werden. Der Vorteil ist, dass Versionsverläufe strukturiert und robust gespeichert werden können, während Artefakte weiterhin einfach zugänglich bleiben und direkt in die Belegarbeit übernommen werden können.
Jede Änderung an der Pipeline Spec erzeugt eine neue Version mit eindeutiger ID. Zusätzlich werden Execution Runs mit dieser Version verknüpft, sodass nachvollziehbar ist, welche Ergebnisse zu welchem Pipeline Zustand gehören. Artefakte werden im Dateisystem in einer klaren Ordnerstruktur gespeichert und über Pfade oder IDs in der Datenbank referenziert.





History, Undo und optionale Branches
Gysi soll es erlauben, frühere Zustände wiederherzustellen, etwa über Befehle wie „gehe zwei Schritte zurück“. Dazu wird ein Versionierungsmodell verwendet, bei dem jede Spec Änderung eine neue Revision erzeugt und der Nutzer zwischen Revisionen wechseln kann. Ein Undo Befehl setzt den aktiven Zustand auf eine frühere Spec Version zurück. Da Artefakte an Spec Versionen und Runs gekoppelt sind, kann das System konsistent auf frühere Ergebnisse referenzieren oder bei Bedarf deterministisch neu ausführen.
Zusätzlich wird eine git ähnliche Branch Funktionalität als wünschenswerte Erweiterung betrachtet. Ein Branch erlaubt es, mehrere Pipeline Varianten parallel zu entwickeln, etwa eine Variante mit One Hot Encoding und eine Variante mit gruppierten Kategorien. Technisch entspricht dies in der SQLite Struktur einer zusätzlichen Branch Zuordnung pro Spec Version sowie einem Zeiger auf den aktuellen Head pro Branch. Falls die Implementierung im Rahmen der Belegarbeit zu aufwendig wird, bleibt das System bei einer linearen Historie, die jedoch weiterhin Undo und explizites Speichern von Zuständen ermöglicht. In der Architektur wird Branching daher als optionaler Bestandteil beschrieben, der ohne Änderung am Grundkonzept ergänzt werden kann.
Codeaufbau für LLM kompatible Interaktion ohne Codegenerierung
Damit das LLM effektiv interagieren kann, ohne selbst Code zu schreiben, wird das Backend als Sammlung klar definierter Module umgesetzt.
Es existiert eine Registry der verfügbaren Pipeline Schritte, in der jeder Schritt einen eindeutigen Typnamen und ein Parameterschema besitzt.
Alle Schritte implementieren ein einheitliches Interface, sodass der Executor sie sequentiell ausführen kann.
Die Pipeline Spec wird durch ein formales Schema validiert, bevor sie ausgeführt wird.
Das Backend erzeugt standardisierte Reports und Resultatobjekte, die als Kontext für das LLM dienen.
Dieses Design stellt sicher, dass Erweiterungen des Funktionsumfangs nicht durch das LLM, sondern durch das Hinzufügen neuer, getesteter Module im Backend erfolgen. Das LLM bleibt damit eine steuernde und erklärende Komponente, deren Eingriffsraum auf konfigurierbare Variation innerhalb eines stabilen Frameworks beschränkt ist.

