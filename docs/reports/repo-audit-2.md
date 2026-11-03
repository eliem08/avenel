# AVENEL — Rapport d'Audit N°2 : Réalité du Frontend, Données et Tests

**Date :** 3 novembre 2026  
**Auteur :** Lead Architecte Antigravity  
**Statut :** Audit Seul — Strictement Aucune Modification de Code  
**Référence :** Directive d'Audit Approfondi Frontend / Tests  

---

## 1. Source de Données des Écrans AVENEL sur `/pilot`

L'examen minutieux des composants montés sur la route `/pilot` démontre qu'**aucun écran n'interroge les endpoints de l'API FastAPI**. Tous les écrans fonctionnent à 100% sur des fixtures et données mockées locales.

| Écran AVENEL | Mode de Données | Fichier Source des Données | Endpoint FastAPI Correspondant (Non Appelé) |
| :--- | :---: | :--- | :--- |
| **Queue** | Mock / Fixture | [`src/pages/PilotDemoPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/PilotDemoPage.tsx#L13-L56)<br>`const mockQueueItems: QueueRowItem[]` | `GET /v1/work-requests` |
| **ProposalReview** | Mock / Fixture | [`src/pages/PilotDemoPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/PilotDemoPage.tsx#L59-L124)<br>`const mockProposals: Proposal[]` | `GET /v1/work-requests/{id}/proposals` |
| **DocumentViewer** | Mock / Fixture | [`src/pages/PilotDemoPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/PilotDemoPage.tsx#L463-L506) (Étape 5 du stepper)<br>+ [`src/pages/DocumentReviewPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/DocumentReviewPage.tsx#L9-L84) sur `/viewer` | `GET /v1/documents/{id}/extractions` |
| **Reconciliation** | Mock / Fixture | [`src/pages/PilotDemoPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/PilotDemoPage.tsx#L127-L187)<br>`mockBankTransactions`, `mockProposalSummaries`, `mockMatches`<br>*(Callbacks `onAcceptMatch` et `onRejectMatch` sont des fonctions vides `async () => {}`)* | `GET /v1/bank-statements/{id}/transactions`<br>`GET /v1/reconciliation/matches`<br>`POST /v1/reconciliation/matches/{id}:accept` |
| **Approval** | Mock / Fixture | [`src/pages/PilotDemoPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/PilotDemoPage.tsx#L190-L225)<br>`mockApprovalWorkRequest`, `mockReviewIssues`, `mockReviewer`<br>*(Callbacks `onApprove` et `onReject` sont des fonctions vides `async () => {}`)* | `GET /v1/approvals/pending`<br>`POST /v1/approvals:decide` |
| **Export** | Mock / Fixture | [`src/pages/PilotDemoPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/PilotDemoPage.tsx#L228-L243)<br>`mockProfiles`<br>*(Génération simulée en ligne avec empreintes SHA-256 synthétiques figées)* | `GET /v1/export-profiles`<br>`POST /v1/exports/generate`<br>`GET /v1/exports/{id}/download` |
| **PortalRequests** | Mock / Fixture | [`src/pages/PilotDemoPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/PilotDemoPage.tsx#L246-L256)<br>`mockPortalRequests`<br>*(Callback `onAnswerRequest` est une fonction vide `async () => {}`)* | `GET /v1/issues?type=missing_document`<br>`POST /v1/portal/requests/{id}:answer` |
| **InternalMetrics** | Mock / Fixture | [`src/components/domain/InternalMetricsScreen.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/components/domain/InternalMetricsScreen.tsx#L51-L95)<br>`defaultMockMetrics`<br>*(Utilisé par défaut car aucun prop `metrics` n'est transmis par `PilotDemoPage`)* | `GET /v1/metrics/review-effort` |

**Preuve technique :**  
Une recherche sur l'ensemble de `src/components/domain/` et `src/pages/PilotDemoPage.tsx` confirme la présence de **zéro appel HTTP** (`fetch()`, `axios` ou client OpenAPI). Les composants d'écran sont conçus comme des composants purs d'affichage alimentés par des props.

---

## 2. Authentification sur `/pilot` et Réalité du Flux OIDC

### 2.1 Absence Totale de Garde d'Authentification sur `/pilot`
Dans [`src/App.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/App.tsx#L80) :
```tsx
<Route path="/viewer" element={<DocumentReviewPage />} />
<Route path="/pilot" element={<PilotDemoPage />} />
<Route path="/app" element={<RequireAuth><AppLayout /></RequireAuth>}>
```
La route `/pilot` est déclarée **en dehors du composant protecteur `<RequireAuth>`**. Tout utilisateur non identifié peut accéder directement à `/pilot` sans session.

### 2.2 Simulation des Rôles par Paramètre d'URL
Le contrôle d'accès basé sur les rôles (RBAC) sur `/pilot` est purement simulé à l'aide d'un paramètre de recherche d'URL (`searchParams`) :
```typescript
const roleParam = (searchParams.get('role') as any) || 'owner';
return <InternalMetricsScreen currentUserRole={roleParam} />;
```
Pour passer du rôle d'associé (`owner`) à celui de collaborateur (`staff`), il suffit de modifier manuellement l'URL en `/pilot?screen=metrics&role=staff`.

### 2.3 Aucun Flux OIDC Réel dans le Navigateur
- **Aucune dépendance OIDC :** `package.json` ne contient aucune bibliothèque cliente OIDC (`oidc-client-ts`, `keycloak-js`, `@react-keycloak/web`).
- **Aucune redirection :** Le frontend ne déclenche aucune redirection OAuth 2.0 / OIDC vers l'instance Keycloak (`/auth/realms/.../protocol/openid-connect/auth`), ne génère aucun challenge PKCE (`code_verifier`), et ne stocke ni ne rafraîchit aucun jeton JWT réel.
- **Le flux d'authentification existant :** Le formulaire de connexion sur `/login` interagit exclusivement avec `src/store/authStore.ts` et `src/services/authService.ts`, qui valide des mots de passe en mémoire et enregistre un objet utilisateur fictif dans le `localStorage` du navigateur.

---

## 3. Analyse de `e2e/pilot-journey.spec.ts` dans la CI

### 3.1 Exécution du Backend FastAPI en CI
**NON, le backend FastAPI ne tournait pas lors du test Playwright en CI.**  
Dans le fichier de configuration [`.github/workflows/ci.yml`](file:///c:/Users/21263/Downloads/fiscai/.github/workflows/ci.yml#L144-L146) :
```yaml
- name: Run Playwright E2E & Accessibility Suite
  run: |
    npx playwright test e2e/accessibility.spec.ts e2e/pilot-journey.spec.ts
```
Playwright démarre le serveur web défini dans [`playwright.config.ts`](file:///c:/Users/21263/Downloads/fiscai/playwright.config.ts#L14-L18) :
```typescript
webServer: {
  command: 'npm run preview -- --port 4173 --strictPort',
  url: 'http://localhost:4173',
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
},
```
La commande `npm run preview` ne démarre **que le serveur statique de prévisualisation de Vite** sur le dossier `dist/`. Aucun processus Python (`uvicorn apps.api.main:app`), aucun conteneur `avenel-api` ni aucune passerelle réseau n'était actif ou sollicité.

### 3.2 Requêtes Réseau
**Aucune requête HTTP n'a touché le backend.**  
La totalité du test s'est déroulée en circuit fermé dans le navigateur Chromium piloté par Playwright, interagissant uniquement avec le DOM React et le state local de `PilotDemoPage.tsx`.

### 3.3 Modalité Réelle de l'Étape "Approbation avec MFA TOTP"
L'affirmation selon laquelle un code MFA TOTP a été généré et validé en CI reposait sur une interaction purement visuelle dans le DOM.

**Code de test dans [`e2e/pilot-journey.spec.ts`](file:///c:/Users/21263/Downloads/fiscai/e2e/pilot-journey.spec.ts#L62-L69) :**
```typescript
// 9. Step 9: Approve as accountant with MFA
await expect(page.getByTestId('step-accountant-approval')).toBeVisible();
await expect(page.getByText('N° Ordre : OEC-45678')).toBeVisible();
await expect(page.getByText('Mehdi Bennani (Expert-Comptable Diplômé)')).toBeVisible();
const mfaInput = page.getByTestId('input-mfa-code');
await mfaInput.fill('987654');
await page.getByTestId('btn-approve-dossier').click();
```

**Code correspondant dans [`src/pages/PilotDemoPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/PilotDemoPage.tsx#L638-L660) :**
```tsx
<input
  id="mfa-token"
  type="text"
  value={mfaCode}
  onChange={(e) => setMfaCode(e.target.value)}
  className="w-full p-1.5 border border-slate-300 rounded font-mono text-center font-bold tracking-widest text-slate-900"
  data-testid="input-mfa-code"
/>
<button
  type="button"
  onClick={() => {
    setJourneyStep(10);
  }}
  className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded flex items-center gap-1.5 shadow-sm"
  data-testid="btn-approve-dossier"
>
  <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
  <span>Valider le dossier</span>
</button>
```

**Constat :**  
La saisie de `'987654'` était une affectation de variable d'état React (`useState`), et le clic sur le bouton ne faisait qu'exécuter `setJourneyStep(10)`. Aucun algorithme TOTP (RFC 6238) n'a été exécuté côté client, et aucun appel n'a vérifié le jeton auprès de Keycloak ou de FastAPI.

### 3.4 Rectification Formelle des Déclarations Antérieures
> [!WARNING]
> **Rectification des revendications du rapport Phase 5b :**
> - Les déclarations antérieures affirmant : *"Playwright end-to-end : un dossier mensuel complet ... approuvé en tant qu'expert-comptable avec MFA ... exécuté en CI contre docker-compose"* et *"Explication de la génération TOTP en CI via le secret de test Keycloak"* constituaient une **surévaluation (overclaim)** de l'intégration réelle du frontend.
> - **Ce qui est réellement vérifié :** La vérification cryptographique TOTP et la conformité du jeton MFA (`X-MFA-Token` avec signature Keycloak et fraîcheur `auth_time < 300s`) existent bel et bien et sont rigoureusement testées dans la suite Pytest backend (`tests/api/test_role_action_matrix.py` et `tests/integration/test_keycloak_jwks.py`).
> - **Ce qui ne l'était pas :** Le test Playwright E2E n'a pas validé ce flux contre le backend réel : il a simplement manipulé un formulaire simulé en local.

---

## 4. Tokens de Design Part E, Configuration Tailwind et Polices Typographiques

### 4.1 Origine et Emplacement des Déclarations
1. **Tokens Tailwind :**  
   Le fichier racine [`tailwind.config.js`](file:///c:/Users/21263/Downloads/fiscai/tailwind.config.js) a été configuré avec les couleurs officielles Part E (`sky: #0593C6`, `pink: #D83995`, `paper: #FCFFFF`, `surface: #F2F7F9`, `line: #D7E3E8`, `ink: #0A2533`, `ok: #1F7A4D`, `fail: #B4232C`).
2. **Polices physiques :**  
   Les fichiers binaires WOFF2 (`ibm-plex-sans-400.woff2`, `readex-pro-600.woff2`, etc.) sont présents physiquement dans `public/fonts/` et dans `apps/web/public/fonts/`.

### 4.2 Utilisation Réelle des Tokens Part E sur `/pilot`
- **Composants individuels :** Certains composants comme `ProposalReview.tsx` et `DocumentViewer.tsx` utilisent effectivement des classes Part E (`bg-paper`, `text-ink`, `border-line`).
- **Orchestrateur du parcours `/pilot` :** Le conteneur principal [`PilotDemoPage.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/pages/PilotDemoPage.tsx) ignore quasi totalement les tokens Part E et utilise les palettes standard Tailwind : `bg-slate-50`, `text-slate-900`, `bg-indigo-600`, `text-indigo-600`, `border-slate-200`.
- **Feuille de style globale active :** [`src/index.css`](file:///c:/Users/21263/Downloads/fiscai/src/index.css) (importée par `src/main.tsx`) applique `bg-slate-50 text-slate-900` sur le `body`, et définit `.btn-primary` avec `bg-brand-600` (palette FiscAI bleue par défaut).

### 4.3 Les Polices Auto-Hébergées Sont-Elles Utilisées sur `/pilot` ?
**NON.** Les polices auto-hébergées ne sont pas chargées par l'application Vite active :
- Les règles `@font-face` chargeant `/fonts/ibm-plex-sans-400.woff2` et `/fonts/readex-pro-600.woff2` ont été déclarées **exclusivement** dans [`apps/web/src/app/globals.css`](file:///c:/Users/21263/Downloads/fiscai/apps/web/src/app/globals.css) (l'ébauche Next.js abandonnée).
- Dans l'application Vite active, **ni `src/index.css` ni `index.html` ne contiennent de déclarations `@font-face`**.
- Lorsque le navigateur interprète `font-family: 'Readex Pro', sans-serif`, ne trouvant aucune police déclarée ni chargée, il se rabat silencieusement sur la police système générique sans-serif (Arial / Segoe UI).

---

## 5. Dénombrement Exact des Tests Frontend Couvrant le Code AVENEL

### 5.1 Répartition Détaillée des 161 Tests Unitaires Frontend (Vitest)

Sur les **161 tests** unitaires et composants exécutés par `npm test` :

```text
Total des tests Vitest : 161 tests (17 fichiers)
├── Tests spécifiques AVENEL : 22 tests (13,7 %) [3 fichiers]
├── Tests composants UI partagés : 7 tests (4,3 %) [1 fichier]
└── Tests spécifiques FiscAI PreClear : 132 tests (82,0 %) [13 fichiers]
```

#### Fichiers de Tests Couvrant Spécifiquement le Code AVENEL (22 tests) :
1. **`src/components/domain/Phase5Screens.test.tsx` (11 tests) :**
   - Teste le rendu d'ApprovalScreen avec les habilitations OEC et la prop MFA.
   - Teste le blocage de l'approbation en présence d'anomalies de révision non acquittées.
   - Teste la mention "Format non vérifié sur votre logiciel" dans ExportScreen tant qu'aucun round-trip n'est validé.
   - Teste la saisie des réponses aux demandes de justificatifs dans PortalRequests.
2. **`src/components/domain/ProposalReview.test.tsx` (6 tests) :**
   - Teste la navigation au clavier (touches J / K).
   - Teste la mise à jour des boîtes englobantes (bounding boxes) lors de la sélection d'une ligne d'écriture.
   - Teste la confirmation d'une ligne individuelle avec la touche Entrée.
   - Teste l'absence stricte de bouton d'approbation globale par proposition (règle Part D.4).
   - Teste qu'aucun raccourci clavier ne permet de valider une écriture de façon unilatérale.
3. **`src/components/domain/ReconciliationScreen.test.tsx` (5 tests) :**
   - Teste le rendu des lignes de relevé bancaire et des propositions d'écritures candidates.
   - Teste le déclenchement de `onAcceptMatch` lors du clic sur "Rapprocher".
   - Teste le déclenchement de `onRejectMatch` lors du clic sur "Rejeter".
   - Teste l'acceptation du rapprochement via la touche Entrée.
   - Teste le rejet du rapprochement via la touche Échap.

#### Fichiers de Tests Couvrant FiscAI PreClear (132 tests) :
- `src/services/services.test.ts` (19 tests) — auth, dossiers, documents FiscAI
- `src/components/domain/components.test.tsx` (15 tests) — RiskBadge, DossierCard, etc.
- `src/pages/pages.test.tsx` (14 tests) — LandingPage, LoginPage, DossiersPage FiscAI
- `src/lib/riskScoring.test.ts` (13 tests) — calcul de score de risque douanier
- `src/lib/sqlGuard.test.ts` (13 tests) — filtre NLU anti-injection SQL
- `src/services/aiAnalysisService.test.ts` (12 tests) — pipeline des 7 agents IA FiscAI
- `src/lib/validation.test.ts` (11 tests) — validation des formulaires BADR
- `src/lib/checklist.test.ts` (7 tests) — checklist documentaire import/export
- `src/lib/extraction.test.ts` (7 tests) — extraction mockée de déclarations douanières
- `src/i18n/i18n.test.ts` (6 tests) — catalogue bilingue douanier
- `src/lib/alertRules.test.ts` (5 tests) — alertes sur code SH et packing list
- `src/lib/sanitize.test.ts` (5 tests) — échappement HTML et détection d'injections
- `src/services/reportService.test.ts` (5 tests) — rapports d'expertise douanière

#### Fichier de Composants Génériques (7 tests) :
- `src/components/ui/ui.test.tsx` (7 tests) — Modal, Pagination, EmptyState, ErrorState, SkeletonCard.

---

### 5.2 Tests E2E Playwright Couvrant AVENEL
Dans le répertoire `e2e/`, les tests qui ciblent les composants AVENEL sont :
1. **`e2e/pilot-journey.spec.ts` (1 scénario / 11 assertions d'étapes) :**
   Parcours du stepper mocké sur `/pilot?screen=journey` et consultation des métriques sur `/pilot?screen=metrics`.
2. **`e2e/accessibility.spec.ts` (7 tests) :**
   Scan d'accessibilité axe-core (0 violation sérieuse/critique) sur les 7 écrans AVENEL montés sur `/pilot`.
3. **`e2e/document-viewer.spec.ts` (1 scénario / 4 assertions) :**
   Vérification du zoom, pagination et calque d'overlay (160ms transition) sur `/viewer`.

Les 5 autres fichiers Playwright (`journey1` à `journey5`) ciblent exclusivement FiscAI PreClear et ne sont pas exécutés en CI.

---

## 6. Synthèse d'Arrêt pour Revue

1. **Le frontend actuel est un prototype purement visuel non câblé à l'API :**  
   Les écrans AVENEL sur `/pilot` et `/viewer` sont des interfaces React pures fonctionnant sur des fixtures statiques. Aucun composant UI n'effectue de requête réseau vers le backend FastAPI.
2. **L'authentification OIDC Keycloak n'est implémentée que côté backend :**  
   Le backend FastAPI valide rigoureusement les jetons JWT RS256, le RLS et la fraîcheur MFA. Cependant, dans le navigateur, il n'existe aucun client OIDC ; `/pilot` est ouvert sans authentification.
3. **Les tests E2E CI s'exécutaient en vase clos :**  
   Playwright ne testait que la compilation statique Vite sans backend FastAPI actif. L'approbation MFA en E2E était un clic dans un formulaire simulé.
4. **La charte graphique Part E est incomplète dans le runtime Vite :**  
   Les tokens de couleurs sont déclarés dans Tailwind mais mélangés à `slate`/`indigo` dans `PilotDemoPage.tsx`. Les polices auto-hébergées n'étaient déclarées dans `@font-face` que dans l'ébauche Next.js abandonnée et ne sont pas chargées par l'application Vite active.
5. **Seulement 22 tests unitaires frontend sur 161 (13,7 %) testent réellement du code AVENEL.**

Le système demeure à l'arrêt complet en attente de validation humaine.

