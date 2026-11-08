# Fermeture biochimique reversible : C4, folates, redox et OPLAH

Demande du 2026-10-06 : traiter les priorites restantes de l'audit RBC-GEM. Nouvelle variante `src/rbc_biochemical_extensions.py`, version `airbc-biochemical-diagnostic-2026.10.06-v1`. Archive distincte : `output/biochemical_closure_2026_10_06/`. Aucun ancien manifeste ni source scientifique n'est reecrit.

## Perimetre et reversibilite

Le noyau `equadiff_brodbar.py`, le catalogue historique `RBC/Rxn_RBC.txt`, le schema structural2, le limiteur, la reference provisoire et le classeur Bordbar restent inchanges. Les variantes sont accessibles uniquement par le nouvel adaptateur : `historical`, `vcse_c4`, `folate_split`, `vcse_folate`. Le mode historique transmet exactement l'appel au noyau precedent, y compris le profil legacy lorsqu'il est explicitement choisi.

Les variantes etendues utilisent124 concentrations + pHi final, contre113 + pHi historiques. Les indices historiques0-112 sont preserves; l'ancien pHi est deplace apres les onze nouvelles concentrations. L'ancienne interface et les anciens tableaux113/114 ne doivent pas recevoir ce vecteur125 : le nouvel adaptateur effectue la projection explicitement. Aucun import automatique dans l'API, l'optimiseur ou les anciens teachers.

Pour revenir a `historical`, reprendre le vecteur historique114 preserve, pas le vecteur etendu125 avec un simple changement de mode. Le mode historique transmet volontairement l'interface originale; les etats et les labels doivent etre selectionnes avec leur registre.

La matrice a112 colonnes :100 historiques, cinq branches preparees lors de l'audit precedent et sept branches nouvelles. Les cinq precedentes restent a zero dans cette passe. Les coefficients CAT/XAO corriges precedemment sont conserves; les exports ABC energetiques restent des hypotheses distinctes et ne sont pas actives dans les nouveaux replays. `abc_exports=True` est disponible uniquement comme option explicite.

## 1. VCSE : correction du produit C4

Ancien bilan :

```
CYSTHIO(C7) -> CYS(C3) + AKG(C5) + NH4
```

Il cree un carbone. Dans la variante C4 :

```
CYSTHIO + H2O -> CYS + AKB + NH4
AKB = 2-oxobutanoate / alpha-ketobutyrate, C4
```

Le coefficient AKG de VCSE devient zero et le nouveau pool AKB recoit le produit. Carbone7 -> 3+4, azote2 -> 1+1, soufre conserve. La somme RBC-GEM `CYSTL1 + 2ABUTENT + 2IMBUTDA` donne exactement cette reaction globale; ses formules source ferment tous les elements. [UniProt CTH / Rhea14005](https://www.uniprot.org/uniprotkb/P32929/entry) confirme cette chimie. Le flux VCSE historique est conserve comme hypothese conditionnelle, pas recalibre.

Le regroupement suppose que les intermediaires amino/iminobutanoate peuvent etre elimines du modele reduit. Il ne prouve pas leurs constantes ni l'activite CTH/RIDA a4C. AKB n'est ni un sink invisible ni une alimentation d'AKG; sans devenir aval valide, il s'accumule explicitement. AKB(0)=0 dans les replays est une hypothese nulle declaree, pas une concentration manquante estimee ou une nouvelle mesure.

## 2. Folates : separation sans conversion implicite

L'ancien METTHF n'etait pas observe dans les55 lignes J1. Il est remplace dans la variante par MTHF au meme indice47, et MLTHF devient un nouveau pool :

```
VSHMT : SER + THF -> GLY + MLTHF (+ H2O omise)
VMESE : HCYS + MTHF -> MET + THF
VMTHFR : MLTHF + NADPH -> MTHF + NADP (proton omis)
```

MTHF est5-methyl-THF; MLTHF est5,10-methylene-THF, et non5,10-methenyl-THF. SHMT ne fournit donc plus directement le substrat de MESE. La colonne SHMT correspond a RBC-GEM GHMT2. La chimie MTR/MTHFR est documentee par [MTR](https://www.uniprot.org/uniprotkb/Q99707/entry) et [MTHFR](https://www.uniprot.org/uniprotkb/P42898/entry); l'equation UniProt MTHFR est presentee a l'envers, avec direction physiologique right-to-left, explicitement verifiee.

VMTHFR n'est activee qu'avec vmax, Km_MLTHF et Km_NADPH explicites; elle est inactive dans tous les replays Bordbar. Les observations disponibles ne prouvent pas MTR/MTHFR actifs dans les RBC matures. Les besoins B12/FAD, la reactivation MTRR, l'orientation reversible de SHMT et les autres branches folates ne sont pas declares resolus. La cinetique MESE historique reste conditionnelle a son ancien Km non valide pour ce nouveau pool precis.

L'initialisation exige une partition explicite MTHF/MLTHF conservant l'ancien total latent METTHF :1mM dans ce contexte, non verifie biologiquement. Les deux extremites methyl-only et methylene-only sont des diagnostics limites, pas des bornes de prior physiologique ou des candidats optimises. THF(0) reste1mM historique non observe; le total THF+MTHF+MLTHF est conserve par ces reactions. Les55 concentrations mesurees J1 et les autres anciennes entrees ne sont pas modifiees.

## 3. Redox : acceptateurs suivis, pas de puits libre

### NADH - cytochrome b5 - metHb

```
VCYB5R : NADH + 2 CYB5OX -> NAD + 2 CYB5RED
VMETHB_RED : CYB5RED + HBFE3 -> CYB5OX + HBFE2
```

HBFE3/HBFE2 sont des concentrations de sites heminiques Fe(III)/Fe(II) sur une meme base volumique, pas des tetrameres Hb. Un NADH fournit deux electrons, un cytochrome reduit en fournit un et un site Fe(III) en accepte un. Le registre conserve les totaux NAD(H), CYB5 et heme ainsi que le ledger2*NADH+CYB5RED+HBFE2 pour ces deux colonnes.

La colonne RBC-GEM FCYTOB5OXR correspond exactement a VCYB5R. En revanche METHBCYTBR consomme deux cytochromes reduits pour un hb dont la formule source comporte un Fe, et a un residu de charge+1 selon les charges stockees. Ce coefficient n'est pas copie dans la representation monosite : l'incoherence de base/electrons est explicite dans `source_audit.json`. [Reactome CYB5Rs/metHb](https://reactome.org/content/detail/R-HSA-6806831) et [UniProt CYB5R3](https://www.uniprot.org/uniprotkb/P00387/entry) soutiennent le mecanisme, sans etablir nos concentrations actives ou constantes a4C.

Il n'y a pas de generation continue artificielle de metHb. La consommation NADH est bornee par les acceptateurs initialement disponibles : au maximum(CYB5OX(0)+HBFE3(0))/2 pour ce sous-reseau. Une autoxydation/oxygenation physiologique exige des especes oxyHb/superoxyde/O2 et des donnees adaptees; elle n'est pas remplacee par un forcing temporel libre.

### NADPH - TXN - PRDX

```
VTRXR : NADPH + TXNOX -> NADP + TXNRED
VPRDX_PEROX : PRDXRED + H2O2 -> PRDXSO (+ H2O)
VPRDX_RESOLVE : PRDXSO -> PRDXOX (+ H2O)
VPRDX_REDUCE : PRDXOX + TXNRED -> PRDXRED + TXNOX
```

Les quatre colonnes correspondent a TRDRy, PRDX2OX1, PRDX2SOR et PRDX2TRDXRD. Le pool sulfenique PRDXSO est explicite. Le cycle net consomme NADPH et H2O2, pas ATP; les totaux NADP(H), TXN et PRDX et le ledger2*NADPH+2*TXNRED+2*PRDXRED-2*H2O2 ferment. Les proteines PRDX2/TXN/TXNRD1 detectees ne fournissent pas automatiquement une fraction active, un etat d'oxydation ou un Km.

La base PRDX est l'unite redox2-cys des formules du GEM; les copies de monomeres proteiques ne doivent pas etre converties directement en ces unites. Les anciens compartiments/volumes restent eux aussi des hypotheses : une fermeture de concentration sur la base historique commune ne prouve pas une conservation de quantite dans une poche aux volumes changeants.

Les modules redox exigent toute la chaine, tous les pools initiaux et chaque constante explicites. Les lois de saturation sont des prototypes phenomenologiques, pas des lois enzymatiques calibrees. Hyperoxydation/reparation PRDX, FMN/BLVRB, acceptateurs alternatifs, cofacteurs et capacites enzymatiques partagees restent a caracteriser. Les nouvelles contributions proton/pH ne sont pas implementees : aucun succes du test de sous-reseau ne valide une prediction acidobasique physiologique.

Les tests synthetiques utilisent des nombres declares uniquement pour tester le logiciel. Les nouveaux pools redox sont a zero et leurs branches inactives dans les replays Bordbar; aucune inference ou import proteomique en concentration active n'est realise. Des pools actifs reels sous1e-3mM exigeraient un audit de sensibilite au limiteur, pas son ajustement au score ATP.

## 4. OPLAH : maintien et contre-test explicite

La politique par defaut est `oplah_policy="retained"` : OXOP + ATP -> GLU + ADP est execute avec la cinetique archivee. La detection recente O14841/OPLAH dans Deep Red (Sheet1, ligne2004, deux estimations F/G) contredit une affirmation d'absence absolue, mais ne prouve pas une activite a4C. L'exclusion [RBC-GEM](https://github.com/z-haiman/RBC-GEM/blob/43fd381d9eb8a8a4079629012362312960e1c009/data/curation/reactions_removals.tsv) reste preservee comme evidence de curation historique.

`oplah_policy="diagnostic_off"` met uniquement le taux execute a zero dans un cas nomme. Aucun gene, parametre seed ou reaction n'est supprime definitivement. [UniProt OPLAH](https://www.uniprot.org/uniprotkb/O14841/entry) confirme la chimie ATP/ADP, pas la capacite RBC stockee. Une mesure d'activite avec temperature, volume et fraction active documentes reste necessaire pour arbitrer le conflit.

## Protocole de verification

Contrat : `config/fla_biochemical_closure_diagnostic.json`. Cinq cas structuraux J1-J4, chacun strict/ultrastrict : VCSE seul, folates methyl-only seuls, corrections combinees methyl-only, corrections combinees methylene-only et contre-test OPLAH-off combine methyl-only. Toutes les55 entrees mesurees J1 sont exactes. Les anciennes cinetiques, les quatre IC redox1mM, le seuil1e-3, le profil BDF et l'absence de reset/forcing restent inchanges. Deux sous-reseaux redox synthetiques ont chacun deux integrations0-2 distinctes des donnees Bordbar.

Pour chaque cas : bilans des flux effectivement executes sur chaque intervalle, quadrature Gauss4/8 aux pas acceptes, minimum brut aux etats acceptes/denses/noeuds Gauss et comparaison strict/ultrastrict. La verification independante reevalue le RHS/limiteur en sept points par replay, reconstruit les matrices/catalogue compartimente, les IC, les budgets stockes, les ledgers et la convergence sur les grilles sauvegardees communes. Elle ne recalcule pas independamment les integrands Gauss non sauvegardes.

Sources primaires : cinq JSON UniProt originaux, sous-ensemble du GEM epingle et receipts dans `primary_sources/`. Suite QA :982 passes, deux ignores pour les anciens originaux JBC/Nishino indisponibles;30 nouveaux tests incluent372 sondes aux frontieres zero. Les six warnings Optuna et l'avertissement Pydantic/Python3.14 sont preexistants.

Les resultats definitifs sont dans `fixed_context/summary.json`, les etats/flux/budgets dans chaque sous-repertoire et les preuves dans `independent_verification.json`. Le catalogue final avec compartiments est `Rxn_RBC_biochemical_compartmented.txt`; la premiere vue matricielle `Rxn_RBC_biochemical_diagnostic.txt` ne porte pas les compartiments et n'est pas le contrat de catalogue final.

## Resultats executes

Les14 integrations sont completes en731.7 secondes. Tous les11480 controles de bilan/quadrature et2142136 comparaisons de convergence passes; minimum verifie zero, aucune concentration negative selon la tolerance declaree de-1e-10mM, fermeture executee a la precision numerique. Les nombres de comparaisons ne sont pas des echantillons biologiques independants.

| Cas ultrastrict | ATP J4, mM nominal | ADP J4 | AMP J4 |
| --- | ---: | ---: | ---: |
| Reference historique archivee | 0.0007510433 | 0.0000804468 | 2.59366510 |
| VCSE C4 seul | 0.0007547004 | 0.0000805570 | 2.59360555 |
| Folates methyl-only seuls | 0.0007510429 | 0.0000804470 | 2.59366511 |
| Combine methyl-only, OPLAH conservee | 0.0007547005 | 0.0000805570 | 2.59360556 |
| Combine methylene-only, OPLAH conservee | 0.0007588565 | 0.0000813870 | 2.59420357 |
| Combine methyl-only, OPLAH contre-test off | 0.0007766316 | 0.0000847363 | 2.59216261 |
| Bordbar J4 nominal | 1.079765 | 1.073256 | 0.539208 |

La reference est verifiee dans l'archive precedente, pas reintegree dans cette campagne. La correction C4 releve ATP d'environ0.49%, le combine methylene-only d'environ1.04%, et le contre-test OPLAH combine d'environ3.41% par rapport a cette reference. Aucun cas ne restaure la partition adenylate, et aucune extremite folate n'est selectionnee comme meilleure initialisation. Les unites/pools/covariances Bordbar restent soumis aux reserves de provenance anterieures.

Les quatre integrations redox synthetiques ferment leurs ledgers, conservent les pools de transporteurs/acceptateurs et restent bornees par les donneurs/acceptateurs initiaux. ATP/ADP/AMP y restent zero : aucune production ATP artificielle. Elles testent des sous-reseaux a constantes fictives declarees, pas une prediction RBC ou une solution au deficit. La verification independante passe2377 controles et confirme les55 IC mesurees, les anciens pools non modifies hors partition folate nommee, les hashes du parent et les colonnes source. Suite QA finale982 passes/deux ignores. Le sceau final preserve les scripts/configurations/documents effectivement executes sans modifier le parent.

## Decision pour FLA

Ces corrections fournissent des hypotheses structurelles auditables; elles ne valident pas les anciens pools latents1mM ni la calibration biologique. L'ancien reseau reste disponible et aucune variante n'est promue sur le score ATP.

Avant la prochaine calibration : reconstruire les contraintes/identifiabilite des flux avec la matrice etendue, clarifier le devenir AKB et les mecanismes CYT/methylation encore ouverts, documenter les pools redox disponibles et leur observation, puis auditer seuil, acidobase, capacites partagees et recuperation synthetique dynamique. Ne pas ajouter simultanement toutes les nouvelles constantes : ni les teachers correles ni la proteomique ne rendent ces branches identifiables sans nouvelles contraintes.

Reproduction : `python scripts/audit_biochemical_closure_sources.py --out <nouvelle_archive>` pour les sources; le runner courant `python scripts/run_biochemical_closure_diagnostic.py` execute le contrat preregistre dans son repertoire reserve et refuse l'ecrasement; verification `python scripts/verify_biochemical_closure_diagnostic.py`. Toute nouvelle campagne doit declarer son propre chemin et conserver les scripts/contrats effectivement executes.
