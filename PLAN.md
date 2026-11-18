# llmSport — plan de réalisation et de reprise

Version 1.0 · 17 novembre 2026. Les charges sont des estimations intégrées et les critères futurs sont des attendus. [PROJECT.md](PROJECT.md) porte les décisions retenues et l’état du projet. [AGENTS.md](AGENTS.md) porte les règles de travail. Ce plan détaille leur exécution.

## Décision et état de départ

**P0 clôturé. T09 porte les vérifications finales de P1.** L’état des contrôles locaux et de la CI est tenu dans les [vérifications P1](documentation/p1-verification.md#t09--intégration-compose-et-pannes). T10 attend son GO. RAG-01 est prévu en fin de P2.

| Élément | État vérifié | Preuve ou limite |
|---|---|---|
| T01, T02, T03 | P0 clôturé, 3 tickets terminés | Raisonnement sur le repas et les révisions, 30 cas fictifs dont 15 alimentaires, 10 sportifs et 5 mixtes/ambigus. 10 oracles de calcul et 10 d’ambiguïté figurent dans ce jeu de développement. [Bilan P0](documentation/p0-verification/rapport.md) · [Cas](data/dev/cases.json) · [Oracles](data/dev/oracles.md) |
| Contrat | Version 0.1.0 exercée sur les cas fictifs | 25 exemples exécutés par le vérificateur, dont 14 conformes et 11 rejetés. La frontière HTTP et les courses du journal en PostgreSQL sont vérifiées en P1. [Schéma](contracts/analysis.schema.json) · [Sémantique](contracts/analysis.md) · [Vérifications P1](documentation/p1-verification.md) |
| Skills | 7 présents, 21 scénarios fictifs évalués et 30 réponses avec rejeux | Le routage implicite a été observé pour `sn-plan-contracts` dans un essai isolé. [Preuves des skills](documentation/verification-skills-2026-11-17/rapport.md) · [Compte rendu du routage](documentation/p0-verification/rapport.md) |
| Réalisation | P0 clôturé, P1 en vérification finale sur T09 | Échange Spring Boot → FastAPI, catalogue fictif, calcul du repas, journal sportif et contrôles transactionnels vérifiés. T09 vérifie l’ensemble via Compose et fournit la CI manuelle. |
| RAG-01 | Cadrage prêt, tests préparés | 3 articles, 17 passages, 8 questions de recherche et 11 cas de synthèse. La [fiche RAG-01](documentation/RAG-01.md) porte le registre des passages, les corrigés et le barème. Le lot attend sa décision de lancement en fin de P2. |

## Produit et responsabilités

1. Angular fournit la saisie des repas et séances, la clarification, la correction, la sélection des apports, l’historique et l’explication des résultats. L’API HTTP suffit à démontrer la première chaîne en P1.
2. Java/Spring Boot possède l’API métier, les autorisations, le contrôle des révisions, l’idempotence, les règles de calcul, les corrections et les écritures. Il vérifie l’origine de Python et sa réponse contre la seule branche `python_proposal`. Il recalcule les valeurs depuis le catalogue, même si le modèle suggère une référence.
3. Python/FastAPI interne propose des extractions structurées et des clarifications, puis porte l’inférence, les expériences PyTorch et la recherche documentaire. Il ne dispose d’aucun chemin d’écriture dans le journal. Le service garde un seul adaptateur IA en P2 et délègue les écritures du journal à Java.
4. PostgreSQL conserve le journal, ses révisions, les résultats et le catalogue versionné. Les imports préparent puis valident une version avant de l’activer atomiquement. Le corpus lexical de RAG-01 aura ses propres tables ou son propre schéma, avec une provenance documentaire distincte des données nutritionnelles.
5. Un seul bilan par repas et révision. Énergie, protéines, glucides et lipides sont proposés par défaut. L’utilisateur peut sélectionner fibres, sucres, sel, vitamines et minéraux connus du catalogue. Chaque ligne porte identifiant, unité, valeur ou sous-total, statut, sources et manques. Un zéro explicite reste connu. Une valeur absente reste inconnue. Les quantités déclarées et les corrections sont traçables. P1 expose les statuts par API, P4 les rend sélectionnables dans l’interface.
6. Le journal sportif conserve durée, distance, séries, répétitions et charge déclarées, avec leurs unités. Une conversion exige des données suffisantes. Les données nutritionnelles et sportives restent distinctes dans une entrée mixte.

Le périmètre initial couvre le journal francophone, local et explicable. Photos, prescription, coaching médical, calories d’activité personnalisées, connecteurs, agents autonomes et Kubernetes sont hors MVP. Le moteur local et l’API distante sont des configurations explicites, avec leurs propres conditions d’accès.

## Charges, budget et dates

Les fourchettes de base du plan P0–P7 viennent de la version opérationnelle du chat principal (**449–649 h** avant ajustements). Les ajouts adoptés sont **+2–4 h en P0** pour le lot complet des skills, **+10–16 h pour PyTorch** réparties sur P2 et P4, et **+15–24 h** pour RAG-01 sur décision distincte en fin de P2. Les heures d’apprentissage, de code, de tests, de correction et de preuve figurent dans les mêmes lots. Les **35–55 h d’AWS** sont comprises dans P7. P5 inclut déjà l’adaptation supervisée.

| Jalon | Charge du jalon | Cumul depuis P0 hors RAG | Cumul si RAG autorisé | Enveloppe de conception |
|---|---:|---:|---:|---:|
| P0 — socle clôturé | 10–16 h | 10–16 h | 10–16 h | 0 € |
| P1 — première chaîne locale | 36–52 h | 46–68 h | 46–68 h | 0 € additionnel |
| P2 — première inférence | 30–46 h + RAG éventuel | 76–114 h | 91–138 h | 0–10 € |
| P3 — laboratoire Azure | 32–48 h | 108–162 h | 123–186 h | 15–40 € |
| P4 — MVP | 88–122 h | 196–284 h | 211–308 h | 0–20 € |
| P5 — adaptation supervisée | 70–100 h | 266–384 h | 281–408 h | 0–60 € |
| P6 — serving et benchmarks | 80–120 h | 346–504 h | 361–528 h | 20–100 € |
| P7 — exploitation et AWS | 115–165 h | **461–669 h** | **476–693 h** | 30–100 € |

- **Reste à réaliser après P0.** 451–653 h hors RAG ou 466–677 h avec RAG. Avec une réserve de 25 % et un arrondi supérieur à l’heure, l’enveloppe totale depuis P0 est de 577–837 h hors RAG ou de 595–867 h avec RAG. Le temps assisté observé en P0 figure dans ses rapports. Le temps d’appropriation de l’utilisateur reste à mesurer.
- **Repères à 10 h par semaine à partir de P1.** Démo locale en 4–6 semaines, MVP en 19–27 semaines hors RAG ou 21–30 avec, parcours complet en 46–66 semaines hors RAG ou 47–68 avec. Créneaux réels, temps d’attente et autorisations restent à confirmer. Recaler les estimations après T04 et T06 à partir des heures observées.
- **Dépenses expérimentales.** 65–330 € d’enveloppes historiques de conception, hors matériel et électricité. RAG local est prévu à 0 € de dépense externe additionnelle. Les enveloppes supposent des laboratoires temporaires et ne valent ni tarifs vérifiés ni autorisation de dépense. Budget externe actuellement autorisé par ce plan **0 €**. Pour une campagne payante, chiffrer au moment de la décision modèle/service/région, ressources et durée, volumes, retries, stockage, logs, réseau, nettoyage, marge et seuil d’arrêt. Séparer les crédits OpenAI, Azure et AWS.

## P0 — preuves de clôture

| Ticket ou lot | Ventilation indicative de l’enveloppe | Livrable réalisé et reprise |
|---|---:|---|
| T01 | 1–2 h | Repas fictif corrigé de 150 g à 100 g de riz et qualification du bilan multi-apports. Règle transactionnelle r1/r2 explicitée. Rejouer les cas de référence dans T06 et T08 avec l’application. |
| T02 | 3–4 h | Corpus de développement, catalogue fictif et oracles relus. Figer la version utilisée pour les tests P1/P2 et garder le futur test final indépendant. |
| T03 | 4–6 h | Schéma, sémantique, exemples et rapport de validation. Appliquer les preuves à l’implémentation sans réouvrir le jalon de cadrage. |
| Lot des skills | 2–4 h | Sept skills disponibles au niveau du projet, vérification de structure, découverte et scénarios. |

Les fourchettes T01–T03 répartissent les 8–12 h de base à titre indicatif. Les fenêtres assistées chronométrées étaient de **11 min 58 s** pour la finalisation T02/T03 et de **12 min 41 s** pour le lot des skills, selon des périmètres décrits dans les rapports de preuve. Elles ne mesurent pas le travail complet ni l’apprentissage.

## P1 — chaîne locale déterministe

**Entrée du jalon.** P0 clôturé et GO local. L’ordre retenu était T04 → T05 → T06 → T07 → T08 → T09. Les chemins d’application sont `java/`, `python/` et `catalog/`.

| Ticket | Charge | Dépendance | Réalisation, exercice et preuve de sortie |
|---|---:|---|---|
| **T04 — frontière Java/Python** | **6–9 h** | P0 + GO | Appel HTTP réel Spring Boot → FastAPI interne avec réponse déterministe, corrélation, délai et validation de branche. Définir l’enveloppe HTTP minimale par-dessus le schéma canonique de réponse. Préparer le démarrage local reproductible avec Compose et le contrôle CI sans appel distant. Exercice unique sur le rôle de la validation à la frontière. Prouver une proposition acceptée, un message mal formé rejeté et un rapport Java renvoyé par Python rejeté malgré sa validité dans l’union. |
| T05 — catalogue et import | 6–9 h | T04 | Charger d’abord un catalogue de développement existant. Examiner version, droit d’usage et métadonnées d’un extrait Ciqual avant acquisition. Importer en zone de préparation, valider, activer atomiquement et tracer source, unité, état cru/cuit, version et empreinte. Exercice sur la différence absence/zéro. Tester rejeu, absence préservée et interruption laissant la version active intacte. Si l’extrait réel est bloqué, démontrer le mécanisme sur le fictif et signaler la provenance réelle restante. |
| T06 — chaîne alimentaire | 7–10 h | T05 | Parser des cas bornés, lever une ambiguïté quand quantité/unité ou correspondance manque, calculer en décimal à partir des références, persister puis relire. Exercice sur la composition des lignes par apport. Prouver F02, le repas corrigé T03-SEL-001 et le maintien des inconnues lorsque la donnée manque. |
| T07 — chaîne sportive | 4–6 h | T04 puis démonstration T06 | Produire, enregistrer et relire durée, distance, séries, répétitions et charge quand elles sont explicites. Exercice sur la dimension d’une unité. Prouver S01, S03 et S06, plus rejet d’une unité incohérente et absence d’énergie inventée. |
| T08 — corrections et idempotence | 7–10 h | T06 et T07 | Mettre à jour la révision et enregistrer l’historique. En base, comparer la révision analysée à la courante et rendre la vérification atomique avec l’écriture du bilan, par verrou effectif ou opération conditionnelle. Exercice sur l’ordre des deux transactions. Tester retour tardif, course correction/analyse, deux appels concurrents sur la même clé, rejeu identique et conflit de contenu. |
| T09 — intégration et pannes | 6–8 h | T04–T08 | Exécuter un parcours repas et un parcours sport de bout en bout via Compose et faire tourner les vérifications applicatives via la CI prévue. Exercice sur le diagnostic par corrélation. Provoquer indisponibilité Python, réponse invalide et duplication. Prouver un état explicite, des journaux corrélés sans texte brut et l’absence de double écriture. |

**Contrôles métier minimaux.**

- F02 attend **415 kcal, 42,5 g de protéines, 46 g de glucides, 4,3 g de lipides**, tous complets. Le catalogue est fictif.
- T03-SEL-001 attend **34,5 g de protéines complètes, 295 kcal partielles, 0 g de sel partiel avec deux contributions manquantes**, glucides et lipides indéterminés. Conserver le riz à 100 g et utiliser la variante de catalogue associée à ce cas.
- S01 attend **30 min** à partir de 20 + 10 minutes. S03 attend **30 répétitions** sur 3 × 10, avec 40 kg déclarés conservés. S06 préserve 30 minutes et demande l’unité du nombre 5.
- T03-STALE-001 attend `stale_revision` et **0 écriture de la réponse r1** quand le repas est déjà en r2. Un résultat de r1 peut être structurellement valide. Un conflit de clé idempotente avec un contenu différent renvoie un conflit explicite, prévu en HTTP 409. Le rejeu d’une réponse ancienne n’altère ni la dernière correction ni le bilan courant. [Scénario de révision](contracts/examples/revision-scenario.json)

**Sortie P1.** 6/6 tickets vérifiés dans leur périmètre, au moins 1 entrée alimentaire et 1 sportive persistées puis relues, 1 ambiguïté correctement signalée, tests du contrat et de concurrence réellement exécutés. La démonstration associe des résultats à leur source versionnée et indique si elle utilise le catalogue fictif. Livrer les commandes de reproduction, les tests et leurs résultats, les versions et les limites de la CI. Ce point rend le produit local démontrable après **36–52 h de travail P1**.

## P2 — première inférence, évaluation et RAG

**Entrée.** Après démonstration de P1, instrumenter d’abord la baseline déterministe (T10). Avant de développer l’adaptateur de T11, comparer les deux candidats locaux **Qwen3-0.6B** et **Qwen3-4B** avec la baseline, sur les mêmes cas fictifs en français, avec prompt et budget de sortie figés. Les essayer dans un banc local minimal en P2. [Fiche Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) · [Fiche Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B)

Pour chaque candidat, consigner révision exacte, modèle de base, tokenizer, quantification et licence applicable aux poids utilisés. Sur le Mac, vérifier que le modèle tient en mémoire à la longueur de contexte retenue, puis relever pic mémoire, latence par requête et coût observé. Comparer la justesse de l’extraction française, la gestion des quantités inconnues et des ambiguïtés ainsi que la proportion de sorties valides contre la branche T03. Documenter erreurs et dénominateurs. **Retenir au plus un modèle initial** pour T11 à l’issue de cette comparaison. Si aucun ne satisfait la licence, les ressources disponibles et les critères qualité fixés en T10, garder la baseline et documenter la décision. Le choix et les essais appartiennent à P2. MLX-LM ou Ollama peuvent assurer l’inférence locale. PyTorch reste prévu pour l’apprentissage de l’entraînement.

| Ticket | Charge | Dépendance | Réalisation et preuve de sortie |
|---|---:|---|---|
| T10 — baseline instrumentée | 8–12 h | P1 | Figer les 30 cas de développement, leur version, les cas réellement exécutables et les métriques avant exécution. Tracer deux runs reproductibles de la baseline avec MLflow, résultat par cas, temps, erreurs et versions. Exercice sur run, métrique et artefact. |
| T11 — premier adaptateur de modèle | 12–18 h | T10 | Une configuration d’inférence bornée produit une sortie structurée validée. Tracer délai global, erreurs et nombre de tentatives. Python possède les retries fournisseur. Partir de 2 tentatives max comme proposition à confirmer dans le ticket et vérifier que Java et le SDK ne les multiplient pas. Exercice sur validation de forme et de sens. Tester sortie invalide, timeout et fournisseur indisponible par double contrôlé ou service autorisé. |
| T12 — première comparaison | 8–12 h | T11 | Sur les mêmes cas, comparer règles et modèle préentraîné. Mesurer exactitude, précision automatique, couverture, clarifications, abstentions, erreurs, latence métier P50/P95 et ressources observables. Fournir run IDs, paramètres, jeux et empreintes, version modèle/tokenizer/prompt, matériel, métriques et cas échoués. Exercice sur les dénominateurs. |
| T13 — diagnostic PyTorch et tenseurs | 2–4 h | P1 + environnement compatible | Noter Python et PyTorch disponibles, réaliser un petit exercice de formes, types et device, produire les dimensions attendues et observées. Comparer un calcul simple sur CPU et accélérateur si disponible. Expliquer une incompatibilité de forme ou de device à partir d’une trace. |
| RAG-01 — pilote lexical en fin de P2 | 15–24 h | Première inférence exploitable + évaluation traçable + GO distinct | Reprendre la [fiche RAG-01](documentation/RAG-01.md). Les 4 postes sont textes et manifeste **3–5 h**, recherche PostgreSQL **4–6 h**, synthèse avec citations **4–6 h**, deux passes et analyse MLflow **4–7 h**. Le registre de la fiche détaille chaque passage stable et les substitutions autorisées. |

**Sortie du cœur P2.** Baseline et premier modèle comparés en conditions déclarées, au moins deux runs versionnés et résultats traçables jusqu’à une entrée validée par Java. Indiquer ce qui est local, simulé, mesuré ou non observable. RAG-01 attend son créneau de fin de P2. Le report du pilote peut être consigné comme tel pour avancer sur le cœur du parcours.

**Sortie du pilote, au moment prévu.** Figer 3 textes, versions, empreintes, droits et correspondance segments–IDs avant les mesures. Exécuter Q1–Q8 en recherche. Le score exige 7/8 dans le top 5, dont Q3 et Q8. Exécuter les 11 cas de synthèse avec passages de référence puis retrouvés, soit 22 évaluations réparties sur deux passes. Appliquer les critères de couverture, de fidélité, de citations, d’abstention et de contrôle Q10 de la fiche. Les erreurs observées détermineront l’intérêt d’une comparaison ultérieure avec des embeddings.

## P3 — premier laboratoire Azure

| Lot | Charge | Dépendance | Réalisation et preuve de sortie |
|---|---:|---|---|
| P3.1 — préparation Azure | 10–15 h | Cœur P2 | Préparer 1 environnement temporaire, Terraform versionné, identité et accès, dimensionnement et coût détaillé. Exercice sur l’identité de déploiement. Vérifier le plan d’infrastructure et le manifeste de release avant application. |
| P3.2 — déploiement contrôlé | 12–18 h | P3.1 + campagne autorisée | Déployer une version immuable, exécuter 2 smoke tests métier et vérifier accès, traces et comportement du service interne depuis l’environnement prévu. Exercice sur un écart entre test local et vérification après déploiement. |
| P3.3 — incident, repli et nettoyage | 10–15 h | P3.2 | Reproduire 1 incident simple, diagnostiquer depuis les traces, vérifier 1 retour applicatif compatible avec les entrées créées depuis et nettoyer les ressources du laboratoire dans le périmètre autorisé. Exercice sur le lien entre une révision applicative et le schéma de base. |

**Sortie P3.** Première preuve de portfolio avec repas et sport, ambiguïté, calcul sourcé, évaluation rejouable, accès contrôlé, 1 incident expliqué, repli compatible et preuves de nettoyage. Un exercice simulé est consigné comme simulation si le déploiement est reporté.

## P4 — MVP utilisable et évaluation renforcée

| Lot | Charge | Dépendance | Réalisation et preuve de sortie |
|---|---:|---|---|
| P4.1 — parcours et historique | 24–32 h | P3 | Compléter clarifications, corrections, historique par révision et agrégations descriptives, autorisations comprises. Exercice sur une correction qui change le résultat sans effacer la provenance. Vérifier une entrée alimentaire, une sportive et une mixte. |
| P4.2 — interface Angular minimale | 24–34 h | P4.1 + contrat P1 | Saisie, restitutions, sélection des apports et détail des sources/manques. Tester les 3 statuts, le zéro connu, la valeur nulle et le sous-total à zéro, unités comprises. Exercice sur un état que le frontend doit restituer à l’identique. |
| P4.3 — données et qualité | 18–26 h | P2 et parcours P4 | Versionner le corpus enrichi, règles d’annotation et groupes anti-fuite. Cible à confirmer pour le test final produit : 60 cas, dont 30 alimentaires, 20 sportifs et 10 mixtes/ambigus. Sceller le sous-ensemble alimentaire destiné à l’expérience P5. Les tests d’intégration P4 et le réglage s’appuient sur des jeux distincts. Exercice sur une paraphrase qui doit rester dans le même groupe. |
| P4.4 — validation du MVP | 14–18 h | P4.1–P4.3 | Rejouer les parcours interface–Java–Python, vérifier rattachement des sources, autorisations, corrections, métriques par catégorie et reproductibilité. Produire une démo du journal local. Exercice de lecture d’un rapport par cas. |
| P4.5 — boucle manuelle PyTorch | 8–12 h | T13 | Construire un petit exercice pédagogique avec Dataset/DataLoader, forward, perte, backward, optimiseur, sauvegarde et rechargement. Proposer une variante à refaire, enregistrer résultat attendu, observé et ressources. |

**Sortie P4.** MVP local démontrable avec nutrition, sport, clarifications, correction, historique, sélection des apports et preuves de validation. Le jeu de test final reste hors réglage, et le petit modèle PyTorch reste un exercice pédagogique.

## P5 — adaptation supervisée

| Lot | Charge | Dépendance | Réalisation et preuve de sortie |
|---|---:|---|---|
| P5.1 — protocole et données | 18–26 h | P4 | Retenir 1 tâche initiale : description alimentaire française vers ingrédients, quantités liées, préparation et manques. Chiffrage de départ à confirmer après échantillonnage : 120–180 exemples d’entraînement et 30–40 de validation, séparés du test final. Versionner provenance, partitions groupées et oracles indépendants. Fixer métriques, effectifs et règles de promotion avant de voir le test final. Exercice sur la différence validation et test final. |
| P5.2 — faisabilité PyTorch | 16–22 h | P5.1 + T13/P4.5 | Tester compatibilité, mémoire, poids, gradients, optimiseur et activations, avec un essai avant/arrière autorisé. PyTorch/Transformers, PEFT/LoRA si compatible. Documenter matériel, device, versions, budget et repli explicite. Exercice sur les paramètres réellement mis à jour. |
| P5.3 — entraînement | 22–32 h | P5.2 + autorisation d’exécution applicable | Exécuter une adaptation supervisée traçable, avec seed, configuration, courbes, checkpoints, durée, consommation observable et erreurs. Recharger le checkpoint prévu et prouver qu’il répond au format attendu. Exercice sur la lecture d’une courbe train/validation. |
| P5.4 — évaluation finale | 14–20 h | P5.3 | Comparer 3 candidats sur le jeu indépendant de la tâche : règles, préentraîné avec prompt figé, même modèle adapté. Contrôler tokenizer, temps de réponse et quantification. Documenter résultat par catégorie, cas critiques et décision de promotion ou rejet. |

**Sortie P5.** Une expérience réellement exécutée, comparaison reproductible et décision argumentée. Un candidat rejeté peut satisfaire l’objectif d’apprentissage. Sans matériel, données ou autorisation nécessaires, l’exécution est à replanifier avec une estimation distincte.

## P6 — serving et benchmarks

| Lot | Charge | Dépendance | Réalisation et preuve de sortie |
|---|---:|---|---|
| P6.1 — protocole de charge | 16–24 h | P5 et mesures P2 | Définir charge, concurrence, longueur de contexte, traitement des timeouts, chauffe, cache et critères d’arrêt. Exercice sur TTFT, TPOT et latence du résultat complet. Cible de départ pour un scénario utile : 2 répétitions de 100 requêtes documentées, à confirmer avec les moyens impartis. |
| P6.2 — campagne locale | 22–34 h | P6.1 | Mesurer au moins 1 niveau nominal et 1 niveau de charge supérieur sur Mac, comparer deux réglages à facteur isolé si réalisable, traiter contexte, quantification, concurrence, mémoire et saturation. Conserver mesures fiables et erreurs. |
| P6.3 — laboratoire GPU | 28–42 h | P6.2 + GPU compatible et campagne autorisée | Monter une session vLLM bornée. Mesurer charge, cache, débit, mémoire, temps et coût par résultat utile. Une référence API éventuelle se compare au niveau produit dans une campagne autorisée. |
| P6.4 — synthèse et décision | 14–20 h | P6.2 et P6.3 pour le bilan complet | Distinguer comparaison produit et comparaison moteur. Publier matériel, poids, tokenizer, quantification, charge, répétitions, erreurs, métriques et limites. Expliquer la différence entre goodput de serving et débit métier utile. |

**Sortie P6.** Recommandation fondée sur la campagne locale et le benchmark GPU effectivement mesuré. Si le GPU est reporté, publier le volet local et conserver le verdict GPU comme non exécuté.

## P7 — exploitation, reprise et AWS

| Lot | Charge | Dépendance | Réalisation et preuve de sortie |
|---|---:|---|---|
| P7.1 — promotion et releases | 25–35 h | P6 | Lier artefacts immuables, rapport qualité, versions contrat/catalogue/modèle/prompt et compatibilité des migrations. Exercice sur la décision de promotion. Réaliser 1 promotion contrôlée et 1 repli applicatif vérifié, selon autorisation. |
| P7.2 — workflows et incidents | 30–45 h | P7.1 | Pour imports et évaluations, persister états, empreintes, tentatives, deadline et annulation. Démontrer reprise d’un traitement interrompu, absence de doublon et impossibilité pour une tentative annulée de publier. Introduire baux ou protection d’exécutant uniquement en cas de nécessité. |
| P7.3 — restauration | 25–30 h | P7.1 | Définir RPO/RTO avant test. Effectuer 1 exercice de restauration autorisé, enregistrer les valeurs observées et valider le scénario de préservation des écritures post-déploiement lors d’un rollback applicatif. Exercice sur la différence entre rollback de code et restauration de données. |
| P7.4 — atelier AWS | 35–55 h | P7.1–P7.3 + budget AWS autorisé | Porter 1 tranche existante, comparer identité, déploiement, logs, exploitation et coût avec Azure. Démontrer 1 smoke test et vérifier le nettoyage. Documenter écarts de portabilité et compromis. |

**Sortie P7.** Socle pédagogique complet lorsque promotion, reprise, restauration et atelier AWS ont des preuves d’exécution. Livrer dossier de démonstration, résultats, incidents, limites et commandes de reproduction. La mesure locale, le laboratoire Azure et l’atelier AWS restent identifiables dans les preuves.

## Critères transverses et pilotage

- **Contrats et provenance.** La suite critique exige 100 % des résultats produits reliés aux sources et aux transformations testées, 0 ambiguïté critique acceptée comme certaine, 0 écriture non autorisée ou obsolète et tous les tests obligatoires réussis. Les métriques portent sur les cas testés.
- **Évaluation.** Publier corrects/total, corrects parmi les acceptés automatiquement/acceptés, et acceptés/éligibles. La précision est indéfinie si aucune réponse n’est acceptée. Clarifications, abstentions et erreurs sont conservées. Les objectifs historiques 95 % de précision automatique, 70 % de couverture non ambiguë, P95 métier ≤ 5 s après chauffe et erreurs techniques < 1 % à charge nominale sont à calibrer avant comparaison finale.
- **Mesures de serving.** Le délai métier se termine au résultat validé. TTFT se mesure au premier contenu utile lorsque le streaming est capturable. Publier les effectifs et les timeouts. Le coût utile divise le coût de l’ensemble des tentatives par le nombre de résultats corrects utiles. Préciser les métriques indisponibles chez le fournisseur et les effectifs insuffisants pour les percentiles extrêmes.
- **Protection et fiabilité.** Utiliser des fixtures fictives, masquer le texte brut et les secrets dans les traces, propager un identifiant de corrélation, borner délais et retries et empêcher les écritures doubles en base. Une protection métier n’implique aucune garantie de facturation unique d’un fournisseur. CI déterministe sur les changements puis campagnes et déploiements déclenchés selon les autorisations applicables.
- **Risques qui changent le calendrier.** Catalogue réel et droit d’usage en T05, outillage local en T04, RAM/disque/accélération en P2 et P5, taille et indépendance du jeu final en P4/P5, accès/région/budget en P3/P6/P7. Les contournements locaux explicites servent à débloquer les exercices et gardent le résultat réel reporté visible.

### Correspondance avec le plan J0–J10

| Ancien jalon | Reprise dans le parcours actuel |
|---|---|
| J0 — Cadrage | P0 |
| J1 — Données et contrats | P0–P1, P4 pour le corpus et P5 pour l’adaptation |
| J2 — Métier déterministe | P1, parcours complets en P4 et reprise en P7 |
| J3 — Extraction et interface | P2 pour l’inférence, P4 pour Angular |
| J4 — Évaluation | P2, enrichissement P4, expériences P5–P6 |
| J5 — Recherche et adaptation | Pilote lexical en fin de P2 sur décision distincte, adaptation en P5 |
| J6 — Inférence locale/API | Première mesure P2, approfondissement P6 |
| J7 — MLOps et CI/CD | CI P1, MLflow P2, livraison P3, entraînement P5, promotion P7 |
| J8 — Azure | Premier laboratoire P3, consolidation et atelier AWS P7 |
| J9 — Observabilité et incidents | Logs P1, incident P3, saturation P6, restauration P7 |
| J10 — GPU et portfolio | Première preuve en P3, GPU P6, dossier complet P7 |

## Reprendre dans un nouveau contexte

1. Ouvrir [AGENTS.md](AGENTS.md), [PROJECT.md](PROJECT.md) et la section de ce plan correspondant au prochain ticket. Vérifier l’état du workspace et consulter seulement la preuve de sortie du ticket précédent et le contrat concerné. À la rédaction, aucun dépôt Git n’a été détecté depuis la racine du workspace. Revalider le chemin et l’état avant de prévoir une opération Git.
2. Retrouver la dernière autorisation explicite et sa portée. Par défaut, partir d’un jalon prévu. Avant une installation, un entraînement, une ressource cloud, un appel payant, une publication ou une action destructive, vérifier que l’autorisation couvre le périmètre, les limites et les coûts. Un GO T04 couvre la seule tranche locale décrite.
3. Choisir la skill utile et ouvrir son `SKILL.md`. Pour cadrer un ticket, [sn-plan-contracts](.agents/skills/sn-plan-contracts/SKILL.md). Pour code et apprentissage, [sn-build-and-learn](.agents/skills/sn-build-and-learn/SKILL.md). Selon le besoin, [provenance](.agents/skills/sn-data-provenance/SKILL.md), [évaluation](.agents/skills/sn-evaluate-models/SKILL.md), [benchmarks](.agents/skills/sn-benchmark-inference/SKILL.md), [exploitation](.agents/skills/sn-platform-ops/SKILL.md) ou [revue de preuves](.agents/skills/sn-review-evidence/SKILL.md).
4. Commencer par un comportement observé et un exercice bref. Enchaîner notion, tentative de l’utilisateur, observation, correction, variante et preuve. En navigateur, privilégier lecture, conception et revue. Sur le Mac personnel, exécuter le code, les mesures et les opérations autorisées. Distinguer réalisé avec aide, refait seul et expliqué sans support.
5. À la fin du ticket, tenir le point de reprise dans le suivi existant. Consigner état du ticket, période et effort observé, fichiers touchés, commande exacte, résultats et chemin des preuves, limites, autorisation consommée ou à obtenir, risque restant et prochaine action. Séparer préparé, exécuté, évalué, déployé et vérifié après déploiement. Un contrôle non exécuté garde ce statut.

## Message de démarrage à copier dans le chat principal

> **GO P1 — T04 uniquement, en local, pour une tranche estimée à 6–9 h et 0 € externe.** Reprends [PLAN.md](PLAN.md), [PROJECT.md](PROJECT.md), [AGENTS.md](AGENTS.md) et le [contrat T03](contracts/analysis.md). P0 est clôturé.
>
> Vérifie d’abord le workspace et l’outillage déjà disponible. Commence par un exercice court sur la validation à la frontière Java/Python. Puis réalise le plus petit échange HTTP réel Spring Boot → FastAPI interne, avec une proposition déterministe, un identifiant de corrélation et un délai borné. Java valide la branche `python_proposal`. Prouve une proposition acceptée, une réponse mal formée rejetée et le rejet d’un rapport Java renvoyé par Python. Prépare un démarrage reproductible et la première vérification CI locale sans appel distant. Si un prérequis manque, indique le point précis et poursuis les contrôles indépendants dans le périmètre autorisé.
>
> Clôture cette tranche avec les fichiers, versions, commandes, résultats réellement observés, temps passé et une seule prochaine action vers T05. RAG-01 reste prévu en fin de P2 avec sa fiche et son barème actuels.
