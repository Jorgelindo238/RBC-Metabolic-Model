# Research « Apple » : tranche 2 (Data Upload et Calibration), livraison pour revue

Date 2026-11-12. Outils fichiers seulement : rien exécuté (ni TypeScript, ni tests Node, ni scénarios navigateur, ni serveur). L'UI n'est pas validée.

## Fichiers modifiés

- `apps/web/components/features/DataUpload.tsx` :
  - indicateur d'étapes « 1 File · 2 Describe · 3 Check » (état, pas navigation) ;
  - plus de sections vides : aperçu, mapping et « Describe and check » n'apparaissent qu'après import ;
  - « Describe and check » : lignes d'état et liste des champs absents du fichier (`DRAFT_MISSING_FIELDS`), en lecture seule, sans champ factice ;
  - logique d'upload, appels API et libellé « Upload & parse » inchangés ; identifiants `#dataset-intake`, `#validation-alignment`, `#data-readiness` conservés.
- `apps/web/components/features/CalibrationJourney.tsx` (réécrit, nouvelle prop `view`) :
  - vue « Your data » : trois lignes d'état (Data valid / Engine compatible / Launch allowed), « Check data contract » en action principale, problèmes, champs manquants ; sans upload, une phrase et un lien vers Data Upload ;
  - plus de bouton de lancement contractuel : texte `contract-launch-status` ;
  - vue « Reference » : plus de bouton « Activate » ; ligne verrouillée `reference-activation-status` ; table EGLC/ELAC, pire canal, espèce + graphe + table ; limites dédoublonnées en trois groupes (Energy, Fit, Data provenance) ; reçu, objectif, unités et périmètre dans l'inspecteur ;
  - résumés à 4 chiffres significatifs, valeur complète en `title` ;
  - puces de parcours supprimées.
- `apps/web/components/features/ParameterCalibration.tsx` :
  - contrôle segmenté « Your data | Reference | Legacy » ; vue par défaut : « Your data » s'il y a un upload, sinon « Reference » ;
  - anciens `?subsection=` et `#id` (y compris alias historiques) ouvrent la vue correspondante ;
  - l'écran legacy passe de `<details>` à un panneau de vue, contenu, paramètres et payloads intacts, avec bandeau « Legacy path… ».
- `apps/web/components/platform/WorkspaceFeatureSurface.tsx` : plus de liens de saut sur Data Upload et Calibration.
- `apps/web/app/research.css` : `.research-workspace [hidden] { display: none !important }` (les panneaux masqués portent des classes d'affichage).
- Tests et scénarios alignés : `apps/web/lib/calibration-journey.test.mjs` (un test), `apps/web/e2e/research-workspace.scenarios.mjs`, `apps/web/e2e/calibration-monitoring.scenarios.mjs`.

## Comportements à vérifier par Codex

- `npx tsc --noEmit` : typage de `SegmentedControl` générique avec le tuple `CALIBRATION_VIEWS`, prop `view`, `useSearchParams` dans `ParameterCalibration`.
- Les trois panneaux restent montés (attribut `hidden`) : l'état legacy et le chargement de la référence survivent au changement de vue.
- `DRAFT_MISSING_FIELDS` est toujours exporté par `calibration-journey.mjs` (fichier modifié par Codex depuis ma version, non relu).
- Scénarios : onglets au clavier (flèche gauche depuis Legacy → Reference), absence de tout contrôle d'activation ou de lancement contractuel, trois réponses « Not checked » avant preflight.
- 320 / 390 / 1440 px sans débordement ; inspecteur en feuille basse sous 1024 px.

## Écarts et limites

- Boutons primaires encore rouges (composant `Button` partagé avec Home/Monitoring) : non traité, à décider (variante locale ou surcharge CSS limitée à Research).
- Data Upload : les alias `?subsection=` ne défilent plus vers une section (la barre a été retirée de cette page).
- Le preflight se lance toujours depuis Calibration ; Data Upload y renvoie.
- Les champs de métadonnées (unités, compartiments, donneur…) ne sont pas saisissables : emplacement prêt, câblage au contrat reporté.

## Retour arrière

Tranche indépendante de la tranche 1 pour le contenu, mais elle utilise ses composants (`StatusLine`, `SegmentedControl`, `WithInspector`) et ses tokens.
