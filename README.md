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

## Vérifier l’écran dans une instance séparée

```sh
./scripts/ecran-local --essai start
python3 -B scripts/verify_ecran_local.py
./scripts/ecran-local --essai stop
```

L’instance d’essai utilise les ports 8213 à 8215 et conserve ses entrées fictives dans `.local/ecran-essai`. Le contrôle vérifie les pièces du suivi dans l’arborescence locale, le POST concurrent et le rejeu, les révisions et la persistance après redémarrage.
