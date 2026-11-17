# PACK RÉGLEMENTAIRE CONSOLIDÉ (VF) — LOGICIEL AVENEL (EXERCICE 2026)

*Référentiel comptable, fiscal et juridique consolidé (CGI 2026, Loi de Finances n° 50-25, Notes Circulaires DGI n° 727, 730, 732, 735 et 737, CGNC, BAM, CNDP).*

---

## 1. TVA & Retenues à la source

### 1.2. Taux de 10 % et taux transitoires en 2026
* **Règle validée à paramétrer dans AVENEL :**
  * **Taux normal par défaut** : **20 %** (CGI art. 98).
  * **Fin des paliers transitoires (convergence 2024–2026 achevée au 1er janvier 2026)** : L’énergie électrique, la location des compteurs d’eau et d’électricité, ainsi que les opérations de transport de voyageurs et de marchandises (hors ferroviaire déjà à 20 %) basculent définitivement à **20 %** au 1er janvier 2026. Désactiver le taux de **14 %** pour toute facture émise à compter du 01/01/2026 (ne le conserver qu’en historique pour les encaissements de créances nées sous le régime antérieur).
  * **Taux réduit de 10 % (CGI art. 99-2°)** : Applicable limitativement aux opérations suivantes :
    * Hôtellerie, restauration touristique, restauration sur place et location d’immeubles à usage touristique ;
    * Opérations de banque et de crédit et commissions de change (CGI art. 89-I-10°) ;
    * Transactions relatives aux valeurs mobilières effectuées par les sociétés de bourse ;
    * Prestations effectuées dans le cadre de leur profession par les avocats, interprètes, notaires, adoul, huissiers de justice et vétérinaires ;
    * Prestations de services rendues par tout agent démarcheur ou courtier d’assurances (stabilisé à 10 % depuis 2025) ;
    * Denrées et produits visés : huiles fluides alimentaires, sel de cuisine, riz usiné, pâtes alimentaires, gaz de pétrole et autres hydrocarbures gazeux, chauffe-eau solaires et panneaux photovoltaïques.
  * **Taux réduit de 7 % (CGI art. 99-1°)** : Maintenu uniquement pour les biens visés non abrogés (notamment sucre raffiné ou aggloméré, lait en poudre, savon de ménage, fournitures scolaires).
* **Sources officielles :** CGI 2026, Articles 95, 98 et 99 ; Loi de Finances n° 55-23 (2024) ; Note Circulaire DGI n° 735.

---

### 1.3. Échéances de déclaration TVA en 2026
* **Règle validée à paramétrer dans AVENEL :**
  * **Déclarants mensuels** (obligatoire si CA taxable N-1 $\ge 1\,000\,000\text{ MAD}$ ou absence d’établissement au Maroc — CGI art. 108) : Télédéclaration et télépaiement **avant l'expiration de chaque mois** au titre du chiffre d'affaires réalisé au cours du mois précédent (au plus tard le dernier jour du mois $M+1$).
  * **Déclarants trimestriels** : Télédéclaration et télépaiement **avant l'expiration du premier mois de chaque trimestre** au titre du trimestre écoulé (30 avril pour T1, 31 juillet pour T2, 31 octobre pour T3, 31 janvier $N+1$ pour T4).
  * **Formulation juridique exacte (CGI art. 110 & 111)** : *« Les contribuables imposés sous le régime de la déclaration mensuelle [trimestrielle] doivent déposer avant l'expiration de chaque mois [du premier mois de chaque trimestre] auprès de l'administration fiscale, une déclaration du chiffre d'affaires réalisé au cours du mois précédent [du trimestre écoulé] et verser, en même temps, la taxe correspondante. »*
  * **Report d'échéance** : Si la date limite coïncide avec un jour férié ou chômé, l’échéance est prorogée au premier jour ouvrable suivant (CGI art. 163).
* **Sources officielles :** CGI 2026, Articles 108, 110, 111, 115 et 163.

---

### 1.4. Plafond des paiements en espèces pour la déduction de la TVA (et de l'IS)
* **Règle validée à paramétrer dans AVENEL :**
  * **Confirmation du calcul sur le TTC** : Le plafond légal des paiements en espèces de **5 000 MAD par jour et par fournisseur**, dans la limite de **50 000 MAD par mois et par fournisseur**, s’apprécie strictement sur le montant **Toutes Taxes Comprises (TTC)**. Le paramétrage d'AVENEL sur le TTC est juridiquement exact.
  * **Double blocage fiscal à appliquer sur la fraction excédentaire** :
    1. **TVA (CGI art. 106-II)** : Rejet du droit à déduction de la TVA correspondant à la fraction payée en espèces au-delà de $5\,000\text{ MAD}$ TTC/jour ou $50\,000\text{ MAD}$ TTC/mois.
    2. **IS / IR (CGI art. 11-II)** : Non-déductibilité fiscale de la charge correspondante (réintégration extra-comptable).
  * **Exception doctrinale (NC DGI n° 727)** : Distinguer dans AVENEL le mode `Espèces Caisse` (soumis au plafond) du mode `Versement Bancaire en Espèces sur compte fournisseur` (non soumis au plafond sur présentation de l’avis de versement bancaire).
* **Sources officielles :** CGI 2026, Article 11-II et Article 106-II ; Notes Circulaires DGI n° 727 et n° 730.

---

### 1.5. Retenue à la source (RAS) sur la TVA (LF 2026 / CGI art. 117 & art. 247-XXXXVI)
* **Règle validée à paramétrer dans AVENEL :**
  * **Calendrier et seuils de chiffre d'affaires HT (CGI art. 247-XXXXVI & NC DGI n° 737)** :
    * **À compter du 1er juillet 2026** : État, collectivités territoriales, EEP, établissements de crédit/assurances et entreprises privées assujetties dont le **CA HT $\ge 500\,000\,000\text{ MAD}$** ;
    * **À compter du 1er janvier 2027** : Entreprises privées assujetties dont le **CA HT $\ge 350\,000\,000\text{ MAD}$** ;
    * **À compter du 1er janvier 2028** : Entreprises privées assujetties dont le **CA HT $\ge 200\,000\,000\text{ MAD}$**.
  * **Fait générateur** : Opérée au moment du **paiement / décaissement** (y compris sur les factures émises avant le 01/07/2026 et payées après) et versée au Trésor au cours du mois suivant (CGI art. 117-V).
  * **Matrice exacte des taux de RAS TVA (Art. 117-IV vs Art. 117-V)** :
    * **Prestations de services visées à l’art. 89-I (5°, 10° et 12°)** *(installation/pose/réparation/façon, opérations bancaires non exemptées, professions libérales : avocat, notaire, adel, huissier, interprète, architecte, métreur, géomètre, ingénieur, conseil et expert en toute matière, vétérinaire)* :
      * **RAS de 75 % de la TVA** : Lorsque le prestataire est une personne morale (payée par État/EEP) ou une personne physique produisant une **attestation de régularité fiscale de moins de 6 mois** *(pour les payeurs privés visés par les seuils CA, la présentation de l'attestation de régularité fiscale par le prestataire personne morale dispense de la retenue)*.
      * **RAS de 100 % de la TVA** : À défaut de présentation de l’attestation de régularité fiscale de moins de 6 mois (pour les personnes physiques et les cas visés à l'art. 117-V), ainsi que sur les prestations fournies par des non-résidents (art. 117-I).
    * **Biens d’équipement et travaux (Art. 117-IV)** : **0 %** si le fournisseur présente l'attestation de régularité fiscale ($< 6\text{ mois}$), et **100 %** de la TVA à défaut d’attestation.
    * **Exclusions légales** : Ventes d’eau et d’électricité, télécommunications (opérateurs agréés), assurances, et opérations $\le 5\,000\text{ MAD}$ TTC (dans la limite de $50\,000\text{ MAD}$ TTC/mois par fournisseur).
  * **Comptes CGNC dédiés (subdivision obligatoire)** :
    * **Chez le client (TVA retenue à reverser au Trésor)** : Crédit du compte **`44561` — État, TVA retenue à la source à reverser**.
    * **Chez le fournisseur (TVA retenue par le client, imputable)** : Débit du compte **`34561` (ou `34553`) — État, TVA retenue à la source par les clients**.
* **Sources officielles :** CGI 2026, Articles 89-I (5°, 10°, 12°), 117-I, 117-IV, 117-V et 247-XXXXVI ; Loi de Finances n° 50-25 (2026) ; Notes Circulaires DGI n° 735 et n° 737 (du 27/02/2026) ; CGNC.

---

### 1.6. Retenue à la source IS de 5 % (et IR) sur les prestations de services et loyers
* **Règle validée à paramétrer dans AVENEL :**
  * **Assiette de calcul** : Strictement le montant **Hors Taxes (HT)**.
  * **Règles d’application selon la nature de l’opération et la qualité du tiers** :
    1. **Prestations de services visées à l’art. 89-I (5°, 10°, 12°)** :
       * Fournisseur **Personne Morale (IS)** payé par État/EEP : **RAS IS de 5 % HT** (CGI art. 15 bis et 19-IV).
       * Fournisseur **Personne Morale (IS)** payé par une **Personne Morale Privée** : **RAS IS de 5 % HT** *uniquement à défaut d’attestation de régularité fiscale de moins de 6 mois* (**0 %** si attestation fournie — CGI art. 157-I).
       * Fournisseur **Personne Physique (IR — régime RNR/RNS)** : **RAS IR de 10 % HT** (CGI art. 45 bis et 73-II-B).
    2. **Loyers (Locations d’immeubles)** :
       * Bailleur **Personne Morale (IS) — Loyers à usage professionnel (LF 2026)** : **RAS IS de 5 % HT** instituée par l’**article 15 ter du CGI** (soumise au même calendrier progressif par tranches de CA : $500\text{ MDH}$ au 01/07/2026, $350\text{ MDH}$ au 01/01/2027, $200\text{ MDH}$ au 01/01/2028, sous réserve des dispenses légales).
       * Bailleur **Personne Physique (Revenus fonciers)** : **RAS IR de 10 %** (loyers annuels $< 120\,000\text{ MAD}$, sous réserve du seuil d'exonération de $30\,000\text{ MAD}$) ou **15 %** (loyers annuels $\ge 120\,000\text{ MAD}$), sauf présentation d’une attestation d’option au paiement spontané délivrée par la DGI (CGI art. 73-II et 160 bis).
  * **Comptes CGNC** : Débit `3453` (Acomptes sur impôts sur les résultats) chez le fournisseur / Crédit `4457` (État, impôts et taxes à payer) chez le client.
* **Sources officielles :** CGI 2026, Articles 15 bis, 15 ter, 19-IV, 45 bis, 73-II, 157-I, 160 bis et 247-XXXXVI ; Notes Circulaires DGI n° 732, 733, 735 et 737.

---

### 1.7. SIMPL-TVA : schéma XSD du relevé des déductions et codes modes de paiement
* **Règle validée à paramétrer dans AVENEL :**
  * **Schéma XSD officiel DGI** : Structure XML standardisée `<DeclarationReleveDeduction>` publiée sur le portail `simpl-tva.tax.gov.ma` intégrant les balises obligatoires par ligne de facture : `<ord>`, `<num>`, `<des>`, `<mht>`, `<tva>`, `<ttc>`, `<refF>` (`<if>`, `<nom>`, `<ice>`), `<tx>`, `<prorata>`, `<mp>`, `<dpai>`, `<dfac>`.
  * **Table officielle des codes des modes de paiement (`<mp>`)** :
    * **`1`** : Espèces
    * **`2`** : Chèque
    * **`3`** : Prélèvement
    * **`4`** : Virement
    * **`5`** : Effet
    * **`6`** : Compensation
    * **`7`** : Autres
  * **Contrôles bloquants avant export XML** : Numérotation `<ord>` séquentielle sans rupture, dates au format ISO `AAAA-MM-JJ`, échappement des caractères spéciaux XML dans `<num>`, présence obligatoire de `<if>` et `<ice>` (15 chiffres) pour tout fournisseur local, et cohérence mathématique $\text{mht} + \text{tva} = \text{ttc}$.
* **Sources officielles :** CGI 2026, Article 112-II ; Cahier des charges EDI / Spécifications techniques XML SIMPL-TVA (DGI).

---

## 2. Comptes par défaut (CGNC)

### 2.1. Compte d’attente pour les lignes bancaires non rapprochées
* **Règle validée à paramétrer dans AVENEL :**
  * **Rejet formel de `3911`** (compte de provision pour dépréciation des matières premières).
  * **Comptes CGNC à paramétrer** : **`34971` (Comptes transitoires ou d’attente - débiteurs — Suspens bancaires)** et **`44971` (Comptes transitoires ou d’attente - créditeurs — Suspens bancaires)** — rattachés aux rubriques normalisées `3497` / `4497` du CGNC (ou `4711`/`4712` uniquement s’ils sont mappés sur les rubriques 349/449 de la liasse).
  * **Contrôle de clôture** : Alerte bloquante à la clôture de l’exercice (31/12) si `34971` ou `44971` présente un solde non nul.
* **Sources officielles :** CGNC, Volume II — Plan des comptes (Rubriques 349 et 449) ; Loi n° 9-88, Articles 9 et 10.

---

### 2.2. Écarts d’arrondi de change
* **Règle validée à paramétrer dans AVENEL :**
  * **Arbitrage en faveur des comptes financiers** : Imputer systématiquement tout écart de conversion ou d’arrondi sur devises (y compris les micro-écarts de centimes) en **`6331` (Pertes de change propres à l’exercice)** ou **`7331` (Gains de change propres à l’exercice)**. Ne jamais utiliser `6588` / `7588` (non courant) pour des opérations en devises.
* **Sources officielles :** CGNC, Volume II (Rubriques 633 et 733) ; Loi n° 9-88, Article 14.

---

### 2.3. Frais bancaires et TVA récupérable
* **Règle validée à paramétrer dans AVENEL :**
  * **Confirmation totale** : Commissions et frais bancaires au débit de **`6147` (Services bancaires)** pour le montant HT ; TVA récupérable au débit de **`34552` (État - TVA récupérable sur charges)** au taux réduit de **10 %** (CGI art. 99-2°).
  * **Distinction agios / intérêts** : Les intérêts débiteurs sur découverts ou financements sont imputés au débit de **`6311` (Intérêts des emprunts et dettes)**, avec TVA à **10 %** également en **`34552`**.
* **Sources officielles :** CGNC, Plan des comptes (`6147`, `6311`, `34552`) ; CGI 2026, Article 99-2°.

---

### 2.4. Sous-comptes CGNC propres à l’activité de chaque client pilote
* **Règle validée à paramétrer dans AVENEL :**
  * **Règle de codification hiérarchique** : Verrouiller obligatoirement les **4 premiers chiffres** (racine du compte principal CGNC) — et les **5 premiers chiffres** pour les comptes divisionnaires normalisés par le CGNC (`34551`, `34552`, `6111`, `6112`, etc.) — afin de garantir l’intégrité automatique de la table de passage de la liasse fiscale. Autoriser la libre création de sous-comptes analytiques/sectoriels par client pilote à partir du **6e chiffre** (ex. `711101`, `711102`).
* **Sources officielles :** CGNC, Volume I, Chapitre IV ; Loi n° 9-88, Article 3.

---

## 3. Lettrage

### 3.1. Tolérance d’écart acceptée en MAD et compte d’imputation
* **Règle validée à paramétrer dans AVENEL :**
  * **Seuil de tolérance** : Paramétrer une tolérance par défaut de **$1,00\text{ MAD}$ maximum par règlement** (avec plafond dur bloquant à **$5,00\text{ MAD}$** au-delà duquel une note d’avoir ou une pièce justificative est exigée).
  * **Comptes d’imputation des micro-écarts d’arrondi ($\le 1,00\text{ MAD}$)** : Utiliser les comptes d’exploitation courante **`6188` (Autres charges d’exploitation)** en cas d’écart défavorable et **`7188` (Autres produits d’exploitation)** en cas d’écart favorable (de préférence à `6588`/`7588` réservés au non courant).
  * **Alerte fiscale** : Tout écart significatif non justifié par un avoir régulier (CGI art. 145) constitue un abandon de créance non déductible fiscalement (CGI art. 10).
* **Sources officielles :** Loi n° 9-88, Articles 1 et 11 ; CGNC (`6188`, `7188`) ; CGI 2026, Articles 10 et 145.

---

### 3.2. Différences de change au règlement
* **Règle validée à paramétrer dans AVENEL :**
  * **Au règlement en cours d’exercice** : Constater la différence définitive entre le cours historique de facturation et le cours effectif de règlement en **`6331` (Pertes de change propres à l’exercice)** ou **`7331` (Gains de change propres à l’exercice)**.
  * **Cycle clôture / ouverture sur factures non réglées au 31/12** :
    1. *Clôture (31/12/$N$)* : Réévaluation au cours BAM de clôture via les comptes d’écarts de conversion actif **`3701` / `3702`** (avec dotation obligatoire d’une provision pour perte de change : Débit `6393` / Crédit `4506` ou `1516`) ou passif **`4701` / `4702`** (avec réintégration fiscale extra-comptable du gain latent).
    2. *Ouverture (01/01/$N+1$)* : Contrepassation automatique des comptes `370` / `470` pour ramener la créance/dette à sa valeur historique avant le règlement.
* **Sources officielles :** Loi n° 9-88, Article 14 ; CGNC, Volume I (Titre IV) et Volume II (`6331`, `7331`, `370`, `470`, `4506`, `1516`, `6393`, `7393`).

---

## 4. Factures

### 4.1. Auto-entrepreneurs et interdiction de facturer la TVA
* **Règle validée à paramétrer dans AVENEL :**
  * **Base légale exacte tranchée** : **CGI Article 89-II** (et non l’article 91). L’auto-entrepreneur soumis au régime de l’article 42 bis est placé **hors champ d’application de la TVA**.
  * **Règles bloquantes dans AVENEL** :
    1. Interdiction absolue de facturer ou de déduire de la TVA sur une facture d’auto-entrepreneur (taux forcé à `HORS_CHAMP — 0 %`, exclusion automatique du relevé des déductions SIMPL-TVA).
    2. Mention obligatoire sur les factures émises : *« TVA non applicable — Régime de l’auto-entrepreneur (CGI art. 89-II) »* + numéro RNAE + ICE.
    3. **Compteur d'alerte RAS 30 %** : Suivi cumulatif annuel par fournisseur auto-entrepreneur ; au-delà de **$80\,000\text{ MAD}$ de chiffre d’affaires annuel** réalisé avec un même client, application de la retenue à la source libératoire de **30 %** sur le surplus (CGI art. 42 ter et 73-II-G).
* **Sources officielles :** CGI 2026, Articles 42 bis, 42 ter, 73-II-G, 89-II et 145-III ; Loi n° 114-13.

---

### 4.2. Algorithme de la clé de contrôle de l’ICE
* **Règle validée à paramétrer dans AVENEL :**
  * **Statut officiel** : L’algorithme de calcul de la clé de contrôle de l’ICE ($15\text{ chiffres} = 9\text{ chiffres racine entreprise} + 4\text{ chiffres établissement} + 2\text{ chiffres clé}$) ne fait pas l’objet d’une spécification publiée au Bulletin Officiel par l’OMPIC / DGI.
  * **Règle d’ingénierie confirmée** :
    1. **Validation bloquante** sur le format exact à **15 chiffres numériques** (`^[0-9]{15}$`) et rejet des suites uniformes (`000...`, `111...`).
    2. **Maintien de l’avertissement non bloquant (Warning)** sur la vérification mathématique **Modulo 97** :
       $$\text{Clé} = 97 - \left(\text{Nombre}_{13\text{ chiffres}} \bmod 97\right)$$
       doublé d’une vérification en ligne via l’annuaire/téléservice DGI/OMPIC lorsque disponible (afin d’éviter tout faux positif bloquant sur d’anciens ICE historiques).
* **Sources officielles :** Décret n° 2-11-63 du 20 mai 2011 instituant l’ICE ; CGI 2026, Article 145-I.

---

### 4.3. Codes banques Bank Al-Maghrib (RIB Maroc)
* **Règle validée à paramétrer dans AVENEL :**
  * **Table officielle BAM vérifiée** :
    * **`007`** : Attijariwafa bank
    * **`011`** : Bank Of Africa *(ex-BMCE Bank)*
    * **`013`** : **BMCI** *(Banque Marocaine pour le Commerce et l’Industrie)*
    * **`021`** : Crédit du Maroc
    * **`022`** : Saham Bank *(ex-Société Générale Marocaine de Banques - SGMB)*
    * **`050`** : Al Barid Bank
    * **`101`** : Banque Centrale Populaire (BCP) *(+ codes régionaux BPR série `1xx`)*
    * **`230`** : CIH Bank
    * **`310`** : Trésorerie Générale du Royaume (TGR)
  * **Résolution du conflit sur le code `013`** : Le code **`013`** est attribué exclusivement et invariablement à la **BMCI**. Les confusions observées dans d’anciens référentiels proviennent d’erreurs de saisie avec le code **`011`** (Bank Of Africa / ex-BMCE) ou d’établissements absorbés historiquement.
* **Sources officielles :** Circulaire Bank Al-Maghrib relative au RIB à 24 chiffres ; Référentiel interbancaire SIMT (BAM).

---

## 5. Questions juridiques, conformité et déontologie

### 5.1. Durée de conservation des pièces comptables originales
* **Règle validée à paramétrer dans AVENEL :**
  * **Durée légale minimale** : **10 ans** à compter de la clôture de l’exercice (obligation comptable, commerciale et fiscale).
  * **Prorogation automatique en cas de déficit** : Bloquer la purge des pièces justificatives des exercices déficitaires tant que les déficits reportables ou amortissements différés n’ont pas été intégralement imputés et prescrits (CGI art. 232-VIII).
  * **Original papier obligatoire** : En l’absence d’archivage électronique qualifié conforme à la **Loi n° 43-20** (signature électronique qualifiée et horodatage agréé par la DGSSI), l’entreprise doit conserver les **originaux papier pendant 10 ans** pour leur opposabilité fiscale (CGI art. 210 et 212).
* **Sources officielles :** Loi n° 9-88, Article 22 ; Code de Commerce, Article 26 ; CGI 2026, Articles 210, 211, 212 et 232-VIII ; Loi n° 53-05 et Loi n° 43-20.

---

### 5.2. CNDP (Loi 09-08) et transfert de données vers une IA hébergée à l’étranger
* **Règle validée à paramétrer dans AVENEL :**
  * **Qualification légale** : Les pièces comptables et de paie contenant des données à caractère personnel (salariés, fournisseurs personnes physiques, gérants), leur envoi vers une API d’IA hébergée hors du Maroc constitue un **transfert international de données** soumis à **demande d’autorisation préalable auprès de la CNDP** (articles 43 et 44 de la Loi 09-08), même vers un pays reconnu adéquat (UE).
  * **Mesure technique de conformité (PII Redaction)** : Activer un module local de pseudonymisation/masquage des identifiants personnels (noms, CIN, CNSS, RIB) avant tout appel à une API IA externe, combiné à une clause contractuelle **Zero Data Retention / No-Training**.
  * **Clauses obligatoires du contrat de sous-traitance (Loi 09-08, Art. 23)** : Traitement uniquement sur instruction écrite du responsable de traitement (la fiduciaire), interdiction d’utilisation des données pour l’entraînement des modèles d’IA, chiffrement en transit et au repos, confidentialité stricte et destruction certifiée en fin de contrat.
* **Sources officielles :** Loi n° 09-08 (Dahir n° 1-09-15 du 18 février 2009), Articles 1, 23, 43 et 44 ; Délibérations de la CNDP relatives aux transferts internationaux.

---

### 5.3. Loi 05-20 relative à la cybersécurité
* **Règle validée à paramétrer dans AVENEL :**
  * **Applicabilité** : Une fiduciaire privée n’est pas qualifiée par défaut d’Infrastructure d’Importance Vitale (IIV) et n’est donc pas soumise à une obligation légale de localisation des serveurs au Maroc par la Loi 05-20 (sauf si elle héberge des données d’entités publiques soumises aux directives Cloud Souverain de la DGSSI).
  * **Obligations de l’éditeur (PSN)** : En tant que Prestataire de Services Numériques (PSN), AVENEL doit appliquer les mesures de sécurité des systèmes d’information et notifier sans délai à la **DGSSI** tout incident de sécurité majeur affectant la disponibilité ou l’intégrité du service.
* **Sources officielles :** Loi n° 05-20 relative à la cybersécurité (Dahir n° 1-20-69 du 25 juillet 2020), Articles 2, 3 et 18 à 25 ; Décret n° 2-21-406 du 4 août 2021.

---

### 5.4. Position de l’OEC sur les outils assistés par IA et le secret professionnel
* **Règle validée à paramétrer dans AVENEL :**
  * **Secret professionnel absolu** : L’expert-comptable est soumis au secret professionnel pénalement sanctionné (Code pénal art. 446 ; Loi 15-89 art. 36). Aucune donnée client identifiable ne doit être exposée à un tiers non couvert par une étanchéité contractuelle et technique totale.
  * **Principe de supervision humaine obligatoire (*Human-in-the-Loop*)** : L’IA est cantonnée à un rôle d’assistance (pré-imputation en brouillard). **Toute écriture générée par l’IA doit faire l’objet d’une validation humaine explicite** avant imputation définitive, avec journalisation complète (piste d’audit distinguant le statut *Proposé par IA* du statut *Validé par Utilisateur*). L’expert-comptable signataire conserve l’entière responsabilité civile, disciplinaire et pénale des états de synthèse.
* **Sources officielles :** Loi n° 15-89 réglementant la profession d’expert-comptable, Articles 30 et 36 ; Code des Devoirs Professionnels de l’OEC ; Code Pénal Marocain, Article 446.

---

### 5.5. Facture électronique au Maroc (CGI art. 145)
* **Règle validée à paramétrer dans AVENEL :**
  * **Statut réglementaire en 2026** : L’**article 145-IX du CGI** institue le cadre légal de la facturation électronique et de la transmission des données à l’administration fiscale, mais **le décret d’application fixant la date d’entrée en vigueur obligatoire et le calendrier par tranches n’est pas encore publié au Bulletin Officiel**. Maintenir AVENEL en mode *« Prêt / Anticipation »* sans bloquer la facturation classique.
  * **Formats techniques & identifiants douaniers** :
    * Structurer le modèle de données factures selon la norme **UBL 2.1 (XML)** et le format hybride **Factur-X (PDF/A-3)**.
    * Pour les importations, intégrer obligatoirement la référence structurée de la **Déclaration Unique des Marchandises (DUM — système BADR de l’ADII)** à **17 caractères** (`Bureau [3] + Régime [3] + Année [4] + N° séquentiel [7]`) ainsi que la **date et le numéro de la quittance douanière** (fait générateur de la déduction de la TVA à l’importation — CGI art. 101-1°).
* **Sources officielles :** CGI 2026, Articles 101-1°, 112-II et 145-IX ; Code des Douanes et Impôts Indirects (CDII) et référentiel BADR (ADII).

---

> **MENTION DE VALIDATION RÉGLEMENTAIRE (AVENEL — PACK VF 2026)**
> *Conformément aux exigences d'auditabilité d'AVENEL, l'activation de ces règles dans le moteur comptable et fiscal est subordonnée à la validation formelle d'un professionnel habilité :*
> - **Nom et Prénom du signataire :** _______________________________________
> - **Qualité (Expert-Comptable DPLE / Commissaire aux Comptes) :** ___________
> - **Numéro d'inscription au tableau de l'OEC :** ___________________________
> - **Date et signature / Cachet :** ________________________________________