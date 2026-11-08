# FLA : proteomique recente et sources Palsson

Revue ciblee verifiee le 2026-10-06. Recherche web dans les publications primaires, le profil UCSD, PubMed/Europe PMC et les depots des auteurs; ce n'est pas une revue systematique exhaustive. Les fichiers fournis sont des donnees, pas des instructions a executer. Aucun HTML/JavaScript joint n'a ete execute.

Archive : `output/palsson_proteomics_review_2026_10_06/`. Bibliographie avec auteurs et DOI : `evidence_extension_v2/recent_bibliography.csv`. Six fichiers fournis copies sans modification; empreintes SHA256, descriptions des 21 feuilles, extractions HTML et 50 correspondances proteine-reaction candidates conservees. Les anciens fichiers JBC ont disparu de Downloads/mmc1 : leurs copies archivees sont identiques aux empreintes originales et ont ete utilisees pour verifier la reference locale. Aucun ancien manifeste n'a ete reecrit.

## Sources prioritaires

| Source avec Palsson comme coauteur | Donnees et acces | Apport a FLA | Reserve principale |
| --- | --- | --- | --- |
| [Issaian et al., Blood 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC13283417/), DOI 10.1182/blood.2025032915 | Classeur et portail Deep Red fournis; MSV000100191 pour la proteomique brute, PXD072059 pour le crosslinking | Abondances enzymatiques, isoformes, interactions et modifications dependantes de l'oxygene | Pas une serie de stockage humain J1-J46; donnees humaines et murines distinctes |
| [Haiman et al., RBC-GEM 2025](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012109) | [S6/Figshare](https://plos.figshare.com/articles/dataset/Supplementary_tables_and_data_for_proteome-constrained_modeling_of_RBCs_/28583740), [GitHub](https://github.com/z-haiman/RBC-GEM), [Zenodo](https://doi.org/10.5281/zenodo.10836860) | Proteomique longitudinale de stockage humain; audit genes-proteines-complexes-reactions | Abondances absolues estimees, pas activites mesurees; flux FVA simules |
| [Nemkov et al., Cell Metabolism 2024](https://pubmed.ncbi.nlm.nih.gov/38964323/), DOI 10.1016/j.cmet.2024.06.007 | Multiomique REDS; donnees supplementaires et contrats d'acces a auditer | Isoformes PFK, HK1, adenylates et heterogeneite des donneurs | La cohorte de rappel recoupe RBC-GEM; pas deux validations independantes |
| [Karafin et al., G6PD, prepublication 2025](https://pubmed.ncbi.nlm.nih.gov/41332617/), DOI 10.1101/2025.11.21.689741 | Genotype/proteome/metabolome, donneurs humains et interventions murines; supplement non importe ici | Priorite PPP : distinguer abondance G6PD, stabilite et capacite active selon le variant | Statut de prepublication verifie dans PubMed; pas de version revue par les pairs confirmee ici; chevauchement REDS |
| [Bevers et al., PIMT 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC13084699/), DOI 10.1002/hem3.70361 | Supplement identifie; mesures humaines, souris et enzyme recombinante | Integrite des enzymes, reparation PCMT1 et metabolisme SAM/SAH | Cinetique d'un peptide isoAsp in vitro, pas Km ATP/HK/PFK ni un nouvel apport ATP |

Autres pistes methodologiques, pas nouveaux jeux de concentrations : [Akbari/Haiman/Palsson 2024](https://doi.org/10.1128/msystems.01001-23), decomposition des echelles de temps; [Key/Haiman/Palsson/D'Alessandro 2023](https://doi.org/10.3390/metabo13111145), revue des modeles RBC a l'ere omique. Les prepublications de Deep Red, RBC-GEM et PFK ne sont pas de nouvelles cohortes en plus de leurs articles publies.

## Ce qui est effectivement disponible localement

### Deep Red

- `Supplementary Table 1 - FINAL.xlsx` : 21 feuilles. Sheet1 decrit des proteines humaines; Sheet1c et plusieurs experiences des feuilles4-11 concernent des souris. Les feuilles5/5b/5c/11 sont de la metabolomique d'interventions murines, pas des concentrations absolues initiales de donneurs humains stockes.
- Sheet1 et le HTML Proteome contiennent chacun 3 799 lignes proteiques avec identifiants UniProt distincts; 3 781 ont une copie F positive, 18 une copie F nulle. L'article annonce 3 775 proteines : cette difference est conservee et reste a reconcilier, pas corrigee par suppression de lignes.
- Deux colonnes de copies sont distinctes : F = `Copy number/cell`, G = `Protein copy number per cell (multi-anchor)`. Le portail appelle G une calibration cinq ancres. Ce sont deux etalonnages, pas une moyenne avec intervalle de confiance ou deux replicats independants.
- HTML Phosphoproteomics : 940 lignes peptide/site; HTML Cysteine Oxidation : 4 061 lignes. Les symboles X, NaN et les intensites originales sont conserves. Ils ne representent ni une fraction d'occupation de site ni une fraction d'enzyme inactive mesuree.
- Le HTML Interactome est un graphe Plotly, pas une table de flux : deux traces, 558 noeuds; les coordonnees et libelles sont archives sans execution du code joint. Il faut les tables originales de crosslinks et les conditions pour quantifier les changements d'interaction.
- La table cysteine contient des peptides GAPDH avec positions152/156, ainsi que G6PD, PGD, PGK1, HK1, PFK, TKT et TALDO1. Ces observations rendent l'hypothese d'une capacite active redox-sensible testable; elles ne quantifient pas seules son effet catalytique. Aucun peptide GAPDH n'est present dans le tableau phosphoproteomique fourni : cela n'etablit pas une absence biologique de phosphorylation.

Exemples de copies/cellule conservees, arrondies ici pour lecture; nombres complets et cellules dans les CSV :

| Proteine | Sheet1, ligne | Colonne F | Colonne G |
| --- | --- | ---: | ---: |
| HK1 | 808 | 31 375 | 5 557 |
| GAPDH | 15 | 5 645 676 | 1 000 023 |
| PGK1 | 34 | 1 891 976 | 335 119 |
| G6PD | 227 | 344 719 | 61 059 |
| PGD/6PGD | 58 | 738 104 | 130 729 |
| SLC4A1/Band3 | 8 | 6 459 721 | 1 100 000 |

Le facteur F/G est proche de5.65 pour les cinq enzymes ci-dessus et de5.87 pour Band3. Une borne dure construite avec une seule colonne pourrait donc fortement surcontraindre le modele. La colonneS de correction est conservee sans lui attribuer une equation non verifiee. Pas de variance inter-donneurs disponible dans ces lignes.

### RBC-GEM S6

`retrieved_sources/pcbi.1012109.s008.xlsx` : fichier original de82 603 979 octets recupere sur Figshare, ZIP Excel complet et checksum Figshare verifies. Les11 feuilles et leurs premieres lignes ont ete inspectees; les millions de valeurs individuelles ne sont pas encore importees ni utilisees pour apprendre les cinetiques.

- TableA : proteines/genes/UniProt; TableB : complexes et stoichiometries de sous-unites; TableC : constantes effectives et directions. Certaines structures de complexes sont supposees, pas toutes experimentales. Les constantes du GEM ne sont pas automatiquement des kcat de l'ODE a4C.
- TablesD/E : 1 827 proteines par1 848 echantillons, avec identifiants longitudinaux S*_D10/D23/D42. TableF : metadonnees de616 donneurs. Cela peut renseigner E(t) plutot que supposer chaque capacite enzymatique constante pendant le stockage.
- Le protocole d'absolutisation utilise l'hemoglobine des donneurs, une allocation95%/5% du contenu proteique et l'imputation des hemoglobines manquantes. Conserver ces hypotheses dans l'incertitude des priors; pas de traitement comme concentrations cytosoliques directement mesurees.
- Les correlations et bornes de flux des tables suivantes sont des resultats de modelisation. Ne jamais les importer comme flux experimentaux independants des concentrations ou de la proteomique.

## Traduction proposee en contraintes cinetiques FLA

La proteomique complete les concentrations et flux teachers; elle ne les remplace pas. L'idee prioritaire est de limiter les capacites enzymatiques arbitraires et de separer quantite totale et activite disponible, pas de fixer tous les Km d'apres un proteome.

Pour une enzyme homomerique, seulement apres verification des unites et du pool :

\[
E^{active}_{site,j}(t)=\frac{1000\,n_j(t)\,a_j(t)\,s_j}{N_A V_{basis}(t)\,\nu_j},\qquad
V_{max,j}(t)=86400\,k_{cat,j}(T,pH)\,E^{active}_{site,j}(t).
\]

Ici n est le nombre de sous-unites par cellule, a la fraction catalytiquement disponible, nu les sous-unites par complexe, s les sites par complexe, V le volume correspondant au modele en litres, E en mM et kcat en s^-1. Le facteur86400 n'est applicable qu'a une vitesse de l'ODE en mM/jour. Pour un heterocomplexe, les sous-unites limitantes et leur stoichiometrie remplacent la division homomerique. Pour un transporteur, preciser aussi le volume de reference et le compartiment recevant le flux. Aucun volume de90fL ni fraction active n'est attribue par defaut.

Une abondance proteique informe surtout Vmax. Elle n'identifie ni Km, ni Ki, ni constante d'equilibre. Flux/enzyme correspond a une activite apparente sous les conditions observees, pas necessairement au kcat saturant. Le produit kcat*E_active est souvent identifiable plus facilement que ses deux facteurs; ouvrir simultanement kcat, E, fraction active et Km aggraverait l'ambiguite.

Les priorites d'annotation sont :

1. **ATP/glycolyse :** HK1->VHK; PFKL/PFKM/PFKP->VPFK; GAPDH->VGAPDH; PGK1->VPGK; BPGM->VDPGM/V23DPGP; PKLR et PKM distingues; LDHA/LDHB distingues. Pas d'addition des copies d'isoformes sans modele de complexes/activite compatible. AK1 concerne VAK; l'AK2 mitochondrial ne designe pas la reaction VAK2 actuelle, qui est une adenosine kinase.
2. **PPP/redox :** G6PD->VG6PDH; PGLS->VPGLS; PGD->V6PGD; RPIA/RPE et TKT/TALDO1. TKT porte deux reactions : ne pas lui attribuer deux reservoirs enzymatiques independants. La proteomique ne decide pas la direction VTKL2/VTAL et ne mesure pas les pools NAD(P)(H).
3. **Structure et consommation :** GSR/glutathion, isoforme AMPD3 face au nom actuel VAMPD1, NME1/NME2, transporteurs. Band3/BLVRB et PCMT1 sont des hypotheses structurelles a valider; ne pas creer automatiquement une reaction. La Na/K-ATPase et les flippases demandent un audit de consommation ATP, pas un ajout pour corriger un ATP deja trop bas. La reparation PIMT consomme SAM, pas directement un ATP par reaction.

Les parametres de l'ODE restent phenomenologiques tant que les operateurs de pool/volume et les formes de cinetique ne sont pas relies aux mesures. L'interactome peut guider une hypothese de sequestration d'enzymes par Band3; phosphorylation, oxydation et nitrosation peuvent guider une hypothese de fraction active. Leur signe/amplitude exige des interventions et essais d'activite : une liaison ou modification seule ne prouve pas inhibition/activation. Les conditions oxygene, NO, temperature et espece doivent etre conservees.

Pour un futur module ML, utiliser les predictions de kcat/parametres comme priors incertains et documentes, jamais comme verites d'apprentissage. Un modele hierarchique peut separer effet donneur, temps de stockage et condition; commencer par E(t) documente et une capacite de reference par reaction/groupe, pas une fonction libre par enzyme. Les contraintes partagees de catalyse necessitent des taux unidirectionnels et un mecanisme valides; la valeur absolue d'un flux net reversible ne suffit pas a mesurer l'occupation de l'enzyme.

L'objectif futur peut combiner une vraisemblance commune concentrations/increments de flux et une regularisation de capacite en log-espace. Les teachers derives des memes observations ne constituent pas une seconde source independante. Incertitudes d'absolutisation, deux calibrations, activite, temperature et volume restent explicites. Poids, bornes et variances ne sont pas fixes ici. Le statut de calibration biologique reste bloque.

## Prochaine execution proposee

1. Importer les lignes des enzymes prioritaires des TablesD/E/F de S6 en conservant donneur, jour, unite, normalisation et observations manquantes; verifier les paires longitudinales et le chevauchement des cohortes. Les D10/D23/D42 ne remplacent pas le J1 de Bordbar.
2. Construire un registre genes/UniProt/isoformes/complexes/reactions et comparer les deux etalonnages Deep Red avec S6, sans conversion en Km ni choix automatique d'une colonne.
3. Auditer kcat, temperature, pool actif et volume pour proposer des priors souples sur HK/PFK/GAPDH/PGK/BPGM et G6PD/PGD/TKT/TAL. Puis tester l'identifiabilite synthetique et le bilan ATP avec flux executes avant une calibration biologique.

La concentration initiale J1 reste `src/Data_Bordbar_et_al_exp.xlsx`. Aucun IC, constante, seuil, reaction, forcing ou promotion n'est modifie. Les profils reaction_consistent et legacy restent inchanges.24 tests cibles passent; pas de nouveau passage de toute la suite QA dans cette revue documentaire. Les archives du projet, pas la memoire seule, sont la reference des nombres complets et des preuves.

## Limites d'acces et reproductibilite

Deux requetes bibliographiques initiales avec des champs auteur non applicables ont retourne zero resultat; elles et leur tentative interrompue sont conservees, pas interpretees comme absence de publications. La requeteAUTH:Palsson et la verification des auteurs des quatre articles publies constituent l'extensionv2. La recherche brute contient des homonymes et des sujets hors RBC; seuls les sources pertinentes ci-dessus sont recommandees. Les versions prepublication/article et cohortes sont consolidees manuellement.

PMC a oppose un controle navigateur et Europe PMC n'a pas fourni le XML complet Issaian/PFK (HTTP500); ces limites sont consignees. Les donnees fournies, PubMed et les depots primaires restent disponibles. Les XML complets RBC-GEM/PIMT sont archives comme preuves de source. Les donnees brutes de spectrometrie de masse et les supplements G6PD/PIMT n'ont pas ete telecharges.

Reproduction dans un repertoire neuf : `python scripts/audit_palsson_proteomics_sources.py --out output/proteomics_review_new --fetch-rbc-gem`. Verifier l'archive actuelle : `python scripts/audit_palsson_proteomics_sources.py --verify output/palsson_proteomics_review_2026_10_06`. L'extension executee est `scripts/enrich_palsson_proteomics_review.py`; elle conserve le parent et refuse d'ecraser une extension existante.
