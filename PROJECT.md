# llmSport — suivi minimal

## Décisions retenues

Objectif : AI Platform / MLOps / LLMOps, spécialisation inference et serving, par un journal sportif et alimentaire francophone. Angular minimal -> Java/Spring Boot -> Python/FastAPI interne ; PostgreSQL. Java calcule et persiste ; le modèle propose. Pas de prescription médicale, de photos ou d'estimation personnalisée des calories sportives au MVP.

L'[ébauche v0.1](documentation/Sport_Nutrition_Skills_Cadrage_v0.1.md) est conservée comme source historique. Ses huit documents proposés ne sont pas adoptés en bloc. Les décisions de la conversation reprises ici priment sur les propositions divergentes.

| Jalon | Direction retenue |
|---|---|
| P0 | Cadrage, contrats, 30 cas fictifs de développement, sept skills locaux et vérifications initiales (option C). |
| P1 | Baselines déterministes alimentaires/sportives, provenance, correction, contrats Java/Python et premiers contrôles d'exploitation. |
| P2 | Première inférence, évaluation et MLflow ; diagnostic Python puis tenseurs, formes, types et device PyTorch. En fin de P2, [pilote lexical RAG-01](documentation/RAG-01.md) prévu sur décision distincte, pour 15–24 h supplémentaires. Passages et barème figés, tests préparés, non exécutés. |
| P3 | Exploitation progressive, reprise et déploiement borné selon autorisation. |
| P4 | Produit et interface : bilan unique, sélection des apports, corrections et historique ; petit exercice PyTorch expliqué. |
| P5 | Adaptation supervisée pédagogique avec PyTorch et Transformers, éventuellement PEFT/LoRA ; intégration au produit conditionnelle. |
| P6 | Inference/serving et benchmarks ; GPU/vLLM seulement si utile, compatible et autorisé. |
| P7 | Industrialisation du laboratoire, Azure et atelier AWS borné ; pas de multicloud actif imposé. |

PyTorch : tenseurs puis Dataset/DataLoader, passage avant, perte, gradients, optimiseur et boucle manuelle avant Trainer, sauvegarde/chargement et vérification. Le petit modèle pédagogique de P4 n'est pas un nouveau modèle de production. Avant entraînement : RAM/disque, versions, accélération Mac réellement disponible, compatibilité du modèle et essai borné avant/arrière autorisé, mémoire des poids/gradients/optimiseur/activations ; chiffrer une solution distante avant accord. Qwen3-4B reste candidat, Qwen3-0.6B est une piste plus petite à vérifier. Aucun matériel ni entraînement n'est validé ici.

Comparer baseline déterministe, modèle préentraîné et même modèle adapté sur tâche/partitions fixées. MLflow trace paramètres, versions code/modèle/tokenizer, données/partitions et empreintes calculées, checkpoints, qualité et ressources observées. Distinguer PyTorch (entraînement/inférence), MLX-LM (autre framework), Ollama (serving pratique) et vLLM (serving selon matériel), sans imposer tous les outils.

**T02 finalisé en P0** : [30 cas fictifs de développement](data/dev/cases.json), répartis en 15 alimentaires, 10 sportifs et 5 mixtes/ambigus, avec [catalogue versionné](data/dev/catalog.json). Les [10 calculs et 10 ambiguïtés](data/dev/oracles.md) sont des sous-ensembles relus par raisonnement d'un second agent ; ce n'est pas une annotation humaine. Ils ne constituent pas le test final indépendant, qui sera préparé séparément.

## T03 — bilan nutritionnel unique et contrat (P0)

Un bilan par repas et révision contient les apports choisis. Énergie, protéines, glucides et lipides sont proposés par défaut ; fibres, sucres, sel, vitamines et minéraux selon les données disponibles. Chaque vitamine/minéral possède son identifiant et son unité. Sélection et affichage ne modifient pas les données ni leurs statuts.

Chaque apport porte identifiant, valeur (ou null), unité, statut, provenance des contributions et éléments manquants motivés. Les quantités déclarées, corrections et version du catalogue restent reliées au résultat.

- **complet** : toutes les contributions du repas déclaré sont calculables pour cet apport, y compris celles explicitement égales à zéro.
- **partiel** : au moins une contribution calculable et au moins une manquante ; valeur = sous-total connu, même s'il vaut zéro.
- **indéterminé** : aucune contribution calculable ; valeur = null, jamais zéro par défaut.

Unité, base de référence, cru/cuit et quantité doivent permettre le calcul ; pas de conversion inventée. Le statut est par apport : aucune étiquette globale ne doit masquer les différences. « Complet » ne prouve pas que tout le repas réellement consommé a été déclaré.

**Premier cas de référence [T03-SEL-001](contracts/examples/java-salt-reference.json)**, intégralement fictif : 100 g de chacun des trois aliments, riz cuit, poulet cuit et courgettes cuites. Le riz est corrigé de 150 à 100 g. Sel du riz explicitement 0 g/100 g ; sel du poulet et des courgettes absent. Attendu validé par l'apprenant : **0 g — sous-total partiel**, deux contributions manquantes. Dans le même bilan : protéines 34,5 g complètes, énergie 295 kcal partielles, glucides et lipides indéterminés faute de valeurs. La fixture est une variante versionnée `DEMO-FOOD 0.1-salt-variant` dérivée de 0.1, pas une modification silencieuse du catalogue original. L'ancienne fixture de cadrage reste conservée dans les preuves du socle ; l'exemple lié ici suit le schéma canonique 0.1.0.

**T03 finalisé en P0** avec le [schéma canonique 0.1.0](contracts/analysis.schema.json), la [sémantique](contracts/analysis.md) et les [25 exemples](contracts/examples/manifest.json), dont 14 conformes et 11 rejetés comme prévu. T04 a vérifié la branche de réception sur HTTP. T08 a vérifié le rejet transactionnel d’une proposition r1 devenue obsolète après correction r2.

**T06 en P1** a confronté le calcul Java des apports aux oracles manuels, avec des statuts différents pour un même repas. **P4** ajoute le sélecteur et le bilan, avec source et manques consultables et distinction entre absence, zéro et sous-total.

## Contrats et exploitation à préserver

Java garde contrôle transactionnel des corrections, révisions et idempotence. Une réponse IA devenue obsolète ne remplace pas une correction. Même clé et même contenu rejouent le résultat ; contenu divergent produit un conflit ; pas de promesse d'appel externe payant exactement une fois. Un propriétaire des retries avec délai global : Python pour les appels IA, sans empilement Java/Python/SDK. Pour une autre opération externe, expliciter son propriétaire sans modifier cette décision IA. Imports validés puis publiés atomiquement ; release versionnée, rollback compatible qui préserve les nouvelles données utilisateur.

## État et effort

**P0 clôturé. P1 clôturable sur `1d4f315`. T10 a reçu son GO.** T01 a établi le raisonnement sur les protéines complètes, l’énergie partielle, le sel partiel avec un zéro connu et la comparaison atomique de révision. T02/T03 et leurs contrôles locaux ont été réalisés en P0. Une demande neutre isolée a conduit à la lecture de sn-plan-contracts. [Bilan P0](documentation/p0-verification/rapport.md) · [Vérifications P1](documentation/p1-verification.md)

P0 : référence historique 8–12 h ; ébauche 4–8 h, estimation distincte non substituée. Le cadrage précédent proposait +1–2 h (9–14 h) sans création/vérification des sept skills. L'option C ajoute maintenant ce lot ; son temps observé et son impact sont consignés dans le rapport de vérification du lot, sans compter deux fois le cadrage. Il ne représente pas le temps d'apprentissage humain.

PyTorch : supplément déjà annoncé +10–16 h (P2 +2–4 h, P4 +8–12 h), P5 réalloué dans sa charge existante ; ne pas le recompter. P1/P4 hors ajout PyTorch restent des hypothèses à recalibrer au découpage des tickets.


Lot option C réalisé le 17 novembre 2026 : [preuves et effort observé](documentation/verification-skills-2026-11-17/rapport.md). Sept skills créés, structure/découverte locale vérifiées, 21 scénarios fictifs évalués (30 réponses avec rejeux). Proposition P0 révisée **10–16 h** : base 8–12 h + enveloppe complète 2–4 h, qui remplace le précédent supplément de cadrage 1–2 h ; temps observé inclus, pas additionné. L’appropriation humaine reste à mesurer. Aucun entraînement ni déploiement effectué.


## Repères d'évaluation et prochains tickets, sans lancement

Les futurs bilans d'évaluation publieront corrects/total et, pour l'acceptation automatique, corrects acceptés/acceptés avec leur couverture et les erreurs critiques par catégorie ; une précision avec zéro acceptation est indéfinie. Clarifications et abstentions restent distinctes. Les objectifs chiffrés de l'ébauche sont des hypothèses, pas des mesures ni des seuils validés. Les 30 cas servent à développer ; toute sélection sur ces cas exclut leur emploi comme test final indépendant.

La [mesure de la baseline déterministe T10](documentation/p2/baseline.md) ouvre P2. T11 attend sa décision de lancement. RAG-01 est prévu en fin de P2.

## T04 — échange HTTP local

**Terminé et vérifié le 17 novembre 2026.** Client → `POST /analysis` (Spring Boot) → `POST /internal/proposals` (FastAPI). Corps de demande minimal pour un repas : `{"entry_id":"MEAL-001","entry_revision":2,"text":"mon accompagnement"}`. Python conserve la déclaration, renvoie une mention à clarifier et laisse sa quantité inconnue. Il génère la même proposition pour la même demande. Aucun modèle, catalogue ou journal n’intervient dans cet échange. [Service Python](python/app.py) · [Réception Java](java/src/main/java/org/llmsport/AnalysisController.java)

Java transmet ou crée un UUID dans `X-Correlation-ID`, contrôle son retour et refuse un résultat rattaché à une autre entrée ou révision. Un seul appel part vers l’adresse Python configurée, avec une échéance de 2 s couvrant la réception du corps. Java résout `#/$defs/python_proposal` dans le [schéma T03](contracts/analysis.schema.json) embarqué à l’identique dans le JAR. La preuve porte sur deux services locaux. L’authentification du service sur un réseau partagé reste à établir.

| Réponse reçue depuis FastAPI | Résultat observé côté client de Java |
|---|---|
| Proposition déterministe produite par le service applicatif | **200**, `python_proposal`, `MEAL-001`, révision 2 |
| Corps JSON tronqué | **502**, `invalid_json` |
| [Rapport Java fictif](contracts/examples/business-invalid-python-forges-java-report.json) conforme à l’union T03 | **502**, `invalid_proposal`. Le contrôle séparé du document confirme union valide et branche Python invalide. |
| Proposition portant le champ interdit `validated` | **502**, `invalid_proposal` |
| Autre repas à révision égale, puis même repas à une autre révision | **502**, `invalid_proposal` dans chacun des deux cas |
| Identifiant de corrélation renvoyé différent | **502**, `invalid_correlation` |
| En-têtes reçus, corps suspendu 6 s | **504**, `python_timeout` après **2,013 s** au dernier passage |

Le [contrôle CI local](scripts/verify_t04.py) a terminé avec le code 0. Le rejeu nominal a donné deux propositions identiques et des corrélations distinctes. L’UUID fourni au premier appel et celui généré par Java au second ont été retrouvés dans les deux journaux, sans le texte du repas. Pour les réponses fautives, un [second serveur FastAPI réservé au test](scripts/t04_faults.py) a pris la place du service nominal. Chaque demande a parcouru la liaison HTTP réelle en boucle locale. Le vérificateur arrête les processus qu’il démarre.

**Reproduction locale depuis la racine du dépôt.** Maven 3.9.4 a construit hors ligne avec son JDK 20.0.1. Le JAR ciblant Java 17 a tourné avec Corretto 20.0.2, Spring Boot 3.5.16 et NetworkNT 1.5.1. Python 3.14.7, FastAPI 0.140.0, Uvicorn 0.51.0 et Pydantic 2.13.4 étaient présents dans un environnement existant utilisé en lecture seule avec `-B`. Le chemin peut être remplacé par un interpréteur équipé des [mêmes dépendances](python/requirements.txt). Aucun téléchargement ni installation pour ce contrôle. [Construction Maven](java/pom.xml)

```sh
python3 -B scripts/verify_t04.py
```

La commande Python construit le JAR (`mvn -o -q -f java/pom.xml package`) puis exécute les cas sur deux ports temporaires de `127.0.0.1`. L’environnement Codex a nécessité une permission d’écoute locale. Pour lancer les services manuellement après construction, utiliser deux terminaux à la racine :

```sh
# Terminal Python
python3 -B -m uvicorn app:app --app-dir python --host 127.0.0.1 --port 8104 --no-access-log
# Terminal Java
java -jar java/target/llmsport-t04.jar
```

Depuis un troisième terminal :

```sh
curl -i --max-time 5 -H 'Content-Type: application/json' --data '{"entry_id":"MEAL-001","entry_revision":2,"text":"mon accompagnement"}' http://127.0.0.1:8103/analysis
```

La configuration Compose de T04 a été remplacée par le parcours avec PostgreSQL décrit dans [T09](documentation/p1-verification.md#t09--intégration-compose-et-pannes).

**Effort et apprentissage.** Environ 10 min écoulées pour le lot assisté, de 20 h 42 à 20 h 52, heure de Paris, dont environ 8 min jusqu’au dernier contrôle HTTP. Travail en parallèle, 0 € de dépense externe. L’estimation pédagogique initiale de 6–9 h inclut la pratique autonome, dont la durée reste à mesurer. L’utilisateur a expliqué correctement pourquoi Java doit comparer le couple `(entry_id, entry_revision)` et rejeter `MEAL-002` reçu pour `MEAL-001` sans écrire dans le journal. Le code a été réalisé avec assistance.

## T05 — import du catalogue

Le socle P0/T04 a été publié dans la [PR #1](https://github.com/samuelstefancic/sport-llm/pull/1), fusionnée au commit `7664a77` après rejeu local et revue Codex du commit `320ec94`.

**Vérifié le 18 novembre 2026 dans PostgreSQL 17.12.** L’exercice a établi que 0 g/100 g est une valeur connue, avec son unité, sa base et sa provenance. Si l’autre contribution est inconnue, le bilan attendu est « 0 g de sel — sous-total partiel ». Le calcul du bilan appartient à T06.

L’[importeur de catalogue](catalog/import_catalog.py) est un outil local distinct de FastAPI. Il reçoit les octets du [catalogue fictif](data/dev/catalog.json) dans une table temporaire, vérifie la source, la version, les identifiants, les états, les unités et les valeurs, puis publie les lignes et bascule le pointeur actif dans la même transaction. Un verrou par catalogue sérialise la publication. Le document source est conservé en JSONB et son empreinte porte sur les octets originaux. Le journal des repas reste du ressort de Java. [Schéma PostgreSQL](catalog/schema.sql)

| Contrôle en base | Observation |
|---|---|
| Activation et provenance | `DEMO-FOOD 0.2.0` relu comme actif dans la base locale. 6 aliments, 60 couples aliment/apport, 42 valeurs connues et 18 absentes. SHA-256 source `2ec60064489c0a4ecc4e7fc1865ddb1652c8af73fbc4dc11dfbcb3e793073ef4`. |
| Zéro et absence | Pour une base de 100 g cuits, le riz D01 conserve un sel numérique égal à 0 avec l’état `known`. Le poulet D02 et les courgettes D03 portent SQL `NULL` et `absent`. L’unité reste le gramme dans les trois cas. Une clé omise dans une variante fictive est également restée inconnue. |
| Rejeu et conflit | Même fichier rejoué, toujours 1 version, 6 aliments, 60 apports, 1 pointeur. Une version déjà utilisée avec d’autres octets est refusée. Le rejeu d’une version historique après activation de la suivante conserve la nouvelle version active. |
| Validation | Une cellule étiquetée absente avec une valeur numérique égale à zéro est refusée. L’état publié reste intact. |
| Interruption et reprise | Dans un schéma jetable, une seconde connexion a observé l’import de B bloqué juste avant la bascule, tandis que A restait lisible. Le test a interrompu la session PostgreSQL de l’import. A est restée active, aucune ligne de B n’a été publiée. Une nouvelle tentative a activé B. |

**Reproduction.** Depuis la racine du dépôt avec PostgreSQL démarré en local et un interpréteur équipé de [Psycopg 3.2.13](catalog/requirements.txt), définir `PGHOST` (socket privé ou hôte local), `PGDATABASE` et `PGUSER` pour une base de développement dédiée. Le rôle de test doit pouvoir créer ses schémas et interrompre sa propre session. L’import accepte aussi `DATABASE_URL`. Sur une base nouvellement créée :

```sh
python -B catalog/import_catalog.py --init-schema data/dev/catalog.json
python -B catalog/import_catalog.py data/dev/catalog.json
python -B scripts/verify_t05.py
```

Le premier appel renvoie `activated`, le deuxième `already_imported` avec la même empreinte. Le [contrôle d’intégration](scripts/verify_t05.py) utilise un schéma neuf sur cette même instance et le supprime à la fin. Les variantes fictives de test restent isolées du catalogue actif.

**Ciqual, métadonnées consultées le 18 novembre 2026.** L’Anses publie la *Table de composition nutritionnelle des aliments Ciqual 2025*. Le dépôt Recherche Data Gouv porte la version 1.0 du 19 novembre 2025 et le DOI `10.57745/RDMHWY`. La **Licence Ouverte Etalab 2.0** autorise l’extraction, l’adaptation, la redistribution et l’exploitation commerciale avec mention du producteur et de la date de mise à jour. L’Anses demande d’indiquer la source et la version et de préserver le sens des données. Une future acquisition devra garder les valeurs originales, tracer les transformations et distinguer valeur manquante, trace, borne et zéro. Attribution prévue : Anses, 2025, *Table de composition nutritionnelle des aliments Ciqual*, version 1.0 du 19 novembre 2025. Acquisition et import des données réelles attendent une décision distincte. [Notice officielle](https://doi.org/10.57745/RDMHWY) · [Documentation Anses, §1 et §3.2](https://ciqual.anses.fr/cms/sites/default/files/inline-files/Table%20Ciqual%202025%20doc%20FR_2025_11_19.pdf) · [Licence Ouverte 2.0](https://www.data.gouv.fr/pages/legal/licences/etalab-2-0)

T06 a calculé le cas fictif F02 en décimal à partir du catalogue actif et l’a confronté à l’oracle P0. [Vérification T06](documentation/p1-verification.md#t06--bilan-alimentaire)

## Livraison des chaînes P1

Le [suivi des vérifications T06 à T09](documentation/p1-verification.md) consigne les commandes, résultats et exercices. La [livraison T09](documentation/p1-verification.md#t09--intégration-compose-et-pannes) donne la reproduction du parcours Compose et du workflow **Vérifications P1**. La PR T09 porte le bilan final de livraison. Le [protocole T10](documentation/p2/baseline.md) fixe la mesure locale et le contenu des preuves.
