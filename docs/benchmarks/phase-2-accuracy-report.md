# Phase 2 accuracy report — 300 synthetic documents

**Run:** 6 Nov 2026, `FULL_SYNTHETIC_RUN=1 python -m pytest tests/evaluation/test_synthetic_pipeline.py -k per_field_exact_match` (16 min, local OCR, no provider call).
**Scope:** synthetic invoices rendered to images and degraded (skew, noise, JPEG). Part H gates are only binding on a real labelled corpus (`tests/fixtures/real/`), which does not exist yet.
**Known weakness:** `supplier_if` on Arabic invoices (1.7 %); every miss was caught (0 silent errors), so these fields go to review.

The harness output follows unchanged.

---

# Rapport de Test du Pipeline Synthétique — Ingestion & Extraction

**Date d'exécution :** 2026-11-06 12:02:52Z
**Moteur OCR :** `RapidOCR / PaddleOCR ONNX PP-OCRv4 + Multilingual v3` (version `1.4.4`)
**Modèles de reconnaissance :** ONNX Latin & Arabe multilingues (ancrés par checksums SHA-256)
**Taille du corpus synthétique :** **300 documents**
**Composition du corpus :** **220 factures Français (FR)**, **60 factures Arabe (AR, synthetic, clean rendering)**, **20 factures Bilingues/Mixtes (FR/AR)**
**Perturbations appliquées aux images :** skew ±1.0°, Gaussian sensor noise (σ=6.0), JPEG quality 70

> [!IMPORTANT]
> Ce test évalue la robustesse de l'extraction sur des images synthétiques dégradées par bruit et compression.
> Conformément à la Partie H d'ARCHITECTURE.md, les portes cibles officielles ne sont validées
> que sur le corpus de test réel labellisé (tests/fixtures/real/).

## 1. Résultats Exact Match par Champ (Ensemble du Corpus)

| Champ extrait | Total | Exact Match | Échecs | Taux Exact Match | Seuil Cible Partie H |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `invoice_number` | 300 | 300 | 0 | **100.00%** | >= 97.0% |
| `invoice_date` | 300 | 299 | 1 | **99.67%** | >= 97.0% |
| `supplier_ice` | 300 | 298 | 2 | **99.33%** | >= 97.0% |
| `supplier_if` | 300 | 238 | 62 | **79.33%** | — |
| `total_ht` | 300 | 300 | 0 | **100.00%** | >= 98.0% |
| `total_vat` | 300 | 300 | 0 | **100.00%** | >= 98.0% |
| `total_ttc` | 300 | 300 | 0 | **100.00%** | >= 98.0% |

## 2. Résultats Exact Match par Langue

| Champ extrait | Français (FR - 220 docs) | Arabe (AR - 60 docs, synthetic, clean rendering) | Bilingue / Mixte (FR/AR - 20 docs) |
| :--- | :---: | :---: | :---: |
| `invoice_number` | 100.0% | 100.0% | 100.0% |
| `invoice_date` | 100.0% | 98.3% | 100.0% |
| `supplier_ice` | 100.0% | 96.7% | 100.0% |
| `supplier_if` | 98.6% | 1.7% | 100.0% |
| `total_ht` | 100.0% | 100.0% | 100.0% |
| `total_vat` | 100.0% | 100.0% | 100.0% |
| `total_ttc` | 100.0% | 100.0% | 100.0% |

## 3. Évaluation face aux Portes Cibles Partie H (Pilote)

| Porte Cible Partie H | Métrique | Cible Pilote | Résultat Obtenu | Statut |
| :--- | :--- | :---: | :---: | :---: |
| **ICE, N° Facture, Date** | Exact Match | >= 97.0% | **99.00%** | Atteint |
| **HT, TVA par taux, TTC** | Exact Match | >= 98.0% | **100.00%** | Atteint |
| **Erreurs silencieuses HT/TVA/TTC** | Silent Error Rate | 0.0% | **0.00%** | Atteint |

## 4. Taux d'Erreurs Silencieuses (Silent Error Rate)

| Champ extrait | Échecs totaux | Détectés (Caught) | Silencieux (Silent) | Taux d'erreur silencieuse |
| :--- | :---: | :---: | :---: | :---: |
| `invoice_number` | 0 | 0 | 0 | **0.00%** |
| `invoice_date` | 1 | 1 | 0 | **0.00%** |
| `supplier_ice` | 2 | 2 | 0 | **0.00%** |
| `supplier_if` | 62 | 62 | 0 | **0.00%** |
| `total_ht` | 0 | 0 | 0 | **0.00%** |
| `total_vat` | 0 | 0 | 0 | **0.00%** |
| `total_ttc` | 0 | 0 | 0 | **0.00%** |

## 5. Analyse Transparente des Échecs sous Bruit d'Image

Détail des documents ayant présenté des écarts sous les perturbations de scan :

- **Document `fr_inv_002`** (Langue: `fr`, Catégorie: `french_corporate`) :
  - `supplier_if` : attendu `56789012`, extrait `None`
- **Document `fr_inv_016`** (Langue: `fr`, Catégorie: `french_corporate`) :
  - `supplier_if` : attendu `78901234`, extrait `None`
- **Document `ar_inv_001`** (Langue: `ar`, Catégorie: `arabic_commercial`) :
  - `supplier_if` : attendu `34567890`, extrait `None`
- **Document `ar_inv_002`** (Langue: `ar`, Catégorie: `arabic_commercial`) :
  - `supplier_if` : attendu `12345678`, extrait `None`
- **Document `ar_inv_003`** (Langue: `ar`, Catégorie: `arabic_commercial`) :
  - `supplier_if` : attendu `45678901`, extrait `None`
- **Document `ar_inv_004`** (Langue: `ar`, Catégorie: `arabic_commercial`) :
  - `supplier_if` : attendu `12345678`, extrait `None`
- **Document `ar_inv_005`** (Langue: `ar`, Catégorie: `arabic_commercial`) :
  - `supplier_if` : attendu `23456789`, extrait `None`
- **Document `ar_inv_006`** (Langue: `ar`, Catégorie: `arabic_commercial`) :
  - `supplier_if` : attendu `34567890`, extrait `None`
