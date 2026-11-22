# llmSport — règles communes

Pour démarrer ou reprendre un lot, suivre le [guide de reprise](documentation/reprise.md). Il indique où vérifier l’état réel, comment attribuer le lot et quelle procédure lire.

## Projet et responsabilités

- Conserver la progression P0–P7 et l'architecture Angular minimal, Java/Spring Boot, Python/FastAPI interne, PostgreSQL. Le suivi minimal est dans [PROJECT.md](PROJECT.md).
- Java possède validation métier finale, calculs déterministes multi-apports, corrections, concurrence et écritures du journal. Python propose des extractions et assure expériences/entraînement/inférence ; il n'écrit pas directement dans le journal.
- Un repas a un bilan unique ; chaque apport sélectionné conserve valeur ou sous-total, unité, statut, sources et manques. Une absence n'est pas zéro. Les règles détaillées et le premier cas T03 sont dans PROJECT.md.
- Distinguer déclaration utilisateur, référence de catalogue, transformation déterministe et proposition du modèle. Conserver provenance, version, unités, état cru/cuit et correction ; ne pas inventer quantité ou conversion.

## Exécution et preuves

- Suivre le périmètre autorisé dans la conversation ; une autorisation déjà donnée reste valable. Une skill ne confère aucun droit technique.
- Avant installation de dépendances, entraînement, appel externe payant, ressource cloud, exposition publique ou action destructive, vérifier que l'autorisation couvre l'action et ses bornes. Ne pas redemander pour une vérification locale déjà autorisée. Pas de repli distant silencieux ni de modification des autres projets.
- Séparer préparé, exécuté, évalué, déployé et vérifié après déploiement. Donner commandes/artefacts et limites ; NOT_RUN n'est pas PASS. Marquer les données et résultats simulés.
- Ne conserver ni secrets ni données personnelles réelles dans les fixtures et traces. Une revue textuelle ne prouve ni le confinement du runtime ni le comportement en production.
- Garder le suivi minimal ; créer un document uniquement pour un besoin concret. L'ébauche v0.1 reste une source historique de propositions, pas une collection de fichiers présumés existants.

## Apprentissage et procédures

- En français, une notion et une question à la fois. Laisser une tentative, puis indices et correction ; expliquer le flux des données avec des repères Java/Python si utiles. Distinguer code assisté et compréhension démontrée.
- Conserver la progression PyTorch et la comparaison baseline/modèle préentraîné/même modèle adapté ; l'intégration au produit dépend des résultats. MLX-LM n'est pas PyTorch.
- Utiliser la seule procédure utile dans `.agents/skills/` : `sn-plan-contracts` (attendu), `sn-data-provenance` (origine), `sn-build-and-learn` (exercice/patch), `sn-evaluate-models` (qualité), `sn-benchmark-inference` (ressources/performance), `sn-platform-ops` (exploitation), `sn-review-evidence` (affirmations/preuves). Les procédures détaillées restent dans leurs SKILL.md ; ne pas les invoquer toutes par défaut.
- Pour une livraison déléguée demandée par l’utilisateur, utiliser `sn-orchestrate-delivery`. Pour une décision de clôture fondée sur une revue indépendante du jalon fusionné, utiliser `sn-review-handoff`.
- Pour chaque demande de l’utilisateur sur llmSport, le pilote lance en parallèle un vérificateur GPT‑6.2 Sol avec l’effort Low. Il lui donne un contrôle précis, la référence du code et les preuves à lire. Le mandat du vérificateur se termine au contrôle confié.
