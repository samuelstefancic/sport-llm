---
name: sn-review-handoff
description: "Relire une passation llmSport dans un contexte indépendant et auditer un jalon livré à partir du code fusionné, des oracles, des tests et des preuves GitHub. Utiliser pour une décision de clôture ou de passage au jalon suivant."
---

# Revoir une passation llmSport

Cette procédure complète la revue de preuves ordinaire pour les livraisons multi-tickets. Le réviseur décide si le jalon est clôturable sur un SHA précis. Il travaille en lecture seule, avec rejeu isolé si les outils et le mandat le permettent.

1. Lire la passation et prouver sa cible. Relever l’URL du dépôt, le SHA complet livré, le `main` distant et l’état du checkout. Si `main` a avancé, auditer le SHA désigné et expliquer la relation avec la tête actuelle. Lire les règles, le plan, le suivi, le contrat, les tests et les oracles de cette révision. Utiliser la passation comme index de recherche et recouper ses affirmations.
2. Charger le [format des preuves](references/evidence-format.md). Pour chaque ticket, vérifier PR, branche de base, tête finale, revue Codex sur cette tête, commit de fusion et présence dans l’historique audité. Comparer le diff réellement fusionné aux critères applicables. Un commentaire du bot peut prouver la revue si son statut et son SHA sont explicites. Un commentaire demandant la revue ne prouve que la demande.
3. Chercher les essais probants. Relier une exécution au SHA, à la commande, à l’environnement, au code de sortie et au résultat attendu. Distinguer validation statique, test local, CI hébergée, démarrage Compose et vérification intégrée après fusion. Lorsqu’un écart change le verdict et que le rejeu est possible, isoler le contrôle des instances de travail.
4. Pour P1, ouvrir la [grille P1](references/p1-review.md). Tester au moins un contre-exemple par invariant critique lorsque les preuves le permettent. Prioriser les écritures sur une mauvaise révision, la duplication et la transformation d’une inconnue en zéro.
5. Si le producteur a fourni le manifeste P1, lancer le [vérificateur de manifeste](scripts/check_handoff.py) depuis la racine du projet avec `python3 -B .agents/skills/sn-review-handoff/scripts/check_handoff.py CHEMIN_DU_MANIFESTE --repo CHEMIN_DU_CHECKOUT`. Ce contrôle vérifie la cohérence du manifeste et l’ascendance Git locale. Vérifier séparément la vérité des liens, les résultats des tests et les faits GitHub.
6. Rendre un seul verdict daté sur le SHA audité. Donner le tableau **Ticket / Critère / Attendu / Observé / Preuve / Statut / Limite**, avec un lien ou un fichier et sa ligne pour chaque constat décisif. Ordonner les blocages par impact, puis donner le prochain pas et les conditions précises qui le rendent admissible.

## Verdicts

- **CLÔTURABLE** si les critères obligatoires sont couverts par des preuves valides sur le périmètre audité.
- **À VÉRIFIER** si le code est présent et une preuve obligatoire manque ou ne peut être reliée au SHA. Nommer le contrôle manquant. Un résultat préparé ou absent reste `NOT_RUN`.
- **À CORRIGER** si un invariant obligatoire échoue. Donner la plus petite correction proposée, l’oracle et le test de confirmation, sans appliquer la correction dans la revue.

Une recommandation de passage à T10 est une conclusion de revue. L’exécution de T10 suit son mandat propre.
