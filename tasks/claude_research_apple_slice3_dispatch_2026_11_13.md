# Claude: Research tranche 3, execution autonome

Date: 2026-11-13 (America/Toronto).
Workspace: `C:/Users/Jorgelindo/Desktop/airbc`, branche actuelle `dev/next-phase`.

## Mandat utilisateur

Implementer maintenant, dans cet ordre, les quatre pages restantes demandees:
**Simulation, Flux Analysis, Pathway Map, Results**. Lire le code actuel, puis
modifier effectivement les pages; ne pas livrer une nouvelle proposition seule.
Enchainer les quatre features sans demander d'autorisation entre chacune.
Les decisions locales de presentation et les corrections de regression dans ce
perimetre sont autorisees. Ne s'arreter que pour un blocage reel, une action
hors perimetre ou une limite d'acces/outils; documenter le blocage precis.

Ce mandat remplace la restriction "proposition seulement" du brief initial.
Il n'autorise ni changement scientifique ni changement d'infrastructure.
Overview et la saisie des metadonnees restent hors de cette livraison.

## Point de depart a conserver

Lire `tasks/claude_research_apple_proposal_2026_11_12.md`, les livraisons
`claude_research_apple_slice1_2026_11_12.md` et
`claude_research_apple_slice2_2026_11_12.md`, puis relire les fichiers actuels.
Le worktree contient deja les tranches 1 et 2 ET les correctifs Codex: ne rien
ecraser, ne pas restaurer une ancienne version de tes composants.

Codex a valide localement TypeScript, 42 tests Node, 27 controles Research sur
320/390/1440 px et 6 scenarios Calibration/Monitoring avec les services reels.
Ces resultats concernent le code AVANT tes changements de tranche 3; ils ne
valideront pas automatiquement ta nouvelle livraison. Pas de build production
ni de deploiement verifies. Les modifications ne sont pas commitees.

Correctifs presents a preserver:
- `SegmentedControl`: chaque option porte son `panelId`; associations
  `aria-controls` / `aria-labelledby`, navigation fleches/Home/End.
- Calibration: ecoute `hashchange` et aliases historiques `?subsection=`.
- `WithInspector`: focus a l'ouverture; fermeture bouton/Echap puis retour
  au declencheur; `aria-expanded` et `aria-controls` corrects.
- Dans l'inspecteur, les lignes `research-review` affichent la valeur sous
  son libelle: ne pas remettre une colonne de valeurs illisible de 60 px.
- La reference n'a AUCUN bouton Activate; le lancement contractuel n'a AUCUN
  controle utilisable tant que le moteur n'est pas qualifie.

## Direction commune

Outil scientifique inspire de la discipline Apple, pas site marketing:
hierarchie nette, peu de chrome, controles familiers, donnees au premier plan.
Reutiliser les tokens `--r-*` et les composants existants dans
`apps/web/components/platform/research/`; aucune nouvelle dependance.
Un seul h1, pas de heros, pas de cartes imbriquees, pas de compteurs factices,
pas de puces de statut ressemblant a des boutons. Anglais coherent dans l'UI;
compte rendu en francais. Icones Lucide et infobulles/noms accessibles.
Espacements et tailles stables; aucune typographie liee au viewport ni
interlettrage negatif. Limiter les styles a Research, sans toucher Home ou
Monitoring. Les boutons primaires des quatre pages peuvent utiliser un style
bleu local Research; ne pas modifier la variante globale Button.

## 1. Simulation

Route: `/research/simulation`.
Fichier principal: `apps/web/components/features/SimulationWorkspace.tsx`.

- Reglages a gauche (environ 320 px), resultat a droite lorsque l'espace est
  suffisant; une colonne sur petit ecran, sans comprimer le graphe.
- Garder tous les controles actuels, leurs valeurs, validations et payloads.
  Une action principale Run simulation; controles techniques en divulgation
  progressive si utile, sans retirer une capacite existante.
- Conserver empty/loading/error/resultats reels. Erreur: garder les reglages;
  progression indeterminee sauf vraie information de progression disponible.
- Mettre source des parametres, details et provenance dans l'inspecteur.
  Ne pas presenter un upload actif comme effectivement applique a l'ODE si
  ce n'est pas vrai; distinguer contexte dataset et entree du moteur.
- Retirer la barre d'ancres de cette page uniquement apres avoir migre les
  anciens liens et adapte les scenarios; conserver les URL publiques.
- Ne lancer aucune simulation ODE pour produire de jolies captures.

## 2. Flux Analysis

Route: `/research/flux-analysis`.
Fichier principal: `apps/web/components/features/FluxAnalysis.tsx`.

- Barre compacte: voie, Re-estimate, etat textuel. Conserver estimation,
  filtrage, signes, unites et gestion d'erreur existants.
- Ligne de synthese utile, puis donnees et graphe lisible; le readout verbeux
  devient une legende concise, pas une nouvelle carte decorative.
- Provenance et limites dans l'inspecteur partage. Identifier la nature des
  flux (estimes/rejoues/simules selon la vraie source), pas de validation
  biologique implicite ni de transformation numerique pour l'affichage.
- Garantir que les valeurs comme `3.82e+3` et les etiquettes ne sont pas
  coupees a 320, 390 et 1440 px. Adapter la hauteur/les marges du graphe au
  nombre de reactions au lieu de reduire les etiquettes jusqu'a l'illisible.
- Retirer les separateurs vides et les doublons de provenance/navigation.

## 3. Pathway Map

Route: `/research/pathway-visualization`.
Fichiers: `PathwayVisualization.tsx` et `features/pathway/NetworkGraph.tsx`.

- Graphe principal non enferme dans une carte decorative; garder l'exception
  pleine largeur et le mode compact par defaut.
- Barre unique de modes Compact / Full et commandes pertinentes; commandes
  lecture/restart uniquement si une trajectoire reelle est disponible.
- Zoom, reset, selection et fermeture de l'inspecteur doivent fonctionner au
  clavier/souris. Selection -> inspecteur commun, sans duplication des details.
- Lisibilite des etiquettes par ajustements visuels seulement: aucun changement
  d'identifiants, de topologie, de donnees ni de projection scientifique.
  Ne pas inventer une nouvelle disposition de reseau dans cette livraison.
- Indiquer clairement qu'un reseau statique n'est pas une trajectoire et que
  connecteurs/bridges du compact sont display-only, pas des reactions cinetiques.
- Ajouter/conserver un etat explicite si aucun noeud n'est disponible; ne pas
  confondre chargement, erreur et graphe vide. Verifier les deux modes non vides.
- Aucune modification du backend pathway_registry, de l'ODE ni de RBC-GEM.

## 4. Results

Route: `/research/calibration-registry`.
Surface actuelle: `RegistrySurface` dans
`apps/web/components/platform/WorkspaceFeatureContent.tsx`.

- Registre reel vide: une phrase No calibration runs recorded yet et lien
  Calibration. Pas de compteurs inutiles, filtres, tableaux/sections vides.
- Registre indisponible: erreur explicite avec reprise appropriee; ne pas le
  presenter comme un registre vide ou zero runs.
- Registre peuple: table compacte avec statuts/verdicts/scores reels et filtres
  utiles; ligne selectionnee -> inspecteur d'evidence et provenance existantes.
- Garder accessible toute fonction existante et les liens vers les preuves.
  Completed n'est ni validated ni activated: conserver la qualification
  unverified si applicable et ne pas inventer de pourcentage de progression.
- Ne pas injecter de runs/donneurs/poches/valeurs dans Supabase pour le design.
  Des fixtures de test explicitement isolees sont possibles, jamais en production.

## Invariants et limites strictes

- Aucun changement a `src/`, `RBC/`, constantes, Km/Vmax, J1, matrices,
  volumes, solveurs, objectifs, contrats ou autorisations d'activation.
- Aucune calibration, campagne scientifique, integration ODE, promotion d'un
  profil, reecriture des archives scellees ou changement des donnees source.
- Garder les appels et payloads existants, la precision stockee et la verite des
  donnees. Un resume arrondi doit donner acces a la valeur complete.
- Pas de conversion relative -> mM ni de donneur/volume/J1 emprunte en silence.
- Aucun secret, .env, schema/migration Supabase, auth, Vercel, configuration
  d'infrastructure ou modification globale Home/Monitoring.
- Pas de nouvelle dependance, skill/plugin, sous-agent, commit, push ou deploy.
  Utiliser les skills UI/React/accessibilite existants seulement s'ils sont
  disponibles; ne pas inventer leur execution.

## Execution et tests

Tu es autorise a modifier le frontend et les tests correspondants et a executer
les validations locales non scientifiques si tes outils le permettent. Ne
redemande pas l'autorisation avant chaque page ou chaque validation courante.
Si tu n'as que des outils fichiers, implementer les quatre pages quand meme,
puis signaler exactement les tests non executes pour reprise par Codex.

Reutiliser le serveur `http://127.0.0.1:3100` s'il fonctionne. Ne pas lancer un
second serveur sur le meme port ni interrompre un processus non identifie.
Le seul chargement/filtrage des flux existant est permis; pas d'appel de
lancement simulation/calibration pendant les tests de navigation.

Commandes de reference (depuis la racine):

```text
node apps/web/node_modules/typescript/bin/tsc --project apps/web/tsconfig.json --noEmit --incremental false
node --test --test-reporter=dot apps/web/lib/server-run-access.test.mjs apps/web/lib/calibration-journey.test.mjs apps/web/lib/calibration-lifecycle.test.mjs
node apps/web/e2e/research-workspace.scenarios.mjs
```

Calibration/Monitoring: executer `apps/web/e2e/calibration-monitoring.scenarios.mjs`
avec `BASE_URL=http://127.0.0.1:3100` et `REQUIRE_LIVE_REGISTRY=1` dans
l'environnement du processus. Ces variables ne sont pas des commandes shell.

- Adapter les scenarios aux changements de structure sans affaiblir les
  invariants: absence de lancement/activation, donnees exactes, erreurs visibles.
- Garder les controles clavier Home/End/fleches, anciens liens Calibration,
  import CSV reel et retour a la reference des scenarios existants.
- Couvrir 320/390/1440 px, etats charges et inspecteur ouvert: zero debordement
  horizontal de page, tableaux eventuellement scrollables a l'interieur.
- Verifier graphes non vides Compact ET Full, selection, zoom/reset, focus et
  fermeture Echap avec retour au declencheur. Ne pas declencher Run simulation.
- Les captures Playwright restent hors Git dans
  `C:/WINDOWS/TEMP/airbc-research-redesign/`; `caret: 'initial'` evite un faux
  mismatch d'hydratation sur le champ fichier. Ne pas masquer les erreurs.
- Test fixtures necessaires aux etats resultat/erreur: isolees et declarees
  comme fixtures, jamais presentees comme sorties biologiques validees.

## Livraison unique apres les quatre pages

Ecrire `tasks/claude_research_apple_slice3_2026_11_13.md` avec fichiers touches,
fonctions preservees/deplacees, tests executes et resultats exacts, etats
inspectes au navigateur vs code seul, limites et points restant a verifier.
Donner un recapitulatif des QUATRE pages et des criteres d'acceptation, pas une
demande d'autorisation pour passer a la suivante. Si une page est bloquee,
expliquer le blocage et terminer les autres pages independantes avant de rendre.
