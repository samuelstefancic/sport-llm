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

`python -B scripts/verify_t07.py` a exercé le parcours local Spring Boot → FastAPI → Java → PostgreSQL. Les résultats acceptés ont été relus par HTTP et par SQL. Les vérifications T06 et T04 ont également réussi. [Oracles](../data/dev/oracles.md) · [Contrôle HTTP et SQL](../scripts/verify_t07.py)

**Exercice T07.** Pourquoi peut-on convertir 5 km en mètres et pourquoi la déclaration « j’ai couru 5 » ne permet-elle pas cette opération ?

## T08 — Révisions, corrections et idempotence

Sur les deux domaines `meals` et `workouts`, `PUT /{domaine}/{id}/revisions/{r}/declaration` enregistre une déclaration indépendamment de l’analyse. Son corps contient `text` et, pour un repas, les champs facultatifs `selected_nutrients` et `corrected_mentions`. La première révision est 1. La correction soumet le texte complet à la révision suivante. Répéter un PUT identique renvoie la déclaration enregistrée. Un autre contenu à la même révision retourne HTTP 409 `revision_conflict`. Une correction alimentaire contrôle les masses déclarées, les apports sélectionnés et les identifiants des mentions corrigées. Les quantités inconnues restent admises.

Les `POST /meals` et `POST /workouts` gardent leurs corps historiques, avec `entry_id` et `entry_revision`. Ils calculent le résultat d’une déclaration identique déjà enregistrée, ou enregistrent la déclaration et le résultat ensemble pour une première révision ou une correction immédiate. `GET /{domaine}/{id}/revisions/{r}/declaration` et `GET /{domaine}/{id}/revisions/{r}` relisent respectivement la déclaration et le résultat historiques. `GET /{domaine}/{id}` relit le résultat de la révision courante et renvoie 404 tant que cette révision attend son résultat.

Sur les POST, l’en-tête facultatif `Idempotency-Key` est commun aux deux domaines du journal local. Il accepte de 1 à 128 caractères ASCII parmi les lettres, chiffres, points, underscores, deux-points et tirets, avec une lettre ou un chiffre en premier. Le contenu comparé comprend domaine, identifiant, révision, texte exact, sélection ordonnée et ensemble des mentions corrigées. Le défaut de sélection équivaut à sa liste explicite dans le même ordre. La clé d’un résultat enregistré rejoue ce résultat, même après correction. Un contenu différent pour cette clé retourne HTTP 409 `idempotency_conflict`. La clé enregistre un succès dans PostgreSQL. Des POST concurrents peuvent chacun solliciter le pair Python.

Java lit d’abord la révision sans verrou et ferme la connexion avant l’appel à Python. Après réception, Java ouvre une transaction PostgreSQL `READ COMMITTED` et verrouille la clé si elle est fournie. Il relit ensuite la révision sous `SELECT … FOR UPDATE` sur l’entrée. Ce verrou protège le contrôle final, l’éventuelle correction, le résultat et sa clé jusqu’au commit. Une proposition devenue obsolète reçoit HTTP 409 avec le rejet `java_analysis_rejection` et les deux révisions. [Schéma et reprise des données](../java/src/main/resources/journal.sql) · [Scénario T03](../contracts/examples/revision-scenario.json)

Appliquer `java/src/main/resources/journal.sql` au stockage T06/T07 après avoir arrêté l’ancien écrivain, puis démarrer la version Java T08 qui renseigne `declaration_bound`. Le résultat préexistant le plus récent fixe le domaine et la révision de départ. Les résultats déjà présents restent relisibles dans leur domaine historique. Aucune déclaration ni clé n’est reconstruite pour ces résultats.

Après la migration, PostgreSQL accepte un INSERT au format T06/T07 si le domaine correspond à l’entrée et si la révision n’a pas de déclaration T08. Le premier INSERT pour un nouvel identifiant fixe son domaine. Une écriture incompatible est refusée en SQLSTATE `23514`. Au retour vers T08, rejouer le script avance la tête jusqu’au dernier résultat compatible et préserve une déclaration courante plus récente en attente d’analyse.

| Contrôle local sur données fictives | Résultat observé par HTTP et PostgreSQL |
|---|---|
| Premier calcul du repas r1 retenu chez le pair | Correction de 150 à 100 g sur r2. Bilan T03 du sel vérifié sur r2. Retour r1 en HTTP 409 avec `PROP-OLD` et les révisions 1/2. Deux déclarations, zéro bilan r1, un bilan r2 préservé. |
| Course sur le journal sportif | La correction r2 tient le verrou de ligne. `pg_blocking_pids` confirme que l’analyse r1 attend ce verrou après sa lecture préparatoire. Au commit de la correction, l’analyse reçoit HTTP 409. Le résultat r2 relu vaut 25 min et conserve la source de correction. |
| Même clé et même contenu | Deux transactions atteignent le verrou PostgreSQL de la clé. Deux HTTP 200 avec le même résultat, une déclaration, un résultat et une clé persistés. Les UUID distinguent le commit `journal_committed` du rejeu `idempotent_replay`. |
| Même clé et deux textes | Les deux transactions se présentent au même verrou PostgreSQL. HTTP 200 pour l’une et HTTP 409 `idempotency_conflict` pour l’autre. Le résultat et le texte du gagnant sont conservés. |
| Même révision sans clé | Deux requêtes attendent le verrou de la même entrée. Seule celle qui correspond à la déclaration persistée aboutit. |
| Rejeu ancien et échecs | La clé r1 renvoie le résultat initial après r2, y compris avec le pair arrêté. Les versions et les lignes SQL restent identiques après le rejeu, une proposition invalide, une correction refusée ou un appel d’analyse qui échoue. |
| Migration sur données historiques | Résultats T06/T07 fictifs au format de l’ancien stockage. Leurs charges JSON restent relisibles. La plus haute révision devient courante et peut être corrigée. Réappliquer le script conserve l’état. |
| Reprise après l’ancien écrivain | Un INSERT repas r6 au format T06/T07 est repris par la migration. PostgreSQL refuse un résultat sport r9 sur le même identifiant et laisse possibles les corrections repas r7 à r10. Une déclaration sport courante sans résultat garde sa révision. |
| Révision réservée | Pour un repas dont la déclaration r2 est à 100 g, PostgreSQL refuse le résultat ancien à 150 g. Le GET courant retourne 404, puis le calcul T08 publie les 100 g de r2. |

`python -B scripts/verify_t08.py` exécute ces contrôles dans un schéma isolé. Le pair HTTP de test invoque le parseur déterministe du service Python et permet de maîtriser l’ordre et d’injecter des réponses invalides. Les contrôles T06/T07 lancent FastAPI. Les barrières de T08 attendent des événements ou des verrous observés côté PostgreSQL. Les observations portent sur l’exécution locale. [Vérification T08](../scripts/verify_t08.py)

**Exercice T08.** Si l’analyse a lu r1 et que la correction obtient le verrou d’abord, quelle révision la transaction d’analyse observe-t-elle quand elle obtient enfin le verrou, et que peut-elle écrire ?

## T09 — Intégration Compose et pannes

L’API Spring Boot s’appuie sur PostgreSQL 16 et interroge FastAPI (Python 3.11) sur le réseau interne Compose. Sur un volume neuf, PostgreSQL applique le SQL du journal, puis le service ponctuel `catalog` exécute l’importeur T05. Java 17 attend son succès et le démarrage de Python. Le catalogue `DEMO-FOOD 0.2.0` et les entrées d’exemple sont fictifs. Seul Java publie un port, attribué par Docker sur `127.0.0.1`. Le montage du mot de passe sert à l’environnement local de développement. [Compose](../compose.yaml) · [Importeur](../catalog/import_catalog.py) · [Oracles](../data/dev/oracles.md)

Sur l’hôte, il faut Java 17 ou supérieur, Maven, Docker avec Compose v2 et Python 3.11 équipé des dépendances des vérificateurs. Depuis la racine du dépôt, dans un environnement Python dédié :

```sh
python -m pip install -r python/requirements.txt -r catalog/requirements.txt jsonschema==4.26.0
python -B scripts/verify_t09.py --all
```

La commande prépare le JAR avec Maven, rejoue P0 puis T04–T08 en séquence et exécute T09. `--offline-maven` réutilise le cache Maven local quand il est complet. En omettant `--all`, on exécute uniquement le contrôle T09 dans Compose. Chaque exécution crée un projet de nom aléatoire, un volume dédié et un mot de passe temporaire dans un fichier accessible à son propriétaire. Une surcharge de test publie aussi PostgreSQL sur un port éphémère de la boucle locale. En fin d’exécution, le vérificateur supprime et contrôle les ressources de ce projet. Le cache Docker est partagé. [Vérificateur](../scripts/verify_t09.py)

Pour lancer seulement la pile de démonstration, fournir un fichier de mot de passe stable tant que le volume est utilisé. Choisir un nouveau nom pour chaque environnement.

```sh
project="llmsport-demo-$(openssl rand -hex 8)"
secret_dir="$(mktemp -d)"
export LLMSPORT_DB_SECRET="$secret_dir/db-password"
(umask 077; openssl rand -hex 32 > "$LLMSPORT_DB_SECRET")
mvn -q -f java/pom.xml package
docker compose -p "$project" up --build --wait
docker compose -p "$project" port java 8103
```

Pour supprimer une démonstration jetable et son journal, `docker compose -p "$project" down --volumes --rmi local`, puis supprimer le fichier de mot de passe créé pour ce projet.

| Contrôle Compose | Résultat attendu par le vérificateur |
|---|---|
| F02 | 415 kcal, 42,5 g de protéines, 46 g de glucides et 4,3 g de lipides. Rapports complets et références du catalogue versionnées. POST, GET et SQL comparés. |
| S03 | 3 × 10, 30 répétitions et 40 kg, avec sources déclarées. POST, GET et SQL comparés. |
| S06 | 30 min et une clarification pour le 5 sans unité. Distance inconnue, conservée comme telle après lecture HTTP et SQL. |
| Python arrêté | HTTP 502 `python_unavailable` si la connexion échoue immédiatement, ou HTTP 504 `python_timeout` à l’expiration du délai. Même UUID entre la réponse et Java. Les tables `journal_entry`, `journal_declaration`, `journal_result` et `journal_idempotency` gardent leurs lignes et leur état transactionnel observé. |
| Rejeu et conflit de clé pendant l’arrêt | Même résultat pour la même clé et le même contenu, HTTP 409 pour un contenu divergent. Une seule entrée, déclaration, ligne de résultat et clé pour F02. |
| Pair invalide | Le serveur de test remplace FastAPI et répond HTTP 200 avec une proposition incomplète. Java renvoie HTTP 502 `invalid_proposal`, avec le même UUID dans le client et les deux services, et sans changement des quatre tables. |
| Entrée composée d’une espace insécable | HTTP 400 `invalid_request`, aucun appel au pair et aucune écriture. |

Les traces Compose sont contrôlées pendant le test pour les saisies fictives, leurs fragments de référence, la clé de rejeu et le secret PostgreSQL, y compris les échappements JSON. Pour les appels qui atteignent un pair, l’UUID relie la réponse client à Java et à FastAPI. En cas d’arrêt du pair, de refus précoce ou de rejeu servi en base, l’UUID apparaît côté Java uniquement. Le contrôle est borné aux scénarios exécutés.

**Rejeu local du 18 novembre 2026.** `python -B scripts/verify_t09.py --all --offline-maven` a terminé avec le code 0. Docker Engine 29.1.3 tourne dans une VM Linux ARM64 locale dédiée avec Compose 2.31.0. Le parcours a utilisé Temurin 17.0.21, Python 3.11.18 et PostgreSQL 16.16 dans les conteneurs. L’import T05 a activé `DEMO-FOOD 0.2.0` avec l’empreinte du fichier versionné. L’arrêt Python a donné HTTP 504 `python_timeout` en 2,032 s, le pair invalide HTTP 502 `invalid_proposal` en 0,061 s. Le contrôle des traces et le nettoyage du projet ont réussi.

Le workflow GitHub Actions **Vérifications P1** reprend la même commande et dépend des minutes incluses dans le dépôt pour le runner Ubuntu hébergé. Il se déclenche manuellement avec `workflow_dispatch` et utilise des dépendances publiques. Le résultat de la CI est à relever dans le run du SHA vérifié. [Workflow](../.github/workflows/p1-verification.yml)

**Exercice T09.** Comment utilises-tu l’UUID dans les traces Java et FastAPI pour distinguer un pair arrêté d’une proposition invalide ?
