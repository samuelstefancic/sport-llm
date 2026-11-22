---
name: sn-qwen-test-suites
description: "Créer, relire et figer un jeu de cas fictifs du laboratoire Qwen de llmSport. Utiliser pour rédiger les attendus, enregistrer un jeu dans Jeux d’essai ou préparer le rejeu d’une série. La comparaison et la décision sur un candidat relèvent de sn-evaluate-models."
---

# Préparer un jeu d’essai Qwen

## Définir les cas avant l’appel

1. Nommer le comportement à vérifier et choisir un identifiant versionné, par exemple `riz-correction-v1`. Préparer un à cinq cas fictifs. Chaque cas porte un nom et la déclaration exacte qui sera envoyée au modèle.
2. Écrire l’attendu à partir de la déclaration et de la règle à vérifier. Employer un tableau ordonné de mentions. Chaque mention contient `anchor`, une citation textuelle continue, `state` (`cooked`, `raw` ou `unknown`) et `quantity` (`null` ou un objet `value` et `unit`). Garder l’unité déclarée. Choisir des citations sans chevauchement dans l’ordre du texte. Pour une correction, inclure dans la citation le rejet de l’ancienne valeur.
3. Le tableau `[]` fixe l’attendu à zéro mention. Le champ laissé vide enregistre `null` et rend le cas exploratoire. Pour un exemple à reproduire à la main, ouvrir [riz-correction-v1.json](assets/riz-correction-v1.json) et reporter le nom, les déclarations et chaque tableau `expected` dans le formulaire.

## Enregistrer et relire sur 8113

Ouvrir le [laboratoire local](http://127.0.0.1:8113/#laboratoire-qwen) sur le Mac du projet. Aller dans **Jeux d’essai → Nouveau jeu**. Saisir l’identifiant et le nom du jeu, puis les cas. Coller chaque tableau dans **Attendu d’extraction facultatif → Mentions ordonnées en JSON**. **Ajouter F10 · rév. 2** permet de reprendre le cas F10 déjà annoté. Cliquer sur **Enregistrer le jeu**, puis ouvrir le lien JSON et vérifier le texte, l’ordre et les attendus. Le fichier courant est dans `.local/qwen-lab/ecran/jeux/<id>.json`.

Pour une référence durable, conserver ce JSON fictif sous une version Git avec son identifiant. Réviser le jeu sous un nouvel identifiant quand son texte ou ses attendus changent.

## Rejouer et relever la preuve

Pour une exécution autorisée, choisir dans **Préparer un essai** le mode, la consigne, la température et le plafond, puis cliquer sur **Lancer et enregistrer la série**. En comparant deux séries, conserver les mêmes cas et attendus et faire varier un seul réglage à la fois. Dans **Séries enregistrées**, ouvrir le reçu et relever son identifiant, la copie du jeu, `expected_sha256`, les réglages `settings`, l’identité du labo `lab`, le modèle et son empreinte si disponible. Vérifier le nombre de résultats, le verdict de chaque cas et les interruptions. Une sortie JSON valide peut encore échouer au contrôle de citation ou d’attendu.

Rendre le lien local du jeu, la révision Git s’il est versionné et le reçu s’il existe. Indiquer **préparé** après relecture du jeu et **exécuté** après lecture du reçu. Le gel porte sur les cas, les critères et la configuration de l’essai. Les sorties du modèle restent des observations.
