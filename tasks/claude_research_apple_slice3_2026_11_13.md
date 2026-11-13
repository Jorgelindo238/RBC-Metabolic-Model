# Research « Apple » : tranche 3 (Simulation, Flux Analysis, Pathway Map, Results)

Date 2026-11-13. Mandat `tasks/claude_research_apple_slice3_dispatch_2026_11_13.md`. Les quatre pages sont implémentées. Rien n'est commité ; aucune simulation, calibration, intégration ODE ni écriture Supabase n'a été lancée.

## Socle partagé (modifié)

- `apps/web/app/research.css` :
  - `button.r-primary` (bleu local Research ; la variante globale `Button` est intacte) ;
  - `.r-split` (réglages 300 px + résultat, une colonne sous 1024 px) ;
  - `.r-settings`, `.r-legend`, `.r-metrics`, `.r-table-scroll`.
- `apps/web/components/platform/ResearchSectionNav.tsx` : prop `hidden`. La barre n'est plus rendue, mais les anciens liens `?subsection=` et `#id` continuent d'ouvrir et de faire défiler leur cible.
- `apps/web/components/platform/WorkspaceFeatureSurface.tsx` : liens de saut visibles seulement sur Overview ; mode `hidden` sur les autres pages de tâche ; Calibration garde sa propre gestion des vues.
- `apps/web/components/platform/research/Inspector.tsx` : correctifs Codex conservés (focus à l'ouverture, Échap et retour au déclencheur, `aria-controls`). Ajouts :
  - `anchorId` : un ancien lien « Provenance » (`#id` ou `?subsection=id`) ouvre l'inspecteur ;
  - mode contrôlé `open` / `onOpenChange`, utilisé pour qu'une sélection de graphe ou de ligne ouvre l'inspecteur.

## 1. Simulation (`components/features/SimulationWorkspace.tsx`)

- **Logique intacte** (lignes 1-181 : hooks, payload `simulationRequestMetadata`, snapshot, RoBoCop) ; seul le rendu change.
- **Mise en page** : réglages à gauche, trajectoires à droite. Durée, curve fit, pH (et sévérité/durée si perturbation) ; solveur ODE en divulgation « Solver ». Mêmes bornes, pas et valeurs.
- **Action** : « Run Simulation » unique, bleu.
- **États** : vide (« No simulation yet »), chargement sans fausse progression, erreur (réglages conservés), résultat (ligne de synthèse, `MetaboliteChart`, « Run log » et « Interpretation » repliés, toujours disponibles).
- **Inspecteur « Run details »** : contexte dataset, paramètres moteur (défauts Bordbar ou calibration explicitement active). L'upload est indiqué comme « envoyé comme contexte », compté appliqué seulement si le résultat le rapporte (`dataset_applied`) ; source des paramètres, motif de repli, solveur. Rappel : une trajectoire n'est pas une validation.
- **Supprimé** : dégradé décoratif, cartes et badges de statut.

## 2. Flux Analysis (`components/features/FluxAnalysis.tsx`)

- **Barre** : Re-estimate (primaire), filtre de voie (`aria-label="Pathway filter"` conservé), état textuel.
- **Erreur** : une ligne `role="alert"` avec reprise par Re-estimate.
- **Synthèse** (seulement avec un résultat) : voie dominante, flux total, réactions, voies affichées.
- **Données** : chaque voie devient une section avec total, « n non-zero of m modeled », plus grand |flux|, puis une ligne par réaction (barre centrée sur zéro, signe visible, valeur à taille fixe). La valeur exacte de l'API est en `title`. L'ancien graphe SVG à `viewBox` fixe réduisait les étiquettes vers 5 px sur mobile et arrondissait par `toFixed(1)` ; il n'est plus utilisé ici. `flux/FluxBarChart.tsx` est inchangé, ses `PATHWAY_GROUPS`/`PATHWAY_COLORS` sont réutilisés.
- **Inspecteur « Flux details »** (ancre `comparison-view`) : nature des valeurs (estimations de taux du service pour un instantané de concentrations ; ni flux mesurés, ni trajectoire, ni validation), origine de l'instantané (dernière valeur de chaque série mappée, sinon défauts de référence), concentrations issues de l'upload, calibration, source, unités telles que renvoyées, sans conversion.
- **Inchangés** : estimation, payload `/flux/estimate`, filtrage, tri, signes.

## 3. Pathway Map (`components/features/PathwayVisualization.tsx`)

- **Logique et données inchangées** : chargement, `buildCompactBridgeGraph`, playback, `NetworkGraph` (non modifié). Aucune topologie, disposition ni donnée nouvelle.
- **Barre** : Refresh network, état, comptes connectors/bridges ou metabolites/reactions. Modes « Compact graph | Full model map » (`aria-pressed` conservé).
- **Lecture** : boutons lecture/restart et curseur **uniquement** si une trajectoire de simulation existe. Sinon, note explicite « Static network… no playback ». La note précise aussi que connecteurs et bridges du mode compact sont des regroupements d'affichage, pas des réactions cinétiques.
- **Graphe** : hors carte, pleine largeur. État explicite si 0 nœud (`pathway-graph-empty`), distinct de chargement, erreur et absence de réseau.
- **Inspecteur « Pathway details »** (ancre `pathway-story`) : sélection (nom, type, voie, concentration ou flux avec valeur complète en `title`, compartiment ou réaction, résumé, Clear), sélection rapide, atlas compact ou groupes de voies, provenance, mention « disposition d'affichage seulement ». Une sélection dans le graphe ouvre l'inspecteur.
- **Supprimé** : `<details>` « Selection & details » et sa carte imbriquée, et « Provenance » en double.

## 4. Results (`RegistrySurface` dans `components/platform/WorkspaceFeatureContent.tsx`)

- **Registre indisponible** (`runsError`, désormais transmis) : erreur explicite + Retry, présentée comme une erreur et non comme « zéro run ».
- **Registre vide** : une phrase « No calibration runs recorded yet. » + lien Calibration (ou « workspace selection pending »). Pas de compteurs, filtres ni sections vides.
- **Registre peuplé** :
  - ligne « N recorded runs · M completed (unverified) », puis filtre de verdict (`Run outcome filter` conservé) ;
  - table compacte Run · Verdict · Completion · Score · Final loss · Cases · Recorded, en défilement interne ;
  - « Completed » devient « Completed (unverified) » ; Cases en « x/y » réels, sans pourcentage ; valeurs complètes en `title`.
- **Inspecteur « Run evidence »** (ancre `artifact-trace`) : un clic sur un run ouvre verdict, completion, score, loss, cases, scope, stratégie, manifeste (run le plus récent), « Biological validation: not established by registry completion » et lien « Inspect run » vers `/runs/{id}`.

## Fonctions préservées

Routes, URL publiques, payloads (`/simulate…`, `/flux/estimate`, `/pathway/network`), contextes RoBoCop, sélection/zoom/reset de `NetworkGraph`, playback, filtres de registre, liens vers les preuves. Aucune modification de `src/`, `RBC/`, Km/Vmax/J1, solveurs, Supabase, Home/Monitoring/auth/Vercel.

## Tests

Exécutés :
- TypeScript (`tsc --noEmit --incremental false`) : 0 erreur.
- Tests Node (`server-run-access`, `calibration-journey`, `calibration-lifecycle`) : 42/42.
- Scénarios navigateur : voir « Résultats navigateur » plus bas.

Scénario `apps/web/e2e/research-workspace.scenarios.mjs` adapté :
- **Simulation** : état vide, bouton actif mais jamais cliqué, curseur au clavier.
- **Flux** : au moins une réaction affichée, aucune erreur, aucune valeur `.r-num` rognée, avant et après filtrage, une seule voie après filtre « Glycolysis ».
- **Pathway** : aucune erreur, aucun bouton de lecture sans trajectoire, note « display-only », graphe non vide en Compact ET Full.
- **Results** : registre vide (une phrase, aucun filtre ni table), indisponible (échec si `REQUIRE_LIVE_REGISTRY=1`) ou peuplé (filtre Keep, aucun pourcentage).
- **Inspecteur sur les trois premières pages** : ouverture, focus dedans, pas de débordement, Échap ferme et rend le focus au déclencheur.
- **Largeurs** : 1440, 390 et 320 px (viewport 320 déjà présent chez Codex).

## Résultats navigateur (exécutés le 2026-11-13, serveurs existants web :3100 et API :8010, aucun relancé)

- `node apps/web/e2e/research-workspace.scenarios.mjs` : **27/27 PASS**, exit 0, exécuté deux fois (avant et après les retouches visuelles). Couvre les 7 routes, les anciens liens Calibration, et l'import CSV réel de test → mapping → porte Calibration → retour à la référence, à 1440, 390 et 320 px. Aucune erreur console ou page ; aucune requête de lancement simulation/calibration (garde du scénario).
- `node apps/web/e2e/calibration-monitoring.scenarios.mjs` avec `BASE_URL=http://127.0.0.1:3100` et `REQUIRE_LIVE_REGISTRY=1` : **6/6 PASS**, exit 0.
- TypeScript : 0 erreur après les retouches. Node : 42/42.
- Captures inspectées visuellement (hors Git, `C:/WINDOWS/TEMP/airbc-research-redesign/`) : Simulation desktop, Flux 320 px (aucune valeur coupée, « 3.82e+3 » entier), Pathway desktop et 390 px.

Retouches issues de cette inspection :
- piste et pouce des curseurs en accent bleu dans Research (`[data-slot="slider-range"|"slider-thumb"]`) ;
- marge à droite du bouton d'inspecteur (il touchait le bord en pleine largeur sur Pathway) ;
- `NetworkGraph.tsx` : `textposition` des étiquettes de métabolites ancrée à l'opposé du nœud au lieu de `middle center`. Changement visuel seulement : mêmes positions, identifiants, données et disposition.

## Limites et reprise Codex

- Le lanceur de chat flottant recouvre encore une partie du graphe Pathway en mobile (par exemple l'étiquette B23PG à 390 px). Préexistant, hors de ces pages ; à traiter avec la coquille.
- Le bouton d'inspecteur est seul sur sa ligne au-dessus du contenu. Fonctionnel et accessible, mais il pourrait rejoindre la barre d'outils de chaque page dans une passe ultérieure.

- La sélection d'un nœud Plotly n'est pas automatisée : l'ouverture de l'inspecteur par sélection est vérifiée au code ; le test couvre le bouton d'inspecteur.
- Zoom/reset restent ceux de `NetworkGraph`, non modifiés ni re-testés ici.
- États « résultat » de Simulation et « registre peuplé » de Results : vérifiés au code seulement. Aucune simulation n'a été lancée, et le registre réel est vide.
- `getRegistryStatusTone` n'est plus utilisé (laissé, sans effet).

## Revue et correctifs Codex (2026-11-13)

Les limites ci-dessus decrivent la livraison Claude avant cette revue.

- Corrige `PlatformFeaturePage.tsx`: les erreurs/configurations manquantes du
  registre atteignent maintenant la vue Results au lieu de court-circuiter sa
  coquille Research et son bouton Retry.
- Corrige le contraste des boutons bleus Research (texte sombre), sans modifier
  le composant Button global.
- En mobile, le lanceur RoBoCop ferme est dans le flux de la coquille au-dessus
  du workspace, pas sur les noeuds du graphe. Le panneau ouvert reste flottant.
- Simulation distingue desormais les parametres demandes de la source declaree
  dans le resultat (provided/defaults/auto_loaded). Pas de changement du payload.
- Le scenario Research couvre maintenant le clic pointeur sur un vrai noeud
  Plotly, l'ouverture de l'inspecteur, Echap, zoom/reset, la difference Compact /
  Full et l'absence de recouvrement par le lanceur de chat.
- Ajoute cinq tests de rendu isoles dans `lib/research-rendering.test.mjs`:
  registre vide, indisponible, peuple, et transmission des erreurs/configuration
  manquante par la page serveur. Le registre peuple est une fixture en memoire,
  jamais ecrite dans Supabase; ses interactions ne sont pas validees en navigateur.
- Ajoute `e2e/research-simulation-fixtures.scenarios.mjs`: resultat, chargement,
  provenance et erreur a 1440/390/320 px. Chaque requete de simulation est
  interceptee et satisfaite dans le navigateur avant le backend; aucune ODE ne
  s'execute. Les sorties de fixtures ne sont pas des preuves scientifiques.

Validations Codex executees:
- TypeScript: 0 erreur.
- Tests Node: 47/47 (42 existants + 5 rendus isoles).
- Research: 27/27, trois largeurs, selections/zoom ajoutes, import CSV reel et
  anciens liens compris; aucun lancement scientifique reel, aucune erreur console
  sur la passe finale. Une premiere passe avait rencontre ERR_NETWORK_CHANGED;
  le premier test de clic SVG a aussi ete adapte a la couche de pointeur Plotly,
  sans modifier le comportement du graphe ni injecter un evenement Plotly.
- Calibration/Monitoring: 6/6 avec `REQUIRE_LIVE_REGISTRY=1`.
- Fixtures Simulation: 3/3, source auto_loaded testee malgre une demande sans
  custom_params; succes, echec et conservation des reglages controles.
- Build de production (`next build`): succes, compilation, types et generation
  des 28 pages termines. Avertissements non bloquants: plusieurs lockfiles sur
  la machine influencent la racine de tracing et une grosse chaine du cache
  webpack; aucune configuration globale n'a ete modifiee pour les masquer.

Suite fonctionnelle recommandee, non lancee: cabler la saisie des metadonnees
Data Upload au contrat (temps, unite/nature et compartiment par canal, donneur
ou groupe, geometrie documentee et provenance de l'initialisation), sans
normalisation ou J1 implicites et sans lever la restriction du moteur non qualifie.
