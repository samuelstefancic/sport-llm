# Oracles manuels du corpus de développement

**30 cas entièrement fictifs : 15 alimentaires, 10 sportifs, 5 mixtes ou ambigus.** Ils servent au développement, pas à un test final indépendant. Le [corpus](cases.json) porte exactement 10 indicateurs `manual_checks.calculation` et 10 indicateurs `manual_checks.ambiguity`. Ces 20 annotations sont des sous-ensembles des 30 cas ; elles ne créent pas 20 cas supplémentaires.

Les raisonnements et attendus ci-dessous ont été rédigés et relus manuellement par l’agent `p0_corpus`, indépendamment d’un calculateur applicatif inexistant. Python a servi à sérialiser les fichiers et contrôler les décomptes, pas à générer les résultats attendus. Cela ne constitue ni une annotation humaine indépendante, ni une preuve d’exécution Java. Tout contrôle arithmétique automatisé ultérieur doit être rapporté séparément.

## Source et conventions

Source unique : [catalogue fictif DEMO-FOOD 0.2.0](catalog.json), références pour 100 g. La version enrichit explicitement les anciennes fixtures avec glucides/lipides, quelques micronutriments et les fiches D04–D06 ; les valeurs historiques de riz/poulet/courgettes et les manques de sel et d’énergie sont conservés. Aucun catalogue externe n’a été importé. La fiche D03 n’a toujours pas de valeur énergétique.

- Contribution connue = quantité en g ÷ 100 × référence du nutriment pour 100 g.
- `complet` : toutes les contributions des aliments déclarés sont calculables pour cet apport ; `partiel` : au moins une calculable et une manquante ; `indéterminé` : aucune calculable, valeur `null`.
- Une contribution explicitement égale à zéro est connue. Les références absentes ne sont jamais remplacées par zéro.
- L’énergie vient de sa propre référence ; ne pas la reconstituer à partir des macronutriments avec une formule différente.
- Les mesures sportives viennent des déclarations. Aucune dépense énergétique n’est déduite de durée, distance, répétitions ou charge.
- `group_id` rassemble des variantes proches ; ces groupes devront rester ensemble dans de futures partitions. Aucun découpage train/test final n’est fait ici.

## Dix calculs vérifiés manuellement

| Cas | Calcul et résultat attendu | Vérification du sens |
|---|---|---|
| **F01** — sel et bilan du repas | 100 g de chaque D01/D02/D03. Sel : 1 × 0 = **0 g, partiel**, deux teneurs absentes. Énergie : 130 + 165 = **295 kcal, partiel**, D03 absent. Protéines : 2,5 + 31 + 1 = **34,5 g, complet**. Glucides : 28 + 0 + 2 = **30 g, complet**. Lipides : 0,3 + 3,6 + 0,2 = **4,1 g, complet**. | Un bilan unique à cinq lignes possède des statuts différents. Les glucides/lipides complets appartiennent à la nouvelle version 0.2.0 ; les fixtures historiques où ils étaient absents ne sont pas réécrites. |
| **F02** — quatre apports complets | 100 g de chaque D01/D02/D04. Énergie : 130 + 165 + 120 = **415 kcal**. Protéines : 2,5 + 31 + 9 = **42,5 g**. Glucides : 28 + 0 + 18 = **46 g**. Lipides : 0,3 + 3,6 + 0,4 = **4,3 g**. | Les quatre résultats sont complets : trois contributions connues pour chaque apport. D04 remplace ici les courgettes ; il ne comble pas leur énergie manquante. |
| **F03** — énergie partielle avec demi-portion | D01 50 g : 50 ÷ 100 × 130 = 65 kcal. D02 100 g : 165 kcal. D03 100 g : référence absente. 65 + 165 = **230 kcal, partiel**. | La quantité de D03 est connue ; le manque vient du catalogue. Aucune estimation des courgettes. |
| **F10** — correction | Avant : riz 150 g → 1,5 × 130 = 195 kcal ; avec poulet, 195 + 165 = 360 kcal. Après correction du riz à 100 g : 130 + 165 = **295 kcal, complet**, révision 2. Protéines après correction : 2,5 + 31 = **33,5 g, complet**. | Réduction énergétique de 65 kcal cohérente avec 50 g de riz retirés. L’ancienne révision et sa déclaration restent dans l’historique ; le résultat courant utilise 100 g. |
| **F12** — vrais zéros complets | D06 200 g : facteur 200 ÷ 100 = 2. Énergie : 2 × 0 = **0 kcal** ; protéines/glucides/lipides : 2 × 0 = **0 g** chacun. | Quatre résultats complets, puisque chaque zéro est une référence explicite de la fiche fictive. Ne pas prendre le faux logique de zéro pour une absence. |
| **F13** — changement d’échelle | D01 250 g : facteur 2,5. Énergie : 2,5 × 130 = **325 kcal**. Protéines : 2,5 × 2,5 = **6,25 g**. Glucides : 2,5 × 28 = **70 g**. Lipides : 2,5 × 0,3 = **0,75 g**. | Quatre résultats complets ; unités préservées et pas d’arrondi intermédiaire. |
| **F14** — unités des micronutriments | D04 50 g : facteur 0,5. Vitamine C : 0,5 × 4 = **2 mg**. Vitamine B9 : 0,5 × 30 = **15 µg** (code `ug`). Calcium : 0,5 × 20 = **10 mg**. | Trois apports complets distincts. Ne pas additionner ces nombres entre nutriments, ni confondre mg et µg. |
| **S01** — durées | 20 min + 10 min = **30 min** de course déclarée. | Même séance et même unité explicites. Distance et calories ne sont pas déduites. |
| **S02** — distances | 2 km = 2 000 m. 2 000 m + 750 m = **2 750 m**, soit 2,75 km. | Conversion d’unité exacte, sans hypothèse d’allure ni de dépense. |
| **S03** — répétitions | 3 séries × 10 répétitions par série = **30 répétitions**. Charge déclarée conservée : **40 kg**. | Le total de répétitions n’est ni une durée, ni une dépense énergétique. Aucun tonnage supplémentaire n’est imposé au contrat. |

## Dix ambiguïtés vérifiées manuellement

| Cas | Ce qui est connu | Ce qui empêche une conclusion complète | Attendu vérifié et première question |
|---|---|---|---|
| **F05** — quantité manquante | D01 cuit, 100 g ; poulet cuit identifié D02. | Masse du poulet absente. | Énergie du riz 130 kcal comme sous-total partiel ; pas de portion par défaut. « Quelle quantité de poulet cuit as-tu consommée, en grammes ? » |
| **F06** — cru/cuit | Riz, 100 g. | D01 cuit et D05 cru sont deux références plausibles différentes. | Pas de choix automatique : énergie `null`, indéterminée. Les résultats conditionnels seraient 130 ou 350 kcal, jamais leur moyenne. « Les 100 g de riz ont-ils été pesés crus ou cuits ? » |
| **F07** — portion inconnue | Un bol de riz cuit, D01 identifié. | Un bol n’a aucune masse définie dans la fixture. | Protéines `null`, indéterminées ; conserver « 1 bol ». « Quelle masse de riz cuit contenait ce bol, en grammes ? » |
| **F08** — volume sans conversion | 200 ml de lentilles cuites, D04 identifié. | Catalogue pour 100 g ; ni masse ni densité utilisable n’est donnée. | Énergie `null`, indéterminée ; pas de conversion 200 ml = 200 g. « Quelle est la masse de ces lentilles cuites, en grammes ? » |
| **F09** — recette inconnue | 100 g de galette maison. | Composition et référence nutritionnelle inconnues. | Aucun rapprochement inventé avec D01–D06 ; énergie `null`, indéterminée. « Quels ingrédients et quelles quantités composent cette galette ? » |
| **S05** — activité seule | Course à pied. | Durée et distance absentes. | Conserver l’activité, laisser les mesures absentes et demander une information à la fois : « Combien de temps as-tu couru ? » |
| **S06** — unité de distance absente | Course et durée 30 min ; nombre 5 déclaré. | Le 5 peut désigner une distance dans différentes unités ou une autre mesure. | Durée 30 min conservée ; distance non normalisée. « Quelle unité correspond au nombre 5 ? » |
| **S07** — unité de charge absente | Squats, 3 séries de 10 répétitions, nombre 40 pour la charge. | kg/lb ou autre unité non précisée. | Séries/répétitions conservées ; ne pas affirmer 40 kg. « Dans quelle unité est exprimée la charge de 40 ? » |
| **M02** — deux unités absentes | Mentions riz et course, nombres 30 et 20. | Unités manquantes ; état cru/cuit également inconnu pour le riz. | Ni 30 g ni 20 min supposés ; clarifications progressives. Première question : « Quelle unité correspond aux 30 de riz ? » |
| **M03** — correction sans cible | Une entrée repas et une séance existent ; nombre 100 déclaré. | Cible, champ et unité absents. | Aucune écriture ni correction automatique. Première question : « Quelle entrée veux-tu corriger ? » |

## Cas sensibles complémentaires

**F11 — réponse obsolète.** L’analyse vise r1 (150 g de riz), le repas est déjà en r2 (100 g). Attendu préparé : rejet `stale_revision`, zéro écriture de cette réponse, bilan courant 295 kcal conservé. Comparer la révision et effectuer l’écriture doivent être atomiques ; une lecture de r2 puis une écriture non conditionnelle serait insuffisante. C’est un oracle de règle métier Java pour P1, pas un test de concurrence exécuté.

**F15/S08 — entrées invalides.** Masse ou durée négative : erreur explicite, sans bilan ou séance validée. **M05 — rejeu.** Même clé, même opération, même contenu et même révision : retour du résultat existant sans duplication ; contenu différent : conflit. Aucun appel externe exactement une fois n’est garanti par cet oracle.

**M01/M04 — domaines séparés.** Les données sportives restent distinctes du bilan alimentaire. Aucun bilan calorique net n’est produit à partir d’une dépense sportive inconnue. Le choix d’affichage ne modifie pas les sources ni les valeurs calculables.

## État de vérification

Les 30 cas et leurs attendus sont préparés. Les 10 calculs et 10 ambiguïtés ci-dessus ont une revue de raisonnement d’agent ; les validations automatiques de fichiers et la contre-revue éventuelle sont consignées séparément dans les preuves P0. Les champs d’état des cas sont des états fictifs d’entrée, pas la description d’une base de données existante. Aucun service, import réel, entraînement, GPU, déploiement ou test Java n’est exécuté par ce corpus.
