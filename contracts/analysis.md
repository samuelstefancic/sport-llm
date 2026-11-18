# T03 — contrat canonique 0.1.0

Autorité machine unique : [analysis.schema.json](analysis.schema.json), dialecte JSON Schema Draft 2020-12, identifiant `urn:llmsport:analysis:0.1.0`. La version de contrat est distincte des versions de catalogue et des révisions du repas. Les exemples sont des fixtures fictives ; aucun service Java/Python ni modèle ne les a produits.

Le [manifeste des exemples](examples/manifest.json) fixe les acceptations/rejets attendus avant validation. Le [corpus](../data/dev/cases.json) contient des demandes et oracles de développement, pas une seconde définition des messages API. Les types Java/Python futurs devront rester dérivés du schéma canonique lorsque possible, sinon validés contre lui ; pas deux contrats manuels concurrents.

## Frontière des messages

| Branche | Émetteur autorisé dans le produit futur | Sens |
|---|---|---|
| `python_proposal` | Service Python interne | Mentions extraites, quantités proposées, candidats de catalogue, ambiguïtés. `entry_id` et `entry_revision` sont ceux de l'entrée analysée fournie par Java. Pour `entry_kind=meal`, ils identifient le repas et sa révision. Aucune validation finale, total nutritionnel ou écriture du journal. |
| `java_nutrition_report` | Java | Bilan unique du repas déclaré, à `meal_revision`, avec les apports sélectionnés et leurs contributions/manques. |
| `java_analysis_rejection` | Java | Motif `stale_revision` ou `invalid_proposal`, révision analysée et révision courante. Aucun bilan à appliquer. |

**La réception d'une réponse Python doit valider exclusivement la branche `#/$defs/python_proposal`.** Valider seulement l'union racine permettrait d'accepter la forme d'un rapport Java envoyé par Python. `kind` distingue les formes ; ce n'est ni une authentification ni une autorisation. Java construit les rapports à partir des données validées et des références réellement consultées. Une référence de catalogue fournie par le modèle n'est pas une preuve de sa véracité.

Une proposition peut porter alimentation, sport ou les deux (`entry_kind`). Les mesures sportives restent déclaratives : durée, distance, séries, répétitions et charge. Aucune dépense énergétique n'est déduite. Les résultats de persistance sportive et l'enveloppe HTTP restent à implémenter en P1 ; ce contrat ne crée aucun endpoint. Une entrée mixte doit être orientée par Java vers ses domaines, sans fusionner dépense inconnue et apport alimentaire.

## Bilan et unités

Par défaut : `energy`, `protein`, `carbohydrate`, `fat`. La sélection explicite peut inclure `fiber`, `sugars`, `salt`, puis des identifiants individuels `vitamin_*` et `mineral_*` effectivement connus du catalogue. La sélection du corpus est un paramètre fictif de la demande, distinct du texte libre. Elle ne change pas les données sources.

Chaque ligne porte `id`, `unit`, `value`, `status`, `provenance`, `missing`. Dans 0.1.0 : énergie en kcal ; macronutriments/fibres/sucres/sel en g ; micronutriments en mg ou ug (`ug` s'affiche µg). Java doit vérifier l'identifiant et l'unité précis dans le catalogue : le préfixe `vitamin_` ne suffit pas à autoriser un nouveau nutriment. Aucune conversion implicite sodium/sel.

| Statut | Valeur | Contributions connues | Manques |
|---|---|---|---|
| `complet` | Nombre ≥ 0 | Au moins une ; toutes les mentions du repas couvertes | Aucun |
| `partiel` | Nombre ≥ 0, sous-total | Au moins une, même explicitement égale à zéro | Au moins un |
| `indéterminé` | `null` | Aucune | Au moins un |

Une provenance de contribution lie quantité en g et déclaration/correction d'origine, valeur de référence et base en g, catalogue/version/fiche/champ, puis valeur de contribution. Les références de chaque ligne utilisent la même unité que le résultat. Les portions/volumes non convertibles et les traces non quantifiées restent des manques motivés. Pour une mention non résolue, `item_id` désigne la mention stable, pas un identifiant d'aliment inventé. La source d'un manque pointe vers la déclaration ou la fiche concernée.

La contribution est quantité_g / base_g × référence ; le résultat est la somme des contributions connues. L'énergie conserve sa propre référence : elle n'est pas reconstruite à partir des macronutriments. Les exemples gardent une précision décimale exacte sans arrondi intermédiaire ; l'arrondi de présentation P4 ne modifie pas les valeurs sources.

## Ce que le schéma vérifie et ce que Java devra vérifier

Le schéma vérifie types, champs obligatoires et interdiction des champs supplémentaires, version, branches, valeurs non négatives, compatibilité mesure/unité, unités de référence, et cohérence structurelle des trois statuts. Une structure ambiguë est valide si les inconnues sont explicites ; sa validité n'autorise pas une complétion inventée.

Règles métier **à implémenter et tester en P1** :

1. Authentifier le service/origine et sélectionner la branche attendue ; rattacher chaque déclaration et proposition à l'entrée, l'utilisateur et la révision réellement analysés.
2. Vérifier catalogue/version/fiche/champ, quantité, état cru/cuit, unité et valeur dans les sources autorisées ; ne pas recopier aveuglément les nombres proposés.
3. Garantir un seul résultat par identifiant d'apport, égalité exacte entre sélection et lignes, identifiants de mentions uniques, et couverture de chaque mention du repas une fois dans contributions ou manques. Aucun chevauchement ou aliment omis pour déclarer « complet ».
4. Recalculer contributions, sommes et statuts. Vérifier les conversions autorisées ; demander une clarification lorsque les informations sont insuffisantes. Le schéma n'établit ni vérité des données ni exactitude d'une addition.
5. Vérifier la révision courante **atomiquement avec l'application du résultat**, et conserver correction/historique/idempotence.

Les exemples `business-invalid-wrong-total`, `business-invalid-duplicate-nutrient` et `business-invalid-python-forges-java-report` sont volontairement conformes à l'union racine ; leur rejet appartient respectivement au recalcul, aux invariants métier et à la branche de réception/origine. Les preuves locales contrôlent les fixtures ; elles ne prouvent aucune implémentation Java.

## Révision obsolète : règle transactionnelle Java

Le [scénario T03-STALE-001](examples/revision-scenario.json) démarre une analyse en r1 sur 150 g de riz. La correction utilisateur est enregistrée en r2 à 100 g avant l'arrivée de la proposition r1. La proposition reste structurellement valide ; Java doit produire `stale_revision` et ne modifier ni correction, ni bilan courant, ni révision avec cette réponse.

La comparaison et l'écriture doivent être indivisibles : transaction avec contrôle de concurrence effectif (verrouillage approprié ou opération conditionnelle/CAS sur révision). Une simple lecture suivie d'une écriture non protégée, même dans une transaction sans contrôle suffisant, ne satisfait pas la règle. Si une correction intervient après une lecture préparatoire, la condition doit encore être vérifiée à l'écriture. La révision concerne l'état de l'entrée utilisé pour le calcul, pas la version de catalogue ou du schéma.

Critères P1 : retour tardif r1 après r2 ; course entre correction et résultat ; même révision acceptée une seule fois selon idempotence ; rejeu ancien n'écrasant pas une révision plus récente ; même clé avec contenu différent en conflit. Préserver les nouvelles données lors d'une reprise. Ces tests Java/base de données sont **NOT_RUN en P0**. Le fichier de rejet est un exemple attendu, pas la sortie d'un service lancé.

## Sources fictives et évolution

Le [cas du sel historique](examples/java-salt-reference.json) reprend `DEMO-FOOD 0.1-salt-variant` : sel 0 g partiel, énergie 295 kcal partielle, protéines 34,5 g complètes, glucides/lipides indéterminés. Le [catalogue enrichi 0.2.0](../data/dev/catalog.json) fournit de nouvelles valeurs fictives explicites : F01 peut alors avoir glucides/lipides complets, sans modifier l'ancien catalogue. F02 et [l'exemple quatre apports](examples/java-macros-complete.json) utilisent riz/poulet/lentilles : 415 kcal, 42,5 g, 46 g et 4,3 g, tous complets.

Toute évolution publiée du contrat change sa version et son identifiant, avec exemples et vérification de compatibilité ; ne pas modifier silencieusement une version déjà utilisée. Les messages d'une autre version sont rejetés par 0.1.0. Les descriptions de P0 ne sont ni une installation de framework ni une décision de déploiement.

Référence du dialecte : [JSON Schema Validation 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation). Les contrôles locaux utilisent un validateur existant, sans téléchargement du schéma ni installation de dépendances ; environnement observé et limites dans les preuves P0.
