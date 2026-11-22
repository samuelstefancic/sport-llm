# Concevoir et tester un comportement dans le laboratoire Qwen

Un test vérifie une règle observable sur une déclaration fictive. Le chat **llmSport · Génération des jeux de tests** prépare le texte et le tableau des mentions attendues avant que le laboratoire appelle Qwen. La [skill de préparation](../../.agents/skills/sn-qwen-test-suites/SKILL.md) fixe la procédure commune.

## Passer de la règle au cas

1. **Écrire la règle et le contre-exemple.** Si une déclaration corrige 80 g en 60 g, attendre une mention à 60 g. Prévoir un verdict d’échec si une sortie retient 80 g, ajoute une seconde mention ou perd la citation du rejet. La phrase « le JSON est valide » vérifie la forme.
2. **Choisir des déclarations qui distinguent les résultats.** Pour l’ordre, utiliser deux aliments différents. Pour une quantité absente, citer l’aliment et attendre `quantity: null`. Pour une consommation explicitement niée, attendre le tableau vide `[]`. Un champ d’attendu vide réserve le cas à l’exploration.
3. **Fixer l’attendu avant l’appel.** Reprendre des citations contiguës dans l’ordre du texte. Conserver l’état et les unités déclarés. Vérifier la forme du JSON puis relire les attendus contre la règle. Versionner la déclaration et les attendus ensemble. Si l’un change, préparer un nouveau fichier `-v2` et conserver `-v1`.

## Vérifier le premier jeu

Le [jeu `mentions-repas-v1`](../../data/dev/qwen/mentions-repas-v1.json) contient trois cas de développement.

| Cas | Contrôle à lire après l’appel |
| --- | --- |
| Lentilles puis pêches | Deux mentions dans cet ordre. 140 g de lentilles cuites. Pêches avec quantité `null` et état `unknown`. |
| Carottes, quantité corrigée | Une mention de carottes crues à 60 g. La citation inclut « 60 g et non 80 g ». |
| Repas réchauffé et consommation niée | Tableau de mentions vide. |

1. Sur le Mac du projet, ouvrir le [laboratoire 8113](http://127.0.0.1:8113/#laboratoire-qwen). Dans **Jeux d’essai**, sélectionner **mentions-repas-v1**, puis cliquer sur **Ouvrir**. Relire les trois attendus en ouvrant leurs panneaux.
2. Dans **Préparer un essai**, choisir **Sélection de passages · JSON Schema**, température **0** et plafond **256 jetons**. Garder la consigne proposée pour ce mode. Ces valeurs constituent le réglage de départ de l’exercice.
3. Cliquer sur **Lancer et enregistrer la série**. Quand elle est terminée, l’ouvrir dans **Séries enregistrées**. Relever son identifiant, les trois verdicts et, en cas d’écart, la sortie brute et les champs divergents. Vérifier le lien JSON du reçu. Le statut **Terminée** indique la fin de l’exécution.
4. Pour mesurer l’effet du schéma, rejouer le même jeu en **Sélection de passages · JSON libre**, à consigne, température et plafond identiques. Comparer les verdicts cas par cas avec le premier reçu.

## Lire le verdict et conserver la preuve

- **Échec de structure**. La sortie ne respecte pas le format requis. Examiner le JSON brut et le motif d’arrêt.
- **Échec de citation**. Examiner l’ancre et sa position dans la déclaration source.
- **Écart avec l’attendu**. Examiner le nombre et l’ordre des mentions, la citation, l’état, la quantité et l’unité. Pour les carottes, 80 g échoue même avec la bonne citation.
- **Succès**, **Exploratoire**, **Interrompu**. Compter les succès sur les cas annotés. Consigner séparément les cas exploratoires et les exécutions interrompues. Conserver le résultat de chaque cas et les deux reçus si deux modes sont comparés.

Le reçu conserve la copie du jeu, les empreintes des attendus et les réglages. Pour un nouveau lot, couvrir d’autres formulations ou ambiguïtés avec des attendus relus. Garder à part les cas destinés au test final. La décision de lancement de T11 utilise la comparaison et les critères du [plan P2](../../PLAN.md#p2--première-inférence-évaluation-et-rag).
