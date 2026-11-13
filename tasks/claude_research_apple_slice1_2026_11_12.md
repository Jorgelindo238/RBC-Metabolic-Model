# Research « Apple » : tranche 1 (socle), livraison pour revue

Date 2026-11-12. Défauts de la proposition approuvés par l'utilisateur. Outils fichiers seulement : rien exécuté (ni TypeScript, ni tests, ni serveur, ni navigateur). L'UI n'est pas validée.

## Fichiers

- `apps/web/app/research.css` (modifié) :
  - tokens `--r-*` (surfaces, textes, accent bleu, états, espacements, largeurs) sur `.research-workspace` ;
  - largeur de contenu maximale 1080 px (sauf Pathway Map, pleine largeur) ;
  - anneau de focus visible bleu ; chiffres tabulaires dans tables et `dd` ;
  - liens (« Change source », liens de section) en bleu au lieu du rouge ;
  - nouvelles classes `.r-status`, `.r-segmented`, `.r-toolbar`, `.r-with-inspector`, `.r-inspector`.
- `apps/web/components/platform/ResearchSectionNav.tsx` (modifié) : plus d'`aria-current` ; la barre est stylée en liens de saut « On this page », sans onglet « actif ».
- Nouveaux composants, pas encore utilisés par les pages :
  - `components/platform/research/StatusLine.tsx` (+ `answerTone`) ;
  - `components/platform/research/SegmentedControl.tsx` (tablist, flèches/Home/End) ;
  - `components/platform/research/Inspector.tsx` (`WithInspector`, Échap ferme).

## Écart assumé par rapport à la proposition

La barre d'ancres n'est pas supprimée dans cette tranche. `e2e/research-workspace.scenarios.mjs` s'appuie dessus (`navigation "Page sections"`, hash, ouverture de `#legacy-calibration`). Elle disparaîtra page par page quand les vraies vues segmentées arriveront (tranches 2 et 3), avec mise à jour des scénarios. En attendant, elle ne prétend plus être des onglets.

## Non fait dans cette tranche

- Boutons primaires encore rouges : ils viennent du composant `Button` partagé ; le changement se fera page par page en tranche 2, sans toucher Home/Monitoring.
- Bouton « Activate », puces de parcours, sections vides, Overview : tranches 2 et 3.

## À vérifier par Codex

- `npx tsc --noEmit` dans `apps/web` ; scénarios Research et Calibration/Monitoring existants.
- 320 / 390 / 1440 px : pas de débordement, en particulier Flux (« 3.82e+3 ») avec la largeur maximale.
- Le lanceur de chat et l'en-tête ne sont pas affectés par `.research-workspace > *`.

## Retour arrière

Un seul commit à annuler : les trois nouveaux composants ne sont importés nulle part.
