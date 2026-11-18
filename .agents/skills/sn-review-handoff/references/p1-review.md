# Grille de revue de P1

Lire les versions du plan, du contrat et des oracles au SHA audité. Les repères ci-dessous orientent la vérification. Utiliser les fixtures historiques avec leur version de catalogue propre.

| Ticket | Contrôle décisif | Contre-exemple à écarter |
|---|---|---|
| T04 — frontière HTTP | Appel Java vers FastAPI et validation de la branche `python_proposal`. Vérifier repas, révision, corrélation et délai jusqu’au corps complet. | Une réponse bien formée pour un autre repas, un rapport de l’union T03 produit par le mauvais service ou un corps suspendu. |
| T05 — publication du catalogue | Activation PostgreSQL atomique et provenance versionnée. Prouver zéro connu, absence inconnue, rejeu, conflit de contenu et interruption avant activation. | Le test simule une interruption dans un mock ou la version partielle devient visible. |
| T06 — repas | F02 donne 415 kcal, 42,5 g de protéines, 46 g de glucides et 4,3 g de lipides, complets. Prouver persistance et relecture, puis vérifier T03-SEL-001 et au moins une ambiguïté. | Attendu codé en dur, mauvais catalogue, quantité reliée au mauvais aliment, résultat instantané jamais relu, ou donnée inconnue transformée en zéro. |
| T07 — sport | S01 donne 30 min, S03 donne 30 répétitions et conserve 40 kg, S06 conserve 30 min et demande l’unité de 5. Prouver la relecture. | Charge ou dépense inventée, unité incohérente acceptée ou conversion d’une valeur inconnue. |
| T08 — correction et idempotence | Deux transactions ou requêtes en PostgreSQL. Contrôler retour tardif r1 après correction r2, course à l’écriture, rejeu identique, contenu différent et doublon simultané. Inspecter les lignes et l’historique. | Le test ne vérifie que le code HTTP. Une autre transaction peut écrire entre la comparaison et l’application. |
| T09 — intégration | Un repas et une séance traversent Compose, puis sont relus de PostgreSQL. Vérifier indisponibilité Python, réponse invalide, duplication, corrélation et preuves CI. | Un fichier Compose parse sans démarrage réel, la CI n’a qu’une définition ou le test remplace la persistance par un mock. |

Pour T03-SEL-001, conserver le riz corrigé à 100 g et la variante de catalogue dédiée. Vérifier 34,5 g de protéines complètes, 295 kcal partielles, 0 g de sel en sous-total partiel avec deux manques, et glucides et lipides indéterminés. Inspecter les sources associées et la distinction entre `null` et 0 sur le trajet complet.

Pour T08, le scénario r1 après r2 attend `stale_revision` et zéro écriture de la réponse r1. Le conflit de clé avec contenu différent est explicite. L’unicité d’écriture métier ne promet aucune invocation unique d’un fournisseur externe. Une réponse Python conforme en structure reste une proposition.

## Clôture

Pour déclarer P1 clôturable, contrôler les six tickets, au moins un repas et une séance persistés puis relus, les ambiguïtés couvertes, les tests obligatoires exécutés et les résultats reliés à leur provenance ou déclaration. Vérifier que le code audité est celui des livraisons fusionnées et que les limites Compose et CI sont explicites.

Le prochain point du plan est T10. Les candidats et seuils de P2 restent à comparer après instrumentation de la baseline. Cette revue ne sélectionne aucun modèle et ne déclenche ni RAG-01 ni P2.
