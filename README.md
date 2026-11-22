# llmSport

## Écran local

Depuis la racine du worktree, démarrer l’écran puis ouvrir [127.0.0.1:8113](http://127.0.0.1:8113/).

```sh
./scripts/ecran-local start
./scripts/ecran-local status
./scripts/ecran-local restart
./scripts/ecran-local stop
```

Le lanceur utilise Java, le cache Maven en mode hors ligne, le venv et PostgreSQL 17.12 déjà présents dans `../github-t10/.local/t10`. Pour une autre installation locale de ces deux derniers outils, définir `LLMSPORT_T10_TOOLS`. Java, FastAPI et PostgreSQL écoutent sur `127.0.0.1`, respectivement sur les ports 8113, 8114 et 8115. Le répertoire `.local/ecran` conserve la base dédiée et les journaux de démarrage. L’arrêt et le redémarrage préservent cette base.

Dans **Journal**, charger l’exemple vélo puis choisir **Analyser et enregistrer**. L’écran affiche 4,5 km déclarés, 4 500 m normalisés et la citation « 4,5 km ». L’historique relit les résultats par révision dans PostgreSQL. La latence HTTP mesure le POST jusqu’à réception du corps dans ce navigateur. Elle reste disponible à la relecture dans le même profil navigateur et s’affiche comme indisponible si aucune mesure locale n’existe.

Dans **Suivi**, les décisions et les repères proviennent de [suivi-local.json](documentation/suivi-local.json). Les métriques sont lues dans les pièces locales autorisées par le profil de l’écran. Une pièce absente s’affiche comme indisponible.

### Suivi en direct

L’onglet **Suivi** affiche les tâches en cours, les douze dernières tâches terminées et le dernier relevé mémoire. Le temps mural augmente depuis le début déclaré et se fixe à la fin déclarée. L’écart indique le temps sous la borne basse ou au-delà de la borne haute de l’estimation initiale. À l’intérieur de la fourchette, l’écart vaut zéro.

```sh
./scripts/ecran-local suivi declarer livraison-locale
./scripts/ecran-local suivi session livraison-locale UUID-CODEX --role principal
./scripts/ecran-local suivi session livraison-locale UUID-DU-SOUS-AGENT --role sous-agent
./scripts/ecran-local suivi finir livraison-locale
./scripts/ecran-local suivi historique
./scripts/ecran-local suivi historique livraison-locale
```

Remplacer les UUID d’exemple par ceux des sessions llmSport à mesurer. Le rôle `demandeur` est disponible pour une session distincte. Sans estimation, l’écran indique « Estimation initiale inconnue ». Pour consigner des dates attestées, utiliser `declarer ID --debut DATE --estime-le DATE --min 25 --max 45` et `finir ID --fin DATE`, avec des dates ISO 8601 munies d’un fuseau. Ces commandes peuvent précéder le démarrage du collecteur. La date d’estimation est antérieure ou égale au début réel. Répéter la commande `suivi session` avec le même rôle relit la source dans les fenêtres inscrites, par exemple lorsqu’un fichier redevient disponible après la clôture.

- **Mémoire.** Le collecteur relève toutes les cinq secondes le RSS en Kio de Spring Boot, de FastAPI et du processus parent PostgreSQL. Il vérifie les signatures de démarrage des PIDs dans le registre du lanceur. L’écran convertit les valeurs en Mio. La pression système vient de `kern.memorystatus_vm_pressure_level` quand le système donne accès à cette mesure (1 normale, 2 avertissement, 4 critique). Le relevé est affiché en retard après 15 secondes. Le pic par service correspond au maximum des relevés disponibles entre le début et la fin de la tâche ou l’heure courante. L’écran affiche la période effectivement échantillonnée et les cinq derniers relevés par tâche. Un pic entre deux relevés peut échapper à la collecte. Les archives Qwen restent dans les sections du banc et de la sonde.
- **Jetons.** Le collecteur ouvre le JSONL de chaque UUID inscrit, sous `$CODEX_HOME` ou `~/.codex`, et vérifie l’identité de session et le répertoire de travail llmSport du tour. Il projette les champs techniques des événements de début, de fin, d’interruption, de contexte et de compteurs. Les incréments de cumuls sont dédupliqués et attribués selon l’horodatage d’émission inclus dans la fenêtre. Un appel émis dans la fenêtre peut avoir débuté avant sa borne. Les totaux affichés viennent de la source, avec le cache inclus dans l’entrée et le raisonnement inclus dans la sortie quand les compteurs documentent ces sous-totaux. Une absence de mesure s’affiche comme indisponible. Toutes les sessions ont leur propre ligne. Des fenêtres qui se recouvrent peuvent contenir le même relevé et se lisent individuellement. Après la clôture, une grâce de dix secondes permet de rattraper un flush tardif, dans les bornes déjà déclarées. Le curseur et le rejeu restent limités aux sessions inscrites.
- **Lecture.** Le stockage SQLite privé, les curseurs de lecture et l’agrégat d’affichage se trouvent sous `.local/ecran/suivi-direct`. `suivi historique ID` relit tous les échantillons disponibles de la fenêtre. Le point d’accès [Suivi en direct](http://127.0.0.1:8113/api/local/suivi/direct) accepte une requête GET sans paramètres et restitue un agrégat JSON de schéma versionné, avec `rss_unit`, `postgres_scope`, `active_tasks`, `history` et `latest_sample`. Les horodatages JSON sont en UTC. Les dates de l’écran sont en heure de Paris.

## Vérifier l’écran dans une instance séparée

```sh
python3 -B scripts/test_suivi_direct.py
./scripts/ecran-local --essai start
python3 -B scripts/verify_suivi_direct.py
python3 -B scripts/verify_ecran_local.py
./scripts/ecran-local --essai stop
```

L’instance d’essai utilise les ports 8213 à 8215 et conserve ses entrées et sessions fictives dans `.local/ecran-essai`. Les contrôles couvrent le suivi direct et sa reprise, les pièces du suivi dans l’arborescence locale, le POST concurrent et le rejeu, ainsi que les révisions et leur persistance après redémarrage.
