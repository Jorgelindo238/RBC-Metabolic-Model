# RBC-GEM : audit du reseau AIRBC et corrections reversibles

Revue et execution le 2026-10-06. Demande : exploiter RBC-GEM et ses supplements pour identifier/corriger des reactions manquantes dans `RBC/Rxn_RBC.txt` et l'ODE. Aucun code du depot externe ni HTML fourni n'a ete execute. Aucun optimiseur, nouveau teacher experimental ou ajustement d'IC n'est lance.

## Supplements et versions recuperes

Il n'est pas necessaire de fournir davantage de fichiers pour ce premier audit structurel : les sources prioritaires ont ete recuperees directement.

| Ressource | Usage realise | Limite |
| --- | --- | --- |
| S1, `pcbi.1012109.s003.xml` | SBML original archive; comparaison effectuee sur le JSON GitHub epingle | Le SBML ne contient pas nos lois cinetiques |
| S2, `pcbi.1012109.s004.xlsx` | Inventaire des feuilles; tables de curation/genes/reactions correspondantes exploitees depuis GitHub | Presence, absence, evidence et notes de curation ne prouvent pas une activite a 4 C |
| S5, `pcbi.1012109.s007.xlsx` | Inventaire des tables de connectivite | Les versions simplifiees retirent des couplages energetiques/redox; elles ne remplacent pas S |
| S6, `pcbi.1012109.s008.xlsx` | Extraction exacte des enzymes prioritaires et metadonnees longitudinales | Abondances estimees, pas concentrations actives directement mesurees |
| S7, `pcbi.1012109.s009.xml` | Modele proteome-contraint representatif archive | Entites proteine/complexe, pseudoreactions et keff ne sont pas des metabolites/flux experimentaux de notre ODE |

S3 est un resume MEMOTE et S4 une carte : utiles pour presentation/QA, mais non necessaires pour decider des coefficients ci-dessous. Les tables de complexe et les references sont deja disponibles dans les fichiers GitHub recuperes. Le fichier image de workflow recupere avec l'index des supplements n'est pas utilise dans l'analyse.

[Depot RBC-GEM](https://github.com/z-haiman/RBC-GEM), [article](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012109), [index Figshare](https://api.figshare.com/v2/articles?resource_doi=10.1371/journal.pcbi.1012109&page_size=100).

- Version publiee 1.2.0 : commit `5347d80275be01e410aa9787b0aac99497a8ed57`.
- Version actuelle 1.3.0 : commit `43fd381d9eb8a8a4079629012362312960e1c009`.
- Les JSON contiennent respectivement 3275/3290 reactions, 2157 metabolites et 820 genes, en comptant aussi les reactions de bord. Ce n'est pas le decompte de reactions biochimiques du texte de l'article.
- Difference observee : 16 sinks lipidiques ajoutes, un ancien exchange retire et deux GPR modifies; aucune stoechiometrie modifiee parmi les identifiants communs. La correction des complexes annoncee dans HISTORY exige de verifier les tables de complexes, pas seulement les JSON metaboliques.
- 33 ressources recuperees, empreintes SHA256 conservees; blobs Git verifies contre les arbres epingles et supplements verifies avec leurs MD5 Figshare.

## Comparaison exhaustive du noyau execute

Le comparateur lit les 100 reactions de `src/rbc_stoichiometry.py`, donc les bilans executes de `equadiff_brodbar.py`, pas seulement le fichier texte. Il preserve les compartiments et ne retire que H2O, H+, Pi, PPi et CO2 explicitement declares comme monnaies omises. Il ne masque jamais un autre metabolite absent pour obtenir artificiellement une correspondance.

Resultat final, `comparison_v2/network_comparison.json` :

- 107 des 113 pools ont une correspondance explicite de metabolite; les pools generiques/ambigus restent non associes.
- 82 reactions ont au moins une equivalence stoechiometrique projetee, au signe/echelle pres. Ce n'est ni une validation atomique complete, ni une equivalence cinetique.
- 13 reactions n'ont pas de correspondance a une reaction unique; des reactions regroupees peuvent exiger plusieurs etapes (PHGDH/PSAT/PSPH, GMP nucleotidase/PNP).
- 5 reactions impliquent des identites de pool non resolues, notamment les folates et methylations.
- 47 reactions RBC-GEM non appariees utilisent uniquement des pools presents, hors monnaies omises et reactions de bord. Ce sont des candidats a curer, pas 47 ajouts automatiquement justifies.

La premiere extraction, conservee a la racine de l'archive, avait trois alias incomplets pour SAM, cysteinylglycine et gamma-glutamylcysteine. Elle est remplacee pour interpretation par `comparison_v2/`; aucun metabolite source n'a ete renomme ou supprime.

## Modifications effectivement realisees

### Catalogue et parseur

`RBC/Rxn_RBC.txt` est maintenant une **projection explicite du reseau historique execute**, avec 100 reactions et 113 pools declares. Onze equations absentes sont ajoutees, dont GPX, AMP nucleotidase optionnelle, ASN et les transports/degradations extracellulaires. SAM ne produit plus d'AMP dans le catalogue; l'orientation VEGLC correspond a l'import utilise par l'ODE. Les declarations et fleches sont coherentes entre elles.

CYT reste un chemostat historique : ses termes consommateurs sont volontairement absents du bilan execute. Les lignes du catalogue l'indiquent, notamment le transfert VECYT qui a une source tamponnee implicite. **Cette parite n'est pas une preuve de conservation physique** : convertir CYT en pool ferme et clarifier le substrat de methylation restent necessaires avant une extension biologique. Les simplifications VCSE/METTHF/OPLAH sont signalees dans l'en-tete, pas presentees comme resolues.

`src/parse.py` est corrige pour lire des coefficients apres un '+', reconnaitre les reactions purement extracellulaires/source/sink en mode strict, et sommer les occurrences d'un meme metabolite au lieu d'ecraser son coefficient. Les termes malformes sont refuses. Le parseur historique et le comparateur independant reconstruisent tous deux les 100 colonnes de l'ODE apres synchronisation.

L'ancien fichier texte et les sources numeriques initiales sont preserves dans `original_local_sources/`. Le noyau historique `src/equadiff_brodbar.py`, son parseur structural `src/rbc_stoichiometry.py`, le limiteur et les donnees Bordbar restent identiques par empreinte.

### Variante ODE explicite, sans migration silencieuse

Nouveau module `src/rbc_gem_network.py`, version `airbc-rbc-gem-diagnostic-2026.10.06-v1` :

| Mode | Modifications | Interpretation |
| --- | --- | --- |
| `historical` | Appel identique au noyau existant | Retour arriere; profils legacy et reaction_consistent conserves |
| `redox_stoichiometry` | Catalase : 1 H2O2 -> 0.5 O2; les deux oxydations hypoxanthine/xanthine consomment chacune 1 O2 et produisent 1 H2O2 | Corrections des coefficients, pas validation du mecanisme ou de l'activite XAO |
| `rbc_gem_core` | Corrections redox; VOPLAH execute a zero; exports GSSG et urate couples a 1 ATP -> 1 ADP par evenement | Hypothese source-specifique a tester, pas nouvelle reference globale |

Pour XAO, les noms locaux et RBC-GEM sont inverses : `VXAO` correspond a `XAO2` du GEM, `VXAO2` a `XAO`. Le choix est fait sur l'equation, jamais sur le nom seul. Les reactions XAO n'ont pas de GPR dans RBC-GEM; une reaction annotee ne demontre pas son activite enzymatique intrinseque dans nos RBC.

Les facteurs de positivite sont recalcules sur **la matrice modifiee**, avec un facteur commun pour tous les termes d'une reaction. Ainsi, un export ABC ne peut pas continuer sans ATP puis etre corrige separement sur le bilan ATP. Les trackers recoivent les flux executes de cette matrice. Les termes pH actuellement utilises ne dependent que de reactions dont les facteurs restent inchanges a etat fixe dans ces hypotheses.

L'O2 reste le pool simplifie existant : pas de liaison Hb, transport, oxygenation de poche ou apport externe nouveau. Le limiter a 1e-3 mM est numerique, pas un Km d'oxygene. Aucun succes numerique ne valide cette representation physiologique.

### Cinq branches manquantes implementables, inactives par defaut

Le module fournit des colonnes et lois MM explicitement optionnelles, avec `vmax` et chaque `km_<substrat>` obligatoires si la branche est ouverte. Aucun chiffre cinetique n'est invente pour un usage biologique.

| Branche locale | Source RBC-GEM | Pools projetes | Risque a controler |
| --- | --- | --- | --- |
| VARGN | ARGN / ARG1 | ARG -> ORN + UREA | Presence/activite, conditions et origine des signaux ORN/UREA |
| VXPPT | XPPT / HPRT1 | XAN + PRPP -> XMP | Capacite partagee avec HGPRT; pas trois reservoirs HPRT1 independants |
| VACYP | ACYP / ACYP1/2 | B13PG -> P3G | Derivation sans ATP; partager correctement le drainage B13PG et ne pas corriger artificiellement ATP |
| VGMPR | GMPR / GMPR/GMPR2 | GMP + NADPH -> IMP + NADP + NH4 | Couplage purines-redox, isoformes et disponibilite NADPH |
| VGSR_NADH | GTHOx / GSR | GSSG + NADH -> 2 GSH + NAD | Activite secondaire, partage du budget GSR avec la reduction NADPH |

Ces cinq branches sont presentes dans la matrice diagnostique mais ont un taux zero sans parametres explicites. Elles ne sont **pas activees dans les huit replays**, ni dans l'API/calibration. Des parametres de test synthetique ne sont pas des priors physiologiques.

Exemple d'activation structurelle sans nouvelles branches :

```python
from rbc_gem_network import equadiff_rbc_gem
rhs = lambda t, x: equadiff_rbc_gem(
    t, x, network_mode="rbc_gem_core", custom_params=frozen_parameters,
    positivity_policy="reaction_consistent", reaction_availability_threshold=1e-3,
)
# Retour arriere : network_mode="historical", ou le noyau equadiff_brodbar existant.
```

## Conclusions biologiques importantes de la curation

1. **OPLAH : contradiction a resoudre, pas suppression promue.** [La table des exclusions RBC-GEM](https://github.com/z-haiman/RBC-GEM/blob/43fd381d9eb8a8a4079629012362312960e1c009/data/curation/reactions_removals.tsv) retire OPAH/OPLAH, en citant PMID24636780 et PMID4150022. Cependant Deep Red2026 contient OPLAH, UniProt O14841, Sheet1 ligne2004, environ1227 copies F /217 copies G par cellule. Le supplement S6 ne la rapporte pas parmi les lignes selectionnees. Detection proteique recente, activite catalytique et flux a 4 C restent des questions differentes; ce conflit impose une mesure d'activite et une borne d'incertitude, pas une affirmation d'absence absolue.
2. **VCSE : erreur d'identite carbone.** Cystathionine C7 -> cysteine C3 + AKG C5 + NH4 cree un carbone. RBC-GEM CYSTL1 produit cysteine et 2-aminobut-2-enoate C4, puis la deamination fournit alpha-ketobutyrate/NH4. Ajouter le vrai pool C4 et son devenir est preferable a remplacer AKG par un produit sans etat suivi. La correction n'est pas encore active; fermer ce bilan exige IC/observations et definition du pool. CYSTS a une note GAPFILLING et pas de GPR dans le GEM : la chaine complete ne doit pas etre consideree prouvee simplement parce qu'elle est dessinee.
3. **Folates : METTHF est ambigu.** SHMT produit 5,10-methylene-THF, pas le 5-methyl-THF consomme par la methionine synthase. Le GEM les distingue; MTR/MTHFR ne sont pas dans son registre de genes et ne sont pas listes dans le tableau Deep Red inspecte. Absence dans une liste n'est pas preuve d'absence biologique, mais il faut separer les pools et justifier les enzymes avant de fermer un cycle consommant NADPH.
4. **Citrate cytosolique : exclusion RBC-strict trop generale.** ACO1/ACONT, IDH1/ICDHy et ACLY/ACITL sont soutenus dans le GEM et detectes dans Deep Red. L'absence de mitochondries ne justifie pas a elle seule leur suppression. ACO+IDH exige un vrai pool isocitrate ou une reduction documentee; ACLY consomme ATP et CoA, et produit OAA et ACCOA. Aucun retour automatique des anciens lumpings ni ajout ATP-source n'est fait.
5. **Maintien energetique : couplages manquants.** Le GEM annote les exports GSSG/urate ABC, Na/K-ATPase, pompe Ca et flippases. Les deux premiers sont testables avec les pools presents; les autres demandent ions/lipides, compartiments et cout energetique documentes. Ils ajoutent une consommation, pas une solution magique au deficit ATP. Export GSH et degradation extracellulaire ont des mecanismes plus incertains : pas d'ATP attribue par analogie.
6. **Redox incomplet :** CYB5R3/cytochrome b5/metHb, BLVRB/FMN et PRDX2/TXN/TXNRD1 sont absents de notre mecanisme explicite mais soutenus par les sources. Il faut ajouter les acceptateurs oxydes/reduits, les cycles et les observations, pas un simple puits NADH/NADPH ajustable. La regeneration/salvage/reparation NAD implique notamment NAMPT/NMNAT/NAXD/NAXE et invaliderait l'hypothese de totaux redox conserves si elle devenait active.
7. **Partition adenylate et cinetique :** ADK3 utilise AMP+GTP -> ADP+GDP via AK1; ADPGK utilise glucose+ADP -> G6P+AMP. Ces branches meritent un examen de l'evidence et des budgets enzymatiques, pas un parametre libre pour chaque reaction. Les reactions reversibles du GEM ne rendent pas automatiquement les lois MM actuelles reversibles ou conformes aux contraintes de Haldane. Les Km ne se deduisent pas des bornes FBA.

Les genes GLUD1, GDA et ASRGL1 sont detectes dans Deep Red2026 mais absents de certaines annotations/series plus anciennes. Leur absence du GEM seul n'autorise donc pas a supprimer VGDH/VGDA/VASNG. Les observations recentes et les assays doivent etre confrontes a la curation historique.

## Proteomique S6 effectivement extraite

`priority_proteomics_v2/` contient les valeurs d'origine et leurs cellules, identifiants UniProt, genes candidats, donneur/jour et unites :

- 62 proteines prioritaires, 616 donneurs, 1848 echantillons aux jours10/23/42.
- Table D : 114576 valeurs en nmol proteine/gDW; Table E : 114576 representations en copies/cellule.
- Aucune valeur manquante dans cet extrait; 6247 zeros rapportes par table, conserves comme zeros, sans epsilon ou logarithme automatique.
- Les Tables D/E ne sont pas deux assays independants. Leurs colonnes ont **163 positions differentes** : jointure par `S*_D*` exclusivement. La tentative initiale a refuse l'egalite positionnelle et reste preservee dans `priority_proteomics/`.
- Deep Red F/G est conserve separement; aucune conversion en mM, choix automatique d'etalonnage, kcat, fraction active ou cout de transport n'est effectue.
- Tableau F des metadonnees et toutes les unites d'origine sont preserves. Les jours10/23/42 ne remplacent pas Bordbar J1. Ces donneurs REDS recoupent Nemkov/PFK2024 : pas de validation externe independante par simple changement d'article.

Verification source independante : reouverture du classeur et comparaison exacte de toutes les229152 valeurs D/E, de leurs coordonnees/identifiants/temps/unites et des17864 cellules de metadonnees F. Tous les controles passent sans tolerance numerique; receipt `source_value_verification.json`, script `scripts/verify_rbc_gem_proteomics_cells.py`. Les manifestes d'extraction anterieurs restent inchanges.

La presence de l'ACYP, ARG1, GMPR, GSR, redox et transporteurs soutient des priors de capacite **souples et source-specifiques**, apres verification de l'activite et des complexes. Les deux sources ne sont pas interchangeables pour fixer des valeurs initiales de metabolites.

## Replays a parametres fixes

Contrat : `config/fla_rbc_gem_structural_diagnostic.json`. Meme vecteur exact des55 observations Bordbar J1, memes59 autres entrees, memes cinetiques archivees et meme seuil1e-3. Seul le cas OPLAH seul met explicitement sa capacite a zero; les autres cas remplacent des termes structurels dans l'adaptateur. J1-J4 libre, sans reset, forcing ou selection de meilleur candidat.

| Hypothese | ATP J4 ultrastrict, mM nominal | ADP J4 | AMP J4 |
| --- | ---: | ---: | ---: |
| Historique | 0.0007510433 | 0.0000804468 | 2.59366510 |
| OPLAH seul desactive | 0.0007724954 | 0.0000845651 | 2.59222840 |
| Coefficients redox seuls | 0.0007510427 | 0.0000804470 | 2.59366510 |
| Variante RBC-GEM core | 0.0007664191 | 0.0000849197 | 2.59227953 |

Nominal Bordbar J4 ATP/ADP/AMP : 1.079765 /1.073256 /0.539208 mM, sous les reserves de normalisation/pools deja documentees. OPLAH-off ameliore ATP d'environ2.86%, core d'environ2.05%; aucune hypothese ne restaure la partition. La variation numerique d'ATP avec les seuls coefficients redox est inferieure a0.001%; aucun test statistique n'est realise. Ces replays ne prouvent pas l'inutilite des modules redox/maintenance dans des conditions/IC correctement caracterisees.

Huit integrations en335.7 secondes. Tous les7632 controles de quadrature/bilan passes; 1423774 comparaisons ponctuelles strict/ultrastrict passees (ce ne sont pas des observations independantes). Minimum parmi les etats acceptes, grilles denses et noeuds Gauss verifies : zero, aucune concentration negative selon la tolerance declaree; fermeture des bilans executes a la precision numerique. Deux historiques reproduisent exactement les tableaux acceptes des anciens replays.

Suite QA : **952 tests passes, 2 ignores**, dont30 nouveaux tests; six avertissements Optuna existants et l'avertissement Python3.14/Pydantic. Les deux ignores concernent les anciens originaux JBC/Nishino absents de Downloads, pas les sources RBC-GEM. Les copies JBC precedemment archivees restent disponibles; un test ignore n'est pas un nouveau controle de ces originaux.

Verification independante :207 controles, empreintes sources, parite catalogue, equivalence des dix colonnes corrigees/ajoutees au GEM, budgets stockes, sept reevaluations ODE par replay et reproduction historique. Aucun fichier source numerique ou ancien manifeste n'est reecrit.

## Decision et prochaine execution

1. Conserver les corrections de catalogue/parseur et l'adaptateur reversible, **sans promouvoir le mode core ni ouvrir tous les nouveaux vmax**. Les gardes de readiness biologiques restent en place.
2. Fermer d'abord les contrats VCSE/C4, folates et CYT/methylation, et caracteriser redox disponible/O2. Confronter OPLAH ancien/nouveau avec une activite pertinente au stockage.
3. Prioriser ensuite l'audit dynamique AK1 et le couplage NADH-GAPDH/metHb, avec capacites partagees et priors proteomiques incertains. Les signaux sources et les teachers restent correles; nouvelles branches augmentent l'ambiguite cinetique sans nouvelles observations.

Les donnees initiales demeurent `src/Data_Bordbar_et_al_exp.xlsx` a J1. Il n'y a pas de remplacement par les conditions XLS, pas d'ajustement silencieux du redox1mM, pas de promotion de parametres ni de nouvelle calibration biologique.

## Fichiers et reproduction

Archive : `output/rbc_gem_network_audit_2026_10_06/`; tables de comparaison finales : `comparison_v2/`; observations : `priority_proteomics_v2/`; replays : `fixed_parameter_diagnostic/`.

`final_manifest.json` scelle les fichiers de cette archive et les vingt sources locales preservees dans `executed_local_sources/`, dont le code effectivement teste et les documents actualises. Il ne remplace aucun manifeste anterieur. Les scripts d'extraction/verifications S6 utilisent le runtime Python fourni avec openpyxl; la simulation et les QA utilisent l'environnement scientifique du depot.

Comparer les sources : `scripts/audit_rbc_gem_network.py`; reconstruire les observations : `scripts/extract_rbc_gem_priority_proteomics.py`; executer le contrat : `scripts/run_rbc_gem_structural_diagnostic.py`; verifier : `python scripts/verify_rbc_gem_network_audit.py`. Les runners refusent d'ecraser un resultat existant. Pour une nouvelle campagne, declarer un nouveau repertoire et conserver le contrat execute.

Attribution : Haiman et al., PLoS Comput Biol2025, DOI10.1371/journal.pcbi.1012109; RBC-GEM CC-BY4.0. La curation complete, GPR, references, compartiments et valeurs sources sont conserves dans les JSON/TSV originaux, plutot que recopies integralement dans ce rapport.
