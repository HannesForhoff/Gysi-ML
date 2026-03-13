## **Preprocessing BelegArbeit** 



**Benötigte librarys :**

*primär bei pandas, sklearn (+ eine optionale Ausnahme mit caboost feature selection)*



#### **Erforderlich :**

**Feature Selection** (auf unterschiedliche Art und Weise)

&nbsp;	Interne Selektion als nächste Iteration

&nbsp;	User kann manuell auswählen

&nbsp;	Filter-Methods - z.B. auf Basis von Korrelationsmetriken

&nbsp;	Feature Selection Methoden 

&nbsp;		-> (Filters, Wrappers, Embedded Methods <- Seite 83 in 05\_Data Preperation)



**Ausreißerentfernung** bzw. Grenzen festlegen (-> Visualisierung Notwendig)

&nbsp;	-> Winsorization , Density-based neighborhoods, Boxplots (Zur Visualisierung der Outlier/Anomaly Detection)



**Samples selektieren** 

&nbsp;	-> Direktes Abrufen von Spezifischen Samples (paar Standard Abrufe : Selektiere alle Samples wo es geregnet 	hat)



**Missing Values** beheben

&nbsp;	-> Falls zu wenig Values = Selbst welche künstlich erzeugen

&nbsp;	-> Variable dropping , List-wise deletion, Mean imputation , Median imputation (Zusatz : Hot deck imputation)

&nbsp;	   Linear Interpolation, Last observation carried forward (LOCF), Next observation carried backward, NA 	   Imputation



**One-Hot-Encoding of categorical features vs. Zusammenfassen zu gruppierten Features**

	 

**Time Feature Encoding**

	**-> 1 Feature zu 3 Features (dd/mm/yyyy -> einzel features : day / month and year)**

**Duplikate**

	**-> Erkennen und Entfernen von Duplikaten (Features selbst / Einzel Einträge aber vor allem)**

**Data Splitting - Train-Test Ratios verändern**

	**-> Train-Test-Validation Split Verteilung (Vorsicht Data Leakage)**

(Rare-Category-Bucketing)

(Class Imbalance)

&nbsp;



#### **Optional :**

