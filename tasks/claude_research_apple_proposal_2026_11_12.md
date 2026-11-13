# Research : proposition « outil scientifique à la Apple » (Claude, 2026-11-12)

Proposition seulement. Aucun code applicatif modifié, rien exécuté (ni shell, ni tests, ni serveur, ni navigateur). Baseline lue : `2a0acecc`, fichiers actuels.

## 0. Ce qui a été réellement inspecté

- **Captures ouvertes et regardées (9/9)** dans `C:/WINDOWS/TEMP/airbc-research-redesign/` : `after-overview`, `after-data-upload`, `after-parameter-calibration`, `after-simulation`, `after-flux-analysis`, `after-pathway-visualization`, `after-calibration-registry` (desktop 1440), `final-upload-390`, `final-network-390`.
- **Code lu** : `app/research.css` (lignes 1-90), `ResearchSectionNav.tsx` (entier), structure de `DataUpload.tsx` (sections et titres), `CalibrationJourney.tsx` et `calibration-journey.mjs` (versions que j'ai écrites, modifiées depuis par Codex : non relues ligne à ligne), le mandat et l'en-tête de `fla_current_tasks.md`.
- **Non vérifié** : aucune observation live des routes `:3100` ; états peuplés (fichier importé, simulation lancée, sélection dans le graphe, chat ouvert) ; `SimulationWorkspace`, `FluxAnalysis`, `PathwayVisualization`, `NetworkGraph`, `PlatformHeader` et les scénarios e2e n'ont pas été relus. Les constats sur ces pages viennent des captures seules. Certaines captures précèdent le dernier polissage du chat.

## 1. Problèmes UX prioritaires

| # | Sév. | Constat | Preuve |
| --- | --- | --- | --- |
| 1 | Haute | **Faux onglets.** La barre sous le titre a l'apparence d'onglets mais ce sont des ancres de défilement ; l'onglet « actif » ne correspond pas à ce qui est à l'écran. | Capture Data Upload : « Metabolite mapping » souligné alors que « File & preview » est en haut. Capture Calibration : « Advanced » actif alors que la page est en haut. `ResearchSectionNav.tsx` : `href="#id"`, `active` mis à jour au clic/hash seulement. |
| 2 | Haute | **L'action interdite est le contrôle le plus visible.** Bouton rouge plein « Activate », définitivement désactivé, au centre de Calibration. | Capture Calibration. Un bouton qui ne peut jamais servir n'est pas un bouton. |
| 3 | Haute | **Le rouge veut tout dire** : lien « Change source », onglet actif, item de sidebar, bouton primaire, bouton désactivé, barres de flux. Impossible de distinguer action, sélection, marque et alerte. | Toutes les captures ; `research.css` (`#e24958`, `#f0737e`). |
| 4 | Haute | **Trois navigations superposées sur Calibration** : sidebar, faux onglets (Data verification / Reference profile / Advanced), puis puces de parcours (Data / Verification / Calibration / Results) sans état lisible. | Capture Calibration. |
| 5 | Moyenne | **Sections vides affichées d'office.** Data Upload montre « Metabolite mapping : No mapping available » et un « Review » avant tout fichier ; Results montre trois sections vides, des compteurs « 0 / 0 / — » et un filtre « Keep » présélectionné sur une liste vide ; Flux a des séparateurs entourant du vide. | Captures Data Upload, Results, Flux. |
| 6 | Moyenne | **« Not declared » sans moyen de déclarer.** Review liste unités et compartiments manquants mais n'offre aucun champ. | Capture Data Upload ; `fla_current_tasks.md` (« NEXT: implement explicit upload metadata »). |
| 7 | Moyenne | **Identifiants bruts et valeurs non formatées en texte d'interface** : `assumed_mM_historical_model_convention`, `extracellular_first/2`, « 633.0913816667514 » ; limites en liste de 12 puces avec doublons (unités ×2, bandes ×2). | Capture Calibration. |
| 8 | Moyenne | **Débordement à 1440 px** : « 3.82e+3 » et « Ranked by pathway flux total » rognés à droite ; tables et lignes étirées sur ~1160 px sans largeur maximale. | Capture Flux ; `research.css` (pas de `max-width`). |
| 9 | Moyenne | **Overview = copie de la sidebar** (7 liens + sous-titres), sans aucune information d'état. | Capture Overview. |
| 10 | Basse | Puces statiques qui ressemblent à des boutons (« Bordbar defaults active », « Static network », « 1 pathway », « DOMINANT PATHWAY ») ; « Provenance » en double (ancre + disclosure) ; étiquettes du graphe chevauchant les nœuds ; lanceur de chat posé sur le contenu en mobile. | Captures Simulation, Flux, Pathway, `final-network-390`. |

Ce que Codex a bien fait et que je garde : suppression des héros, cartes aplaties, ligne de contexte dataset, valeurs non arrondies dans l'aperçu, legacy replié, graphe compact par défaut.

## 2. Architecture d'information

Routes et URL inchangées. Libellés de sidebar inchangés (anglais).

| Route | But unique | Action principale | Vues (contrôle segmenté réel) |
| --- | --- | --- | --- |
| `/research` | Où en est mon travail | Continuer l'étape suivante | aucune |
| `/research/data-upload` | Importer et décrire un jeu de données | Import file → Check contract | étapes : File · Describe · Check |
| `/research/parameter-calibration` | Vérifier mes données face au moteur ; consulter la référence | Check contract | Your data · Reference · Legacy |
| `/research/simulation` | Lancer une trajectoire et la lire | Run simulation | aucune (réglages à gauche, résultat à droite) |
| `/research/flux-analysis` | Lire les flux par voie | Re-estimate | sélecteur de voie |
| `/research/pathway-visualization` | Explorer le réseau | aucune (lecture) | Compact · Full |
| `/research/calibration-registry` | Retrouver les runs enregistrés | aucune | filtre de verdict, seulement s'il y a des runs |

Décisions de structure :

- **Supprimer la barre d'ancres** (`ResearchSectionNav`). Une page courte défile ; une page à contenus alternatifs utilise un vrai contrôle segmenté qui affiche une seule vue. Les anciens `?subsection=` et `#id` restent honorés : ils sélectionnent la vue correspondante (table d'alias existante conservée).
- **Un inspecteur à droite** (320 px, repliable ; feuille basse en mobile) remplace les disclosures « Provenance », « Selection & details », le reçu et les limites. Même emplacement sur toutes les pages : la provenance n'est jamais cachée, jamais dans le flux principal.
- **Où va chaque fonction actuelle** :
  - contexte dataset → ligne de statut unique sous le titre (non répétée dans la page) ;
  - puces de parcours Calibration → supprimées, remplacées par trois lignes de statut (voir §5) ;
  - legacy/advanced → vue « Legacy » de Calibration, intacte (mêmes paramètres, mêmes payloads) ;
  - Results summary → une ligne de texte ; filtres → masqués tant que le registre est vide.

## 3. Direction visuelle et tokens

**Recommandation : sombre « graphite » neutre, limité à `.research-workspace`.** Raisons : la coquille (sidebar, Home, Monitoring) est sombre et hors périmètre ; les couleurs de voies du graphe sont réglées pour fond sombre ; aucun changement global nécessaire. **Alternative courte** : thème clair « papier » (`--r-bg:#fff`, `--r-text:#1d1d1f`) pour la seule zone de contenu, meilleur pour tables denses et impression, mais contraste dur avec la sidebar et recalibrage des couleurs du graphe ; à garder pour plus tard, les tokens ci-dessous le permettent.

```css
.research-workspace {
  --r-bg:#101114; --r-surface:#16181d; --r-line:#ffffff14; --r-line-strong:#ffffff26;
  --r-text:#f2f3f5; --r-text-2:#a8adb7; --r-text-3:#7d838e;
  --r-accent:#4c9dff;            /* interactif uniquement : liens, focus, primaire, sélection */
  --r-ok:#3fb97f; --r-warn:#e0a93b; --r-blocked:#e5606c; --r-unknown:#7d838e;  /* états, jamais cliquables */
  --r-radius:6px; --r-focus:0 0 0 2px #101114, 0 0 0 4px var(--r-accent);
  --r-s1:4px; --r-s2:8px; --r-s3:12px; --r-s4:16px; --r-s5:24px; --r-s6:40px;
  --r-content:1080px; --r-inspector:320px;
}
```

- **Couleur** : bleu = interactif ; rouge = bloqué/erreur seulement ; vert/ambre = état ; les couleurs de voies restent propres au graphe et aux barres. Le rouge de marque reste dans la sidebar (hors périmètre).
- **Typographie** (police existante) : titre 22/28 semi-gras ; section 15/22 semi-gras ; corps 13/20 ; légende 12/16 ; chiffres en `font-variant-numeric: tabular-nums`, alignés à droite dans les tables ; pas d'échelle liée au viewport, pas d'interlettrage négatif.
- **Surfaces** : fond unique, séparateurs 1 px, pas de cartes imbriquées. Seuls cadres autorisés : champ de saisie, zone de dépôt, graphe, inspecteur.
- **Contrôles** : un bouton primaire plein par page ; secondaires en contour ; boutons-icônes Lucide 32 px avec `title`/`aria-label` ; contrôle segmenté (`role="tablist"`, flèches clavier) ; états = pastille 8 px + texte, sans bordure ni fond, donc non confondables avec un bouton.
- **Mise en page** : contenu `max-width: var(--r-content)` aligné à gauche ; inspecteur fixe à partir de 1280 px, repliable ; < 1024 px inspecteur en feuille basse ouverte par un bouton « Details » ; < 640 px une colonne, tables en défilement horizontal interne avec première colonne figée, barre d'action collante en bas pour l'action principale.

## 4. Pages : mise en page et états

1. **Overview** : titre « Research », puis trois lignes d'état cliquables, chacune « étape · état réel · prochaine action » :
   - Data : source active, contrat non vérifié / invalide / valide ;
   - Calibration : moteur non qualifié pour données contractuelles ; référence disponible / absente ;
   - Results : n runs enregistrés (0 → « No recorded runs »).
   - États : *loading* squelette de 3 lignes ; *error* ligne « Status unavailable » + Retry. Plus de liste de liens dupliquant la sidebar.
2. **Data Upload** : voir §5.
3. **Calibration** : voir §5.
4. **Simulation** : deux colonnes ≥ 1024 px, réglages (Storage duration, Curve fit strength, pH perturbation, ODE solver) à gauche sur 320 px, résultat à droite ; primaire « Run simulation ».
   - *empty* : zone résultat avec une phrase « No simulation yet » ;
   - *loading* : bouton en cours, indéterminé ;
   - *error* : message + paramètres conservés ;
   - *populated* (spécification, pas de données réelles ici) : graphe de trajectoires puis journal replié.
   - Source des paramètres (« Bordbar defaults ») dans l'inspecteur, pas en puce.
5. **Flux Analysis** : barre d'outils (sélecteur de voie, « Re-estimate », état textuel), puis une ligne de trois chiffres (Dominant pathway, Total flux, Reactions), puis le graphe en barres pleine largeur de contenu. Le « pathway readout » devient une légende d'une ligne sous le graphe. Provenance dans l'inspecteur. *Empty/error* : une phrase à la place du graphe.
6. **Pathway Map** : le graphe occupe la zone ; barre d'outils unique : segmenté Compact | Full, lecture/retour, zoom −/reset/+. L'état « static network » passe en légende sous le graphe avec « 9 connectors / 12 bridges (display only, not kinetic reactions) ». Sélection → inspecteur. Étiquettes décalées hors des nœuds. *Blank guard* : si 0 nœud, message explicite.
7. **Results** : registre vide → une seule phrase « No calibration runs recorded yet » + lien Calibration ; pas de compteurs, pas de filtres. *Populated* (spécification) : table Run · Date · Status · Verdict · Score, filtre de verdict, ligne → inspecteur d'évidence. « Completed » toujours libellé « (unverified) ».

## 5. Wireframes

### Data Upload

```text
Data Upload
● Bordbar reference dataset · reference data                       [Details ⓘ]
──────────────────────────────────────────────────────────────────────────────
 1 File            2 Describe            3 Check          (étapes : état, non cliquables avant d'être atteintes)

 ┌ Drop a CSV / XLS / XLSX file, or [Choose file] ┐        [ Import file ]  ← primaire
 └────────────────────────────────────────────────┘
 (rien d'autre tant qu'aucun fichier : pas de sections vides)

── après import ───────────────────────────────────────────────────────────────
 experiment_07.csv · 14 time points · 23 columns · 19 mapped       [Replace]
 Preview (valeurs exactes du fichier, non arrondies, défilement interne)
 Mapping   Column → Model pool        ○ 4 unmapped (liste)

 2 Describe   (rien n'est prérempli ; vide = manquant)
   Time unit [ — ▾ ]   Time origin [ — ▾ ]   Subject [ donor id / declared group ]
   Hematocrit [   ] source [ — ▾ ]
   Per channel:  Compartment [ — ▾ ]   Kind [ absolute | relative ]   Unit [ — ▾ ]
   ⚠ Relative channels are kept as declared; they are never converted to mM.
   Initial state: [ measured at first time | declared table ]  (never borrowed from the reference)

 3 Check                                                    [ Check contract ]
   ● Data valid          No — 6 fields missing (liste cliquable → champ)
   ● Engine compatible   Not checked
   ● Launch allowed      No
                                                   Continue to Calibration →
```

Mobile 390 : une colonne, étapes en « 1/3 File », barre collante en bas portant l'action de l'étape. L'étape Describe est l'emplacement du travail « upload metadata » annoncé ; tant qu'elle n'est pas câblée, elle affiche la liste des champs manquants en lecture seule (comportement actuel de `DRAFT_MISSING_FIELDS`), sans champ factice.

### Calibration

```text
Calibration
● experiment_07.csv · upload                                        [Details ⓘ]
──────────────────────────────────────────────────────────────────────────────
 [ Your data | Reference | Legacy ]                       (segmenté : une vue à la fois)

 YOUR DATA
   ● Data valid          Yes
   ● Engine compatible   No — engine not qualified for new contractual datasets
   ● Launch allowed      No
   Issues (2)   engine_requires_mM · channels[3] · …
   [ Check contract ]  ← primaire          Calibrate: unavailable until the engine is qualified
   (sans upload : « No user dataset. Import data to check it. » + lien Data Upload)

 REFERENCE                                  🔒 Read-only · cannot be activated
   Provisional extracellular reference — archived table, J1–J15
   EGLC  RMSE 0.168   J15 +1.360   slope −0.264 / −0.474 per day
   ELAC  RMSE 0.829   J15 −3.184   slope +0.679 / +0.837 per day
   Species [ EGLC ▾ ]   graphe observé/prédit + table Day·Observed·Predicted·Residual·Normalized
   Not met: ATP/ADP J15 targets · Worst channel: EINO (633.1) · Units assumed mM
   Inspecteur : receipt d8f30351…, objective, scope, geometry H 0.58 borrowed, donor unknown,
                limites complètes (groupées : Energy · Fit · Data provenance), dédoublonnées

 LEGACY   bandeau : « Legacy path without a data contract: results are unverified and never activated automatically. »
          puis l'écran actuel inchangé (sélection Vmax, stratégie, lancement)
```

Changements clés : le bouton « Activate » disparaît au profit d'une ligne d'état verrouillée (aucune action possible n'est suggérée) ; les trois réponses du preflight sont le cœur de la page ; les valeurs gardent leur précision dans la table, le résumé affiche 4 chiffres significatifs avec la valeur complète en `title` ; les identifiants bruts vont dans l'inspecteur avec un libellé lisible devant.

## 6. Plan d'implémentation (3 tranches réversibles)

**Tranche 1 — socle (CSS + coquille Research, un commit, revert simple)**
- `app/research.css` : tokens §3 en variables, `max-width`, classes `.r-status`, `.r-segmented`, `.r-toolbar`, `.r-inspector`, suppression des règles `[class*=…]` de neutralisation au fur et à mesure.
- Nouveau `components/platform/research/ResearchPage.tsx` (titre, ligne de statut dataset, slot action, slot inspecteur), `SegmentedControl.tsx`, `StatusLine.tsx`, `Inspector.tsx`.
- `WorkspaceFeatureSurface.tsx` / `ResearchDatasetBanner.tsx` : utilisent `ResearchPage` ; `ResearchSectionNav.tsx` retiré du rendu (fichier gardé une tranche pour retour arrière ; alias `?subsection=` déplacés dans `SegmentedControl`).
- Supprimé : barre d'ancres, lien rouge « Change source » (devient action de l'inspecteur + Data Upload), puces statiques.

**Tranche 2 — Data Upload et Calibration**
- `DataUpload.tsx` : étapes, sections conditionnelles, bloc Check réutilisant `preflightView`.
- `CalibrationJourney.tsx` scindé en `calibration/YourDataPanel.tsx`, `ReferencePanel.tsx` ; `ParameterCalibration.tsx` rendu dans la vue Legacy, logique et payloads intacts.
- `calibration-journey.mjs` : ajout de `groupLimitations()` et d'un formatteur d'affichage ; aucune règle existante modifiée.
- e2e : `reference-activate` (bouton désactivé) remplacé par `reference-activation-status` (texte verrouillé) ; le test vérifie qu'il n'existe **aucun** contrôle d'activation.

**Tranche 3 — Simulation, Flux, Pathway, Results, Overview**
- Mise en page deux colonnes, inspecteur, états vides en une phrase, Overview en lignes d'état.
- `NetworkGraph.tsx` : décalage des étiquettes seulement (pas de changement de données ni de disposition).

Extrait indicatif (dans cette proposition uniquement) :

```tsx
<StatusLine tone="blocked" label="Engine compatible" value="No" detail={gate.reason} />
// .r-status::before { content:""; width:8px; height:8px; border-radius:50%; background:var(--tone); }
```

Conservé partout : routes, identité et historique du dataset, valeurs et payloads, garde-fous d'activation et de preflight, Vmax-only/Km fixes. Reporté : champs de métadonnées réellement câblés au contrat (dépend du flux contrat), thème clair, persistance worker.

## 7. Critères d'acceptation

- **Navigation** : 7 routes répondent ; anciens `?subsection=`/`#id` ouvrent la bonne vue ; un seul `h1` par page ; aucune barre d'ancres.
- **Clavier/focus** : tout contrôle atteignable au Tab, anneau de focus visible (`--r-focus`), segmenté pilotable aux flèches, inspecteur fermable à Échap, ordre de tabulation = ordre visuel.
- **Largeurs 320 / 390 / 1440** : `scrollWidth ≤ innerWidth` sur les 7 pages ; aucune valeur rognée (cas « 3.82e+3 ») ; action principale visible dans le premier écran, y compris mobile ; le lanceur de chat ne recouvre ni graphe ni action.
- **Précision** : l'aperçu d'import affiche les valeurs exactes du fichier ; les tables affichent la valeur stockée ; tout résumé arrondi expose la valeur complète.
- **Continuité dataset** : la ligne de statut montre la même source sur les 7 pages après import, et après rechargement.
- **Garde-fous** : aucun contrôle d'activation pour la référence ; « Calibrate » contractuel absent ou inactif tant que `launch_allowed` est faux ; les trois réponses du preflight sont affichées séparément ; « relative » jamais libellé mM ; champs manquants affichés vides, jamais préremplis.
- **Graphe** : modes Compact et Full rendent ≥ 1 nœud (pas de zone vide), zoom et lecture fonctionnent, mention « display only » présente.
- **Honnêteté** : registre vide → une phrase, zéro ligne ; aucune chaîne de démonstration (donneurs, poches, scores, pourcentages) ; aucun appel réseau `POST /calibration/run`, `/calibration/jobs` ou simulation pendant les tests de navigation.
- **Régression** : tests Node de `calibration-journey` et `calibration-lifecycle` inchangés et verts ; TypeScript vert.

## 8. Risques et décisions à prendre

| Décision | Défaut recommandé |
| --- | --- |
| Sombre graphite ou clair papier | Sombre, limité à Research ; clair reporté |
| Accent interactif bleu, rouge réservé au blocage | Oui (sinon le problème n° 3 reste entier) |
| Retirer le bouton « Activate » au profit d'une ligne verrouillée | Oui ; implique de mettre à jour le scénario e2e existant |
| Supprimer la barre d'ancres | Oui, avec alias conservés |
| Overview en lignes d'état plutôt qu'en liste de liens | Oui |
| Étape « Describe » visible avant d'être câblée | Oui, en lecture seule (liste des manquants), sans champ factice |

Risques : l'inspecteur ajoute un composant partagé (à garder simple : pas de redimensionnement, pas d'état persistant) ; le scindage de `CalibrationJourney` touche des tests existants ; les états peuplés n'ont pas été observés et devront être vérifiés au navigateur par Codex avant validation.

## Résumé des décisions

Une page = un but, un titre, une action. Vraies vues segmentées à la place des faux onglets. Un inspecteur unique pour provenance et détails. Bleu pour agir, rouge pour bloquer, pastilles pour l'état. Sections vides supprimées, action interdite retirée de l'écran, et toutes les limites scientifiques visibles, groupées et dédoublonnées.
