# Format de passation et preuve de clôture

## En-tête

- Dépôt, jalon, date, base de départ, SHA complet audité et tête distante observée.
- Situation réelle des tickets et mandat consommé. Identifier le prochain ticket et les étapes qui attendent une décision.
- Technologie et équilibre des rôles. Identifier le producteur de chaque patch, l’orchestrateur, les contre-revues éventuelles et la revue Codex de PR. Marquer une hypothèse comme telle.

## Trace par ticket

| Ticket | Attendu | Observation | Test, commande et environnement | Preuve et limites | Statut |
|---|---|---|---|---|---|
| Identifiant stable | Oracle ou invariant | Résultat réel et effectif | SHA testé, commandes, versions et code de sortie | Lien, chemin, repère ou raison du manque | PASS / FAIL / NOT_RUN / BLOCKED |

Ajouter pour chaque livraison la PR, la branche de base, la tête complète revue, le lien et le résultat de revue, le commit de fusion et le contrôle effectué après fusion. Si un seul test couvre plusieurs critères, expliciter les assertions qui les couvrent. Pour une panne, montrer la réponse et l’état métier en base. Pour une mesure, donner l’effectif, le dénominateur et les limites. Les traces excluent données personnelles et secrets.

## Reproduction et reprise

Décrire les prérequis et les commandes dans leur ordre réel, avec l’environnement et le jeu de données. Distinguer ce qui a été exécuté en local, en conteneurs, en CI hébergée et après fusion. Donner les écarts ouverts et la prochaine action. Inclure les exercices à reprendre et le niveau d’autonomie réellement démontré si le parcours est pédagogique.

## Manifeste P1 pour le checker

Le producteur peut joindre un JSON à la passation et réutiliser les mêmes liens de preuve. Le checker vérifie la cohérence déclarée et, avec `--repo`, l’ascendance du commit de fusion dans le SHA audité. La revue établit séparément la véracité des preuves.

| Champ | Valeur |
|---|---|
| `repository` | `samuelstefancic/sport-llm` |
| `audited_sha` | SHA Git complet à auditer |
| `tickets` | Six fiches T04–T09, une par identifiant |
| Champs d’une fiche | `id`, `pr` entier positif, `head_sha`, `review_sha`, `review_status`, `review_url`, `merge_sha`, `controls` |
| `review_status` | `COMPLETED` si la revue de cette tête est terminée et les constats bloquants traités |
| `controls` | Liste de contrôles avec `id`, `status` et `proof`. Inclure au moins un contrôle métier décisif par ticket |
| `gates` | Objet avec les clés `compose-e2e`, `postgres-concurrency`, `ci` et `replay-main`. Chacune porte `status` et `proof` |
| `status` | `PASS`, `FAIL`, `NOT_RUN` ou `BLOCKED`. Une porte obligatoire non passée rend le manifeste incomplet |

Chaque SHA est écrit en entier. Une fiche incomplète conserve ses preuves disponibles et les champs encore inconnus peuvent rester absents. Le checker signale leur manque. Pour `ci`, préciser si la preuve couvre un run hébergé ou une exécution locale, puis laisser au réviseur l’application du critère de clôture prévu dans le mandat et le plan. Les sorties du checker sont `FORMAT_OK` (code 0), `INCOMPLET` (code 1), et erreur de lecture ou de format (code 2).
