# llmSport

## Écran local

Un checkout neuf peut démarrer l’écran avec les outils déjà présents sur la machine.

- Python 3.11 au minimum, avec les dépendances de [python/requirements.txt](python/requirements.txt) (`fastapi`, `pydantic`, `uvicorn`) et de [catalog/requirements.txt](catalog/requirements.txt) (`psycopg[binary]`) déjà installées dans l’environnement choisi.
- JDK 17 ou ultérieur et Maven, avec `java` et `mvn` sur le `PATH`. Le cache Maven doit déjà contenir les dépendances et plugins de [java/pom.xml](java/pom.xml) nécessaires à `mvn -o -f java/pom.xml -DskipTests package`.
- PostgreSQL 17.12, la version vérifiée pour l’écran, avec `initdb` et `postgres` exécutables dans le même répertoire, et leurs bibliothèques et fichiers de support. Pour réutiliser un cluster existant, conserver sa version majeure.
- Un système Unix avec `/bin/sh`, `dirname`, `ps` et les modules standard Python `fcntl` et `sqlite3`. Utiliser un compte non root avec accès en écriture au checkout et des ports libres pour l’instance choisie. Le collecteur utilise `sysctl` pour la pression mémoire si le système fournit cette mesure.

Depuis la racine du checkout, adapter les deux chemins d’exemple puis garder les variables exportées dans le même terminal pour le démarrage, les vérifications et le redémarrage. Pour un venv, indiquer son propre `bin/python`. Le lanceur utilise les outils configurés et crée le cluster dédié au premier démarrage.

```sh
export LLMSPORT_PYTHON='/chemin/vers/mon venv/bin/python'
export LLMSPORT_PG_BIN='/chemin/vers/postgresql/bin'
```

Chaque variable absente ou vide utilise son chemin de repli sous `LLMSPORT_T10_TOOLS` (`venv/bin/python` ou `postgres-17.12/bin`). Sans cette variable commune, le repli est `../github-t10/.local/t10`. Avec les deux chemins explicites, le checkout fonctionne indépendamment de cette arborescence.

Démarrer l’écran puis ouvrir [127.0.0.1:8113](http://127.0.0.1:8113/).

```sh
./scripts/ecran-local start
./scripts/ecran-local status
./scripts/ecran-local restart
./scripts/ecran-local stop
```

Java, FastAPI et PostgreSQL écoutent sur `127.0.0.1`, respectivement sur les ports 8113, 8114 et 8115. Le répertoire `.local/ecran` conserve la base dédiée et les journaux de démarrage. L’arrêt et le redémarrage préservent cette base.

Dans **Journal**, charger l’exemple vélo puis choisir **Analyser et enregistrer**. L’écran affiche 4,5 km déclarés, 4 500 m normalisés et la citation « 4,5 km ». L’historique relit les résultats par révision dans PostgreSQL. La latence HTTP mesure le POST jusqu’à réception du corps dans ce navigateur. Elle reste disponible à la relecture dans le même profil navigateur et s’affiche comme indisponible si aucune mesure locale n’existe.

Dans **Suivi**, les décisions et les repères proviennent de [suivi-local.json](documentation/suivi-local.json). Les archives historiques sont facultatives. Le profil cherche les pièces qu’il autorise dans les arborescences voisines prévues. Une pièce absente s’affiche comme indisponible.

### Laboratoire Qwen

Le profil `ecran-local` ouvre [Laboratoire Qwen](http://127.0.0.1:8113/#laboratoire-qwen). L’instance d’essai utilise [127.0.0.1:8213](http://127.0.0.1:8213/#laboratoire-qwen). Depuis un checkout qui contient ce lot et avec les outils configurés ci-dessus, utiliser :

```sh
./scripts/ecran-local --essai restart
./scripts/ecran-local --essai status
./scripts/ecran-local restart
```

**Actualiser** lit l’installation et la résidence de `qwen3:4b` sur le serveur Ollama déjà disponible à `127.0.0.1:11434`. **Charger le modèle** demande deux minutes de résidence. **Lancer** peut aussi charger le modèle. Le laboratoire utilise uniquement ce modèle installé. L’ouverture de l’onglet consulte l’état. Le démarrage d’Ollama et l’installation du modèle relèvent de l’opérateur. [API Ollama](https://docs.ollama.com/faq#how-can-i-preload-a-model-into-ollama-to-get-faster-response-times)

Pour comparer les trois modes, charger **F10 · rév. 2** puis conserver la température à 0 et le plafond à 256 jetons. Chaque mode permet d’éditer sa consigne :

- **Référence pré-T11** reprend la consigne du banc avec le domaine repas.
- **Variante repas et citations** restreint les instructions à l’extraction alimentaire et conserve les citations libres.
- **Sélection de passages** propose des identifiants de fragments délimités par la ponctuation forte. Les virgules et points décimaux restent dans les fragments. Python recopie à l’identique un fragment existant pour chaque identifiant rendu. Les quantités, unités et états restent proposés par Qwen.

Sur le texte fictif exact de la [révision F10](data/dev/cases.json), le contrôle indépendant vérifie l’ordre, les citations contiguës verbatim, les quantités et l’état. Pour le riz, la citation doit inclure le rejet des 150 g. Pour le poulet, elle doit inclure le maintien de 100 g. Toute modification du texte rend cet oracle inapplicable. L’historique garde trois essais dans la mémoire de l’onglet jusqu’au rechargement. Le laboratoire affiche les sorties brutes et les raisons de verdict. **Télécharger l’essai JSON** enregistre explicitement un essai depuis le navigateur. Le fichier contient aussi le modèle, son empreinte et la version Ollama lorsqu’elles sont connues. Le laboratoire n’écrit aucune déclaration, consigne ou sortie dans le journal et ne sauvegarde automatiquement aucun essai.

Les deux instances passent par le FastAPI du journal sur 8114 ou 8214. Un verrou commun au checkout sérialise les chargements et les essais de ces deux instances. Les autres clients d’Ollama sont hors de son périmètre. Le corps JSON est limité à 24 Kio, avec 4 Kio de déclaration et 8 Kio de consigne encodées en UTF-8. Le contexte Ollama est de 2 048 jetons. Une entrée longue peut dépasser la fenêtre du modèle. La sortie est limitée à 512 jetons et la réponse HTTP d’Ollama à 128 Kio. Le délai d’un appel de chargement ou de génération à Ollama est de 60 secondes. Au-delà, le laboratoire ferme la connexion locale.

La latence murale mesure l’appel HTTP de FastAPI à Ollama. Le temps Ollama, les compteurs de jetons et le temps de génération viennent de sa réponse. Le débit divise les jetons générés par le temps de génération Ollama. Le pic RSS est le maximum échantillonné toutes les 250 ms environ pour le serveur Ollama qui écoute sur le port 11434 et ses descendants. En cas d’identité incertaine ou de relevé absent, le pic est inconnu. Ce RSS peut compter plusieurs fois des pages partagées, manquer un pic bref et ne fournit aucune occupation GPU distincte. Le PID est identifié avec `/usr/sbin/lsof` et `/bin/ps` quand ces outils fournissent une identité fiable. [Mesures de l’API Ollama](https://docs.ollama.com/api/chat)

Vérifier les garde-fous et l’oracle avec le Python existant. Ces tests simulent Ollama :

```sh
"$LLMSPORT_PYTHON" -B scripts/test_qwen_lab.py -v
mvn -o -f java/pom.xml -DskipTests package
```

### Suivi en direct

L’onglet **Suivi** affiche les fiches en cours, les douze dernières fiches terminées et le dernier relevé mémoire. Une fiche réunit l’objectif, le responsable, le critère de fin, l’estimation initiale datée, le temps mural, les jetons par session, le RSS échantillonné et les preuves locales inscrites. Le temps mural augmente depuis le début déclaré et se fixe à la fin déclarée. L’écart indique le temps sous la borne basse ou au-delà de la borne haute de l’estimation initiale. À l’intérieur de la fourchette, l’écart vaut zéro.

```sh
./scripts/ecran-local suivi declarer livraison-locale \
  --objectif "Vérifier l’écran local" --responsable "Équipe locale" \
  --critere-fin "Contrôles d’essai relus" \
  --debut 2026-11-22T09:00:00+01:00 --estime-le 2026-11-22T08:55:00+01:00 --min 25 --max 45
./scripts/ecran-local suivi session livraison-locale UUID-CODEX --role principal
./scripts/ecran-local suivi session livraison-locale UUID-DU-SOUS-AGENT --role sous-agent
./scripts/ecran-local suivi enrichir livraison-locale --preuve workflow-8113
./scripts/ecran-local suivi finir livraison-locale
./scripts/ecran-local suivi historique
./scripts/ecran-local suivi historique livraison-locale
```

Remplacer les UUID d’exemple par ceux des sessions llmSport à mesurer. Le rôle `demandeur` est disponible pour une session distincte. Sans estimation, l’écran indique « Estimation initiale inconnue ». Pour consigner des dates attestées, utiliser `declarer ID --debut DATE --estime-le DATE --min 25 --max 45` et `finir ID --fin DATE`, avec des dates ISO 8601 munies d’un fuseau. Ces commandes peuvent précéder le démarrage du collecteur. La date d’estimation est antérieure ou égale au début réel. Répéter la commande `suivi session` avec le même rôle relit la source dans les fenêtres inscrites, par exemple lorsqu’un fichier redevient disponible après la clôture.

`suivi enrichir ID` applique les options renseignées à une fiche existante, ouverte ou terminée. Les options `--objectif`, `--responsable` et `--critere-fin` peuvent être utilisées séparément. Les trois options d’estimation peuvent compléter une estimation encore inconnue si la date initiale est attestée. Une estimation enregistrée est immuable. Les anciennes fiches conservent leurs mesures et affichent les champs descriptifs manquants comme non renseignés.

`--preuve ID` ajoute un identifiant de reçu à la fiche. L’option est répétable et dédupliquée. L’identifiant compte de 1 à 64 caractères ASCII, commence par une lettre minuscule ou un chiffre, et peut ensuite contenir aussi des tirets. Chaque route `/ecran/preuves-lots/ID` lit le fichier régulier canonique `.local/preuves-lots/ID.json` à la racine du worktree de l’écran. Par exemple, `--preuve workflow-8113` lie `.local/preuves-lots/workflow-8113.json`. On peut ajouter les reçus de nouveaux lots sans modifier le code ni redémarrer l’écran. Les reçus sont servis en texte brut. Une pièce absente ou un lien symbolique est indisponible.

Le dépôt de l’écran et ses worktrees déclarés par Git définissent le périmètre des répertoires de travail. Pour rattacher aussi les sessions ouvertes dans un dossier d’orchestration, fournir son chemin absolu à `start` ou `restart`.

```sh
./scripts/ecran-local restart --suivi-orchestration-cwd /chemin/absolu/orchestration
```

L’option autorise ce dossier précis. Ses sous-dossiers doivent appartenir à un worktree llmSport pour être inclus. Elle est conservée par instance et s’applique aussi aux commandes `suivi` suivantes. Pour la retirer, utiliser `restart --sans-suivi-orchestration`. Redémarrer l’instance 8113 après la mise à jour du périmètre. Le suivi reconstruit les relevés de jetons, de tours et les curseurs depuis les sources accessibles avant de publier son instantané. Une source inaccessible est signalée comme indisponible. Les tâches déclarées, leurs rattachements et les relevés de mémoire restent disponibles.

- **Mémoire.** Le collecteur relève toutes les cinq secondes le RSS en Kio de Spring Boot, de FastAPI et du processus parent PostgreSQL. Il vérifie les signatures de démarrage des PIDs dans le registre du lanceur. L’écran convertit les valeurs en Mio. La pression système vient de `kern.memorystatus_vm_pressure_level` quand le système donne accès à cette mesure (1 normale, 2 avertissement, 4 critique). Le relevé est affiché en retard après 15 secondes. Le pic par service correspond au maximum des relevés disponibles entre le début et la fin de la tâche ou l’heure courante. L’écran affiche la période effectivement échantillonnée et les cinq derniers relevés par tâche. Un pic entre deux relevés peut échapper à la collecte. Les archives Qwen restent dans les sections du banc et de la sonde.
- **Jetons.** Le collecteur ouvre le JSONL de chaque UUID inscrit, sous `$CODEX_HOME` ou `~/.codex`. Il vérifie l’identité de la session et le répertoire de travail déclaré dans ses métadonnées et dans le contexte de chaque tour. Les événements hors périmètre servent seulement à suivre le cumul avant un retour au projet. Les incréments de cumuls sont dédupliqués et attribués selon l’horodatage d’émission inclus dans la fenêtre. Un appel émis dans la fenêtre peut avoir débuté avant sa borne. Les totaux affichés viennent de la source, avec le cache inclus dans l’entrée et le raisonnement inclus dans la sortie quand les compteurs documentent ces sous-totaux. Une absence de mesure s’affiche comme indisponible. Toutes les sessions ont leur propre ligne. Des fenêtres qui se recouvrent peuvent contenir le même relevé et se lisent individuellement. Après la clôture, une grâce de dix secondes permet de rattraper un flush tardif, dans les bornes déjà déclarées. Le curseur et le rejeu restent limités aux sessions inscrites.
- **Lecture.** Le stockage SQLite privé, les curseurs de lecture et l’agrégat d’affichage se trouvent sous `.local/ecran/suivi-direct`. `suivi historique ID` relit tous les échantillons disponibles de la fenêtre. Le point d’accès [Suivi en direct](http://127.0.0.1:8113/api/local/suivi/direct) accepte une requête GET sans paramètres et restitue un agrégat JSON de schéma versionné, avec `rss_unit`, `postgres_scope`, `active_tasks`, `history` et `latest_sample`. Chaque fiche inclut `objective`, `owner` et `completion_criterion`, à `null` si inconnus, et le tableau `evidence_ids`. Les horodatages JSON sont en UTC. Les dates de l’écran sont en heure de Paris.

## Vérifier l’écran dans une instance séparée

Avec les variables de l’exemple exportées, démarrer l’instance d’essai puis ouvrir [127.0.0.1:8213](http://127.0.0.1:8213/). En mode T10, utiliser le Python du venv T10 ou `python3` (3.11 minimum) pour les trois scripts de vérification.

```sh
"$LLMSPORT_PYTHON" -B scripts/test_suivi_direct.py
./scripts/ecran-local --essai start
./scripts/ecran-local --essai status
"$LLMSPORT_PYTHON" -B scripts/verify_suivi_direct.py
"$LLMSPORT_PYTHON" -B scripts/verify_ecran_local.py --sans-archives
./scripts/ecran-local --essai stop
```

L’instance d’essai utilise les ports 8213 à 8215 et conserve ses entrées et sessions fictives dans `.local/ecran-essai`. Les contrôles couvrent le suivi direct et sa reprise, le POST concurrent et le rejeu, ainsi que les révisions et leur persistance après redémarrage. Si les archives historiques sont présentes dans les arborescences attendues, exécuter `verify_ecran_local.py` sans option pour vérifier aussi leur contenu.
