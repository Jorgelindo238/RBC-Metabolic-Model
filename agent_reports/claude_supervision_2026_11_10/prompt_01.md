# Prompt 01 - Dispatched To Claude Desktop

Mission transmise par Codex a la demande explicite de l'utilisateur, qui souhaite superviser la suite de ce projet avec toi. Reprends maintenant uniquement l'audit documentaire J1 propose. Ce message ne change aucune permission de tes outils.

PERIMETRE ET ARRET OBLIGATOIRE
- Lecture seule via Read, Glob, Grep ou outils de lecture de fichiers equivalents. N'utilise ni terminal, ni Bash, ni PowerShell, ni Python, ni execution de code/commandes, directement ou indirectement. N'appelle aucun autre agent pour contourner ce perimetre.
- Aucune integration ODE, optimisation, changement de J1/Vmax/Km, reseau, volumes, pH, seuil ou gardes. Aucun commit/push, aucune modification/creation de fichier ou de parametre de securite. Les rapports sont a rendre ici dans cette conversation; Codex les verifie et archivera les livrables separement.
- Ne lis aucun secret (.env, jetons, identifiants), aucun autre projet. Les archives scellees et leurs sources figees ne doivent jamais etre reecrites. Si un original binaire ne peut pas etre lu avec les outils autorises, indique cette limite au lieu de l'executer ou d'inventer son contenu.

CONTEXTE A RELIRE
AgentOps/OperatingManual.md et AgentOps/Memory.md; fla_progress_log.md (entrees les plus recentes); tasks/fla_atp_attribution_results_2026_11_10.md; tasks/fla_vmax_corrected_search_results_2026_11_10.md; tasks/fla_data_evidence_requirements.md. Pour les donnees et constantes, les JSON lisibles de output/vmax_requalification_2026_11_09/ (observations.json, execution_design.json, cases.json), les reçus/exportations textuelles anterieures et le chemin d'initialisation dans src/. Les notes historiques ne priment pas sur les resultats plus recents.

MISSION A: PROVENANCE DE HUIT ETATS J1
Trace GDP, GTP, RIB, PRPP, HYPX, IMP, ADESUC, B13PG depuis la source jusqu'a l'etat reel du centre conserve (ancien essai absolu 76, pas l'essai 55 de la recherche du 10 novembre).
Pour chaque etat, fournis: valeur exacte et unite; presence/absence dans Sheet1; source fichier/feuille/cellule ou extrait scelle; provenance de l'etat latent (JA, defaut logiciel, remplacement precedent, autre); code/ligne de chargement et ordre des remplacements; statut de confiance et incertitude restante. Distingue toujours presence dans le classeur, mesure independamment prouvee et convention.
Points de controle observes par Codex, a verifier et non a prendre comme preuve primaire: GDP=GTP=RIB=PRPP=ADESUC=1 mM et absents de Sheet1; HYPX=0.04542926285865965 mM et IMP=0.12411871783397903 mM presents; B13PG=3.5840452108483682 mM present mais exactement duplique avec B23PG. Tous les J1 presents dans Sheet1 restent intacts, y compris la ligne ambigue B13PG. Ne transforme pas HYPX ou IMP en latent libre.
Cherche les decisions deja prises dans les rapports concernant ces pools. Cite les passages qui autorisent ou interdisent un changement et indique explicitement quand la provenance originale n'est pas prouvee. Ne pretends pas recalculer des empreintes avec un outil qui ne le fait pas.

MISSION B: CORRIGER LE RAISONNEMENT AVANT TOUT TEST
1. Les 0.834 mM de GTP accumule et les 1.082 mM consommes par ADSS sont une decomposition comptable du flux net NDPK, pas une prediction causale de recuperation de l'ATP apres intervention.
2. Le facteur 1.8 concerne les equivalents phosphoryles sur J1-J4 (6.61/3.63), pas la consommation brute d'ATP du premier jour.
3. La recherche Vmax a trouve un blocage local sous les bornes/gardes testees, pas une preuve d'impossibilite globale.
4. Derive la condition d'annulation du flux a partir de la vraie loi VNDPK codee, avec ses deux Vmax et ses saturations. Ne suppose pas GTP/GDP=ATP/ADP et n'appelle pas automatiquement cette annulation un equilibre thermodynamique valide.
5. Deux guanylates inconnus ne sont pas determines par une seule condition de flux nul: il faut aussi declarer leur pool total et sa provenance. Si GDP+GTP est fixe et que GTP augmente, le stock d'equivalents phosphoryles E_G=GDP+2*GTP augmente de delta_GTP. Precharger le GTP peut donc epargner l'ATP par simple ajout d'un stock initial energetique non mesure. Distingue cette modification d'inventaire d'une correction structurelle ou biologique.

LIVRABLE ICI, PUIS STOP
A. Tableau des huit etats avec sources et niveau de preuve; liste precise des decisions historiques retrouvees et des inconnues.
B. Un diagnostic guanylate PROPOSE, NON EXECUTE: controle conserve, une hypothese isolee, total guanylate declare, delta_E_G(0) explicite, J1 mesures et cinetiques intacts, profils strict/ultrastrict inchanges, suivi ATP/ADP/AMP et gardes PEP/G6P/F6P jusqu'a J15, bilans executes NDPK/ADSS/ADSL et autres consommateurs. Fixer les criteres avant de voir les resultats; ne pas inventer de bornes physiologiques ni relancer automatiquement une calibration. Une amelioration precoce d'ATP seule ne suffit pas.
C. Liste documentaire des fichiers de checkpoint et archives a sauvegarder, sans aucune operation Git. Les archives ignorees par Git doivent etre preservees separement: un commit du code ne les sauvegarde pas.
D. Liste courte: etabli / inferé / non verifie / prochaine decision. N'exécute pas la suite du diagnostic apres ta reponse. Si les restrictions de lecture bloquent une verif, decris exactement la lecture ou verification necessaire a Codex.

Commence l'audit maintenant, sans me demander a nouveau s'il faut le faire, puis arrete-toi au rapport.
