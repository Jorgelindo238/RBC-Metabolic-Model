# Revue AIRBC / Flux Learning Analysis

Date locale : 2026-09-08. Statut : revue et corrections logicielles, aucune promotion cinetique.

Les trois agents demandes (Raman : ODE ; Dewey : donnees/FLA ; Poincare : validation/plateforme) ont ete bloques par la limite d'usage avant de fournir un rapport. Aucun resultat ne leur est attribue. La revue ci-dessous a ete effectuee localement par l'agent principal. Aucun agent supplementaire n'a ete cree.

## Constats classes par priorite

### P1 : deux reactions manquaient dans la matrice FLA, corrige

Le parseur acceptait `V[A-Za-z]...` dans les bilans et ignorait `V6PGD` et `V23DPGP`. Leur extraction de parametres fonctionnait deja, ce qui permettait aux anciens tests de passer sans verifier leurs coefficients stoechiometriques. Consequences : balances GO6P/RU5P/NADP/NADPH et P3G/B23PG incompletes, portee automatique des parametres et problemes inverses potentiellement faux.

Correction : accepter les noms alphanumeriques apres V dans les trois expressions regulieres concernees. Ajout de tests des coefficients, de la connectivite et de tous les 113 bilans de concentration. La matrice contient maintenant 100 reactions a coefficients non nuls, contre 98 immediatement avant correction. Le schema stoechiometrique passe a la revision 2 ; les equations et les constantes de l'ODE ne changent pas.

Verification executable : huit vecteurs positifs distincts, graine 20260908, donnent un ecart maximal `7.1054e-15 mM/j` entre S v et le RHS. Cela teste la coherence d'implementation, pas la conservation elementaire ni la validite biologique. Les anciens teachers/rangs derives de la matrice doivent etre reconstruits ; les bilans manuels deja verifies dans des scripts specialises ne sont pas automatiquement invalides.

Code : [parseur](C:/Users/Jorgelindo/Desktop/airbc/src/rbc_stoichiometry.py:175), [regressions](C:/Users/Jorgelindo/Desktop/airbc/qa/test_fla_review_regressions.py).

### P1 : les corrections numeriques peuvent masquer un defaut de conservation, ouvert

Le RHS remplace les concentrations par au moins `1e-6 mM`, puis amortit separement chaque derivee consommatrice sous `1e-3 mM`. Ce n'est pas une limitation commune du flux de reaction : deux pools participant a une meme reaction peuvent recevoir des corrections differentes.

Un test isole d'AK inverse, ATP=ADP=0, montre un defaut du bilan brut ATP de `7.2670e-7 mM/j`, alors que la reconstruction incluant l'amortissement est exacte. Sur le replay archive `VAMPD1_storage_decay`, le bilan brut ATP+ADP+AMP presente un maximum de `0.0073571 mM/j` et une integrale signee d'environ `+0.0109917 mM` sur J1-J46. L'integrale est une quadrature sur les echantillons enregistres, pas une estimation a tolerances resserrees.

Ne pas attribuer tout l'echec ATP a cet artefact. Il est cependant incorrect de traiter le terme numerique comme un flux biochimique mesure ou d'enlever son effet du seul test de conservation. Le nouveau contrat demande a la fois le bilan brut et la reconstruction effective. Le RHS n'a pas ete modifie ici : un changement de positivite exige un mode reversible et un test conjoint des invariants, de la rigidite et des trajectoires.

Code : [plancher et amortissement](C:/Users/Jorgelindo/Desktop/airbc/src/equadiff_brodbar.py:1905).

### P1 : validation trop permissive, corrigee mais integration incomplete

La validation cumulative pouvait accepter une forte amelioration relative d'un modele restant tres mauvais en ATP. Elle acceptait egalement une valeur negative d'erreur, un indicateur de validation externe vrai sans jeu externe identifie, et des preuves de positivite provenant de trajectoires deja tronquees.

Corrections du contrat, revision 3 :

- Minimum brut avant clipping et bilan brut sans terme de reparation numerique obligatoires.
- Replay continu sans resets ni forcage obligatoire.
- Limites absolues de nRMSE predeclarees pour EGLC, ELAC, LAC, ATP, ADP, AMP, B23PG, en plus des garde-fous relatifs.
- Limites absolues volontairement non renseignees tant que le contrat de mesure n'est pas fige : une information absente ne donne pas un feu vert.
- Identifiants d'ensembles non vides lorsque la validation correspondante est revendiquee ; absence de chevauchement entre les trois listes.
- Valeurs non physiques d'erreur et indicateurs non booleens non acceptes comme preuves positives.
- Donnees/provenance et compatibilite independante ne sont plus declarees vraies par constante dans les deux ecrans purines recents.

Les identifiants ne prouvent pas a eux seuls l'absence de fuite : le decoupage des lignes, le pretraitement, les echelles et les hashes doivent etre audites. Tous les anciens runners n'utilisent pas encore ce contrat. Aucun resultat historique n'est requalifie comme valide.

Code : [validation](C:/Users/Jorgelindo/Desktop/airbc/src/fla_validation_v2.py), [replay et minimum brut](C:/Users/Jorgelindo/Desktop/airbc/scripts/profile_glycolysis_flux_bottlenecks.py:316).

### P1 : l'ATP reste incompatible avec une prediction globale, ouvert

Le candidat de decroissance VAMPD1 tombe sous `0.01 mM` vers J2.1 et termine a `2.7094e-5 mM`, contre `0.46976 mM` dans la table. La bonne fermeture des equations ne valide pas ce comportement. La passe VADSS/km_GTP specifique ameliore fortement un replay a etats fixes mais pas la simulation libre ; ses cinq candidats restent rejetes.

Le contre-factuel NDPK remplace ATP **et ADP**, pas ATP seul. Il suggere un couplage energetique, sans demontrer que NDPK est compensatoire ou qu'un nouveau modele energetique echouerait. Les groupes dits production/consommation ATP contiennent les flux nets reversibles VAK et VNDPK : le signe d'un groupe n'est donc pas un test d'irreversibilite. Ces deux interpretations sont corrigees dans les runners et dans de nouveaux rapports, sans ecraser les anciens.

Sources : [audit ATP revise](C:/Users/Jorgelindo/Desktop/airbc/output/fla_review_2026_09_08/atp_sustainability/summary.json), [audit NDPK revise](C:/Users/Jorgelindo/Desktop/airbc/output/fla_review_2026_09_08/gtp_ndpk/summary.json).

### P2 : les resets ne constituent pas encore du multiple shooting calibre, corrige

Le diagnostic reinitialise 52 etats observes sur 13 intervalles, en transportant les etats latents. Aucun noeud ni parametre n'est optimise. La discontinuite est seulement rapportee, avec une perte moyenne `28.5912`, et n'etait pas penalisee dans un objectif malgre le champ JSON qui l'affirmait.

La fraction d'echantillons au-dessus du seuil ATP etait nommee fraction de temps, bien que les intervalles aient des durees differentes. Recalcul en duree, avec franchissements lineaires a l'interieur de chaque segment et aucun pont entre les resets : `2.36565%` en simulation libre contre `26.52987%` avec resets. Cela ne mesure ni le rang des sensibilites ni une performance predictive hors echantillon. Le gain d'erreur locale ne justifie plus une adoption automatique.

Code : [duree au-dessus du seuil](C:/Users/Jorgelindo/Desktop/airbc/src/fla_multiple_shooting.py), [diagnostic corrige](C:/Users/Jorgelindo/Desktop/airbc/scripts/diagnose_brodbar_multiple_shooting.py).

### P2 : export et calcul des teachers pouvaient consommer des sorties invalides, corrige

L'export CSV remplacait les echantillons de flux manquants par zero et pouvait ecrire des lignes de concentration trop courtes. Il valide maintenant dimensions, unicite, ordre temporel des trajectoires et valeurs finies avant toute creation de CSV. Les flux signes sont conserves. Les teachers integres rejettent les concentrations/flux non finis, ainsi que les echelles et tolerances invalides.

Les temps du tracker de solveur peuvent inclure des essais rejetes et etre non monotones. L'export preserve ces journaux ; ils ne constituent pas un maillage de quadrature. La validation scientifique doit utiliser un replay sur les etats acceptes, comme le helper FLA.

Code : [export](C:/Users/Jorgelindo/Desktop/airbc/apps/api/services/pure_ode_runtime.py), [teachers integres](C:/Users/Jorgelindo/Desktop/airbc/src/fla_integrated_flux.py).

### P2 : provenance et plateforme, ouverts

- La table locale Bordbar/Brodbar contient 55 lignes et 14 temps J1-J46, mais les metadonnees sources et les transformations ne sont pas toutes etablies. Un endpoint tabule n'est pas automatiquement un endpoint experimental primaire.
- B13PG/B23PG et P2G/P3G sont des doublons exacts ; ne pas les compter comme observations independantes. Les initiaux PPP latents ne deviennent pas mesures parce qu'ils sont contraints.
- Bardyn : 98 lignes par condition, mais seulement 40 controle et 37 supplementees retenues apres quarantaine conservatrice des lignes constantes a 1.0. Michel : 28. Cette regle doit etre remplacee par une provenance explicite. Aucune validation externe n'est declaree acquise.
- L'API limite `base_params` a des nombres ; elle ne transporte pas correctement les choix de famille cinetique sous forme de chaines. Le chemin de simulation standard utilise un debut J1 alors que Michel/Bardyn commencent J2. La parite API/runner n'est pas demontree.
- Le scope automatique est volontairement non-hybride et n'inspecte pas toutes les dependances des helpers. Il ne certifie donc pas l'identifiabilite des options de transport ou de decroissance VAMPD1.
- Les dependances declarees imposent NumPy <2, alors que plusieurs scripts historiques utilisent `np.trapezoid`. Les modules de quadrature touches ici utilisent SciPy, mais la compatibilite de l'ensemble doit encore etre testee sous l'environnement declare. Le runtime local Python 3.14 emet un avertissement Pydantic v1.

## Strategie retenue

FLA reste pertinent comme approche d'inference contrainte par les bilans, mais pas comme une succession de regressions contre un teacher suppose exact. Un teacher intracellulaire depend souvent des autres flux du modele ; les memes donnees de concentration ne constituent pas deux sources independantes quand elles supervisent a la fois concentration et derivee.

1. Reconstruire les matrices, les rangs et les teachers PPP/Rapoport-Luebering avec le schema 2 ; conserver les jeux de parametres et les options de reference inchanges.
2. Sur des replays acceptes standard et stricts, mesurer la contribution des planchers/amortissements a ATP, ADP, AMP, G6P, NADP/NADPH et GTP. Tester ensuite un mode de positivite conservant les reactions, reversible et desactive par defaut. Ne pas ajouter une source ATP artificielle pour compenser un plancher.
3. Figer le contrat de mesure, les seuils absolus justifies et les blocs train/holdout avant tout nouveau fit. L'incertitude non renseignee doit rester explicite, avec analyse de sensibilite aux poids.
4. Comparer des sensibilites dynamiques a horizon court avec et sans ancrage des observations. Si le rang et les profils le permettent, optimiser un petit bloc energetique conjoint avec continuite explicite et etats latents contraints. Les purines restent figees pour cette etape.
5. Tester sans reinitialisation la trajectoire continue J1-J46, puis les jeux externes demarrant a leur vrai temps initial. Les gains de warm-start ML ne sont utiles que s'ils accelerent ce probleme valide, avec un budget identique au temoin.

## Verification et reproductibilite

- `python scripts/review_fla_evidence.py` : inventaire courant, huit audits positifs, deux cas de depletion, fraction de temps corrigee et bilan adenylate archive. Fichier [evidence.json](C:/Users/Jorgelindo/Desktop/airbc/output/fla_review_2026_09_08/evidence.json), avec hashes des sources consommees.
- `python -m pytest -q qa` : 512 tests passes, six avertissements Optuna existants. Verification finale archivee dans `output/fla_review_2026_09_08/qa_results.xml` ; avertissement de demarrage Pydantic v1/Python 3.14 egalement observe.
- Aucun nouvel ajustement cinetique, aucune reecriture des resultats historiques, aucune promotion et aucune validation externe executee dans cette passe.
- La revue couvre la chaine scientifique et les points critiques du replay/API. Elle ne constitue pas un audit de securite, un benchmark exhaustif, ni une certification de toutes les branches optionnelles de la plateforme.
