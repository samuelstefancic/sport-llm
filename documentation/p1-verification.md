# P1 — Vérifications des chaînes applicatives

## Reproduction locale

Depuis la racine du clone, utiliser Java 17 ou supérieur, Maven, une base PostgreSQL de développement dédiée et un Python équipé de `python/requirements.txt`, `catalog/requirements.txt` et `jsonschema==4.26.0`. Les tests du journal créent et suppriment chacun leur propre schéma PostgreSQL. Configurer `PGHOST=127.0.0.1`, `PGPORT`, `PGDATABASE`, `PGUSER` et le moyen d’authentification local. Les scripts construisent le JAR avec Maven hors ligne lorsque les dépendances sont déjà en cache. Lancer les scripts successivement pour éviter deux constructions du même JAR en parallèle.

## T06 — Bilan alimentaire

`python -B scripts/verify_t06.py` lance l’API Java et le serveur FastAPI sur la boucle locale. `POST /meals` accepte la déclaration, l’identifiant, la révision et la sélection facultative des apports. `GET /meals/{id}/revisions/{r}` relit la version enregistrée. Java contrôle les fragments de la déclaration et les candidats reçus, consulte le catalogue actif, calcule en décimal et écrit le rapport avec sa provenance dans PostgreSQL. Une quantité corrigée peut être indiquée par son identifiant dans `corrected_mentions`.

| Oracle ou contrôle | Résultat observé |
|---|---|
| F02, catalogue fictif 0.2.0 | 415 kcal, 42,5 g de protéines, 46 g de glucides, 4,3 g de lipides. Tous complets. Rapport validé contre T03 puis relu par HTTP et SQL. |
| T03-SEL-001, variante historique isolée | Riz corrigé à 100 g, autres aliments déclarés. Protéines 34,5 g complètes, énergie 295 kcal partielles, sel 0 g partiel avec deux manques, glucides et lipides indéterminés. L’ancien rapport F02 reste lisible après activation de cette variante. |
| Ambiguïté et décimales | Le riz sans quantité provoque une clarification. Avec 12,5 g de riz, le résultat est 0,0375 g de lipides. |
| Validation | Un espace insécable seul reçoit HTTP 400. Une quantité Python portée à 150 g pour une déclaration de 100 g reçoit HTTP 502. Dans les deux cas, zéro résultat enregistré. |

Les règles de lecture en français couvrent des formulations bornées. Chaque référence de calcul porte sa fiche et sa version, distinctes du texte saisi. Régressions exécutées : P0 (25 exemples, 30 cas), T04 (HTTP et délai) et T05 (import, interruption et rejeu). [Oracles](../data/dev/oracles.md) · [Schéma](../contracts/analysis.schema.json) · [Cas du sel](../contracts/examples/java-salt-reference.json) · [Test HTTP et SQL](../scripts/verify_t06.py)

**Exercice T06.** Si seul le riz a une teneur en sel connue, quel statut et quelles preuves doivent accompagner une somme de zéro ?

## T07 — Journal sportif

`POST /workouts` reçoit `entry_id`, `entry_revision` et `text`. Java demande une proposition `workout` à FastAPI et vérifie chaque mesure contre la déclaration, y compris son unité, son extrait et sa révision. `measures` conserve les valeurs déclarées. `summary` indique les valeurs calculables, les unités, les sources et les statuts `known`, `absent` ou `unresolved`. La distance est normalisée en mètres, et la durée en minutes ou en secondes si une mesure est fournie en secondes. Une relation « séries de répétitions » explicite permet de calculer `total_repetitions`.

`GET /workouts/{id}/revisions/{r}` relit le résultat dans le journal PostgreSQL. Une déclaration sans unité peut conserver son nombre, un résultat inconnu et une question. `energy_burned` reste à `null`. La grammaire française couvre une activité et des formulations bornées. Elle reconnaît les segments reliés par « puis » ou « et », ainsi que les durées composées comme « 1 h 15 min ». La gestion des corrections et de la révision courante relève de T08.

| Contrôle sur données fictives | Résultat observé en local |
|---|---|
| S01 | 30 min. Les segments 20 min et 10 min gardent chacun l’extrait correspondant. Distance absente. |
| S03 | 3 séries de 10 répétitions, 30 répétitions au total et 40 kg déclarés. Durée et distance absentes. |
| S06 et témoin explicite | 30 min dans les deux cas. Le nombre 5 sans unité est conservé avec une question. Lorsqu’il est déclaré en km, il donne 5 000 m. |
| S02, S04, S05, S07, S10 et variantes | Somme de 2 750 m, durée de 75 min, activité sans mesure, charge sans unité, zéro explicite, décimales, secondes et alternatives ambiguës vérifiés. |
| Vitesse et allure | `km/h`, `m/s` et `min/km` avec ou sans espaces, ainsi que « km par heure », restent dans la déclaration. Les 30 min explicites sont enregistrées seules. |
| Milliers groupés | Valeur entière et extrait d’origine conservés pour `1 000 m` et `1 250 m`, y compris les espaces insécables et les variantes décimales. Un groupe incomplet reçoit HTTP 400, sans écriture. |
| S08 et unité incohérente dans la déclaration | HTTP 400, aucune écriture. |
| Réponses simulées du pair FastAPI | HTTP 502 et aucune écriture pour une dimension invalide, une valeur ou une unité plausible contredite par le texte, une omission et une mauvaise révision de source. |

`python -B scripts/verify_t07.py` a exercé le parcours local Spring Boot → FastAPI → Java → PostgreSQL. Les résultats acceptés ont été relus par HTTP et par SQL. Les vérifications T06 et T04 ont également réussi. Le démarrage avec Compose reste à vérifier dans T09. [Oracles](../data/dev/oracles.md) · [Contrôle HTTP et SQL](../scripts/verify_t07.py)

**Exercice T07.** Pourquoi peut-on convertir 5 km en mètres et pourquoi la déclaration « j’ai couru 5 » ne permet-elle pas cette opération ?
