# RAG-01 — Récupération glucidique après un effort d’endurance chez l’adulte

**Fiche de cadrage v1.0 · 17 novembre 2026 · lot prévu en fin de P2 · 15–24 h pour le pilote lexical.** Corpus, questions, passages de référence et barème figés. Tests préparés, non exécutés. P0 est clôturé. P1 attend la décision de l’utilisateur.

Le pilote répondra en français à des questions générales sur les premières heures de récupération. Il distinguera trois mesures différentes : la **vitesse de resynthèse du glycogène musculaire**, le **temps jusqu’à épuisement** lors d’un nouvel effort et le **temps pour parcourir 20 km**. Un temps plus long indique une meilleure performance dans la deuxième mesure, un temps plus court dans la troisième. Le sous-groupe de récupération longue sert à vérifier les limites d’une conclusion à quatre heures. Java/Spring Boot conserve le calcul du bilan de repas à partir du catalogue versionné. La recherche documentaire et la synthèse relèvent de Python/FastAPI interne.

## Corpus et versions de référence

Les trois références ont été repérées dans PubMed. Les passages ci-dessous ont été vérifiés le 17 novembre 2026 dans les **textes intégraux publiés**. Les repères « résumé » désignent uniquement la partie *Abstract* de cette même version. Chaque ID du registre hérite du DOI, du PMID et de la version indiqués pour son préfixe. Les pages renvoient à la pagination imprimée de l’éditeur.

| Préfixe | Article et version consultée | Accès |
|---|---|---|
| C | Craven et al. (2021), *The Effect of Consuming Carbohydrate With and Without Protein on the Rate of Muscle Glycogen Re-synthesis During Short-Term Post-exercise Recovery: a Systematic Review and Meta-analysis*. Sports Medicine – Open 7, art. 9. Version publiée le 28 janvier 2021, HTML et PDF. DOI `10.1186/s40798-020-00297-0`. | [PMID 33507402](https://pubmed.ncbi.nlm.nih.gov/33507402/) · [Texte intégral éditeur](https://link.springer.com/article/10.1186/s40798-020-00297-0) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7843684/) |
| N | Kloby Nielsen, Lambert et Jeppesen (2020), *The Effect of Ingesting Carbohydrate and Proteins on Athletic Performance: A Systematic Review and Meta-Analysis of Randomized Controlled Trials*. Nutrients 12, art. 1483. PDF de référence du 20 mai 2020, HTML mis à jour le 17 août 2026. DOI `10.3390/nu12051483`. | [PMID 32443678](https://pubmed.ncbi.nlm.nih.gov/32443678/) · [Texte intégral éditeur](https://www.mdpi.com/2072-6643/12/5/1483) · [Historique des versions](https://www.mdpi.com/2072-6643/12/5/1483/notes) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7284704/) |
| F | Flynn, Rosales, Hailes et Ruby (2020), *Males and females exhibit similar muscle glycogen recovery with varied recovery food sources*. European Journal of Applied Physiology 120, 1131–1142. Version publiée le 25 mars 2020, HTML et PDF. DOI `10.1007/s00421-020-04352-2`. | [PMID 32215726](https://pubmed.ncbi.nlm.nih.gov/32215726/) · [Texte intégral éditeur](https://link.springer.com/article/10.1007/s00421-020-04352-2) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7181447/) |

Les trois articles sont publiés sous **CC BY 4.0**. La licence permet de copier, découper, indexer et traduire le texte avec attribution des auteurs et de la source, lien vers la licence et indication des adaptations. Vérifier le crédit individuel avant de reprendre un élément tiers. Les descriptions françaises ci-dessous sont des reformulations. [Licence CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

## Passages de référence

Les IDs désignent des passages de la publication et restent indépendants du découpage technique ou du rang de recherche. Les bornes et repères ci-dessous permettront d’associer les futurs passages indexés à ces IDs. Les valeurs entre crochets sont des intervalles de confiance à 95 %. **CHO** désigne les glucides et **PRO** les protéines.

### Craven et al. · C

Pour les différences de vitesse, l’article utilise des **mmol par kg de muscle sec et par heure**. Le signe donne le sens de la différence entre la première condition citée et son comparateur.

| ID stable | Section, page et repère | Affirmation soutenue |
|---|---|---|
| `C-AGE` | Méthodes, critères d’inclusion n° 2 et 3. [p. 3][c3] | Adultes ≥ 18 ans sans affection connue. Première biopsie dans les 30 min suivant l’effort, autre mesure au plus tard à 8 h. Définit la population et la fenêtre admissibles. |
| `C-EAU` | Résultats, comparaison CHO/témoin, du premier paragraphe à l’estimation pondérée qui renvoie à la fig. 3. [p. 6][c6] | CHO contre eau ou boisson sans nutriments, 10 essais, n = 86. Vitesse supérieure de +23,5 [19,0 à 27,9] dans l’unité ci-dessus. Huit essais de cyclisme, deux de musculation, récupération observée de 1 à 5 h. |
| `C-EAU-ABS` | Résumé, résultats, partie 1, phrase sur les dix essais et estimation qui suit. [p. 1][c1] | Même effectif, comparateur eau, différence de vitesse et intervalle. |
| `C-MIX` | Résultats, comparaison CHO+PRO/CHO, début du sous-titre et paragraphe d’estimation pondérée avant la fig. 4. [p. 6][c6] et [p. 8][c8] | 19 essais, n = 160, cyclisme ou course. CHO+PRO moins CHO seuls, +0,4 [−2,7 à +3,4] dans la même unité. Aucun avantage moyen statistiquement détecté. |
| `C-MIX-ABS` | Résumé, résultats, partie 2, phrase sur les 19 essais et estimation qui suit. [p. 1][c1] | Même effectif, différence regroupée et intervalle pour CHO+PRO contre CHO seuls. |
| `C-DEUX` | Discussion, sous-section sur CHO+PRO et la resynthèse à court terme, 2ᵉ paragraphe, références 29 et 58, jusqu’à la remarque sur les protocoles. [p. 9][c9] | Deux essais favorisent significativement le mélange. Les auteurs envisagent un apport glucidique faible et une réponse insulinique plus élevée. Ils relèvent que cette explication ne se retrouve pas dans tous les essais. |
| `C-UN` | Même sous-section, paragraphe suivant, référence 56, jusqu’à l’explication par l’oxydation du glucose. [p. 9][c9] | Un essai favorise significativement les glucides seuls. Le recours au glucose pour soutenir la synthèse protéique est une hypothèse des auteurs de cet essai. |
| `C-FEM` | Discussion, limites, premier paragraphe, phrase donnant les proportions féminines des deux comparaisons. [p. 13][c13] | Les femmes représentent 9,3 % pour CHO/témoin et 4,4 % pour CHO+PRO/CHO. Cela a empêché d’étudier l’influence du sexe sur la vitesse de resynthèse dans la revue. |

### Kloby Nielsen et al. · N

La mesure est le **temps jusqu’à épuisement** lors de l’effort suivant. Les différences moyennes ci-dessous sont en minutes, mélange CHO+PRO moins CHO seuls. Les effectifs sont ceux rapportés pour les comparaisons.

| ID stable | Section, page et repère | Affirmation soutenue |
|---|---|---|
| `N-CRIT` | Méthodes, §2.2, critères sur l’âge et le comparateur, puis définition de la récupération entre deux efforts. [p. 3][n3] | Adultes en bonne santé ≥ 18 ans, témoin CHO seuls. Les méthodes écrivent court ≤ 8 h et long ≥ 8 h. |
| `N-COURT` | Résultats, §3.4.1, les deux paragraphes précédant la fig. 6. [p. 11][n11] | Sous-groupe court, 11 essais, n = 93. Différence moyenne −0,64 min [−5,27 à +3,99], p = 0,79. L’estimation regroupe les essais de cette catégorie. |
| `N-FIG6` | Résultats, §3.4.1, fig. 6, intitulé de la comparaison, ligne du total et test de l’effet global. [p. 11][n11] | Même différence moyenne, intervalle et absence de différence significative pour le sous-groupe court. La légende seule ne fournit pas les chiffres. |
| `N-LONG` | Résultats, §3.4.2, de la définition de la durée à la dernière phrase sur Romano-Ely et Saunders. [p. 11][n11] | Les résultats écrivent **> 8 h**. Trois essais, n = 37, différence +10,59 min [+4,18 à +17,01], p = 0,001. Deux de ces essais apportaient le supplément pendant l’effort **et** la récupération. |
| `N-DUREES` | Résultats, tableau 1, colonne de durée de récupération, extrait des lignes Richardson à Karp. [p. 7][n7] | Parmi les essais du groupe court, Richardson prévoit 3 h, Qin 6 h et Karp 4 h. Le résultat regroupé au §3.4.1 porte ainsi sur plusieurs durées. |

### Flynn et al. · F

| ID stable | Section, page et repère | Affirmation soutenue |
|---|---|---|
| `F-PART` | Méthodes, participants, premier paragraphe. [p. 1132][f2] | Seize personnes en bonne santé, actives en loisir et familières de l’endurance, huit femmes et huit hommes. Les participantes utilisaient une contraception hormonale. C’est un passage de recrutement. |
| `F-PLAN` | Résumé, méthodes, du plan croisé au test cycliste final. [p. 1131][f1] | Les mêmes personnes ont essayé les deux menus. Après 90 min de cyclisme, elles ont récupéré 4 h, mangé à 0 et 2 h, puis parcouru 20 km contre la montre. |
| `F-TEMPS` | Résultats, paragraphe sur le contre-la-montre de 20 km, comparaison des menus avant la comparaison des sexes. [p. 1138][f8] | Temps moyen de 38,3 ± 4,4 min après le menu à base de pommes de terre et 37,8 ± 3,9 min après les suppléments sportifs, p > 0,05. Aucune différence significative entre menus dans cet essai. |
| `F-TEMPS-ABS` | Résumé, résultats, deuxième phrase, valeurs pour chacun des deux menus. [p. 1131][f1] | Mêmes temps sur 20 km, dans le même ordre, avec p > 0,05. |

## Questions et corrigé figés

Chaque ligne donne **tous** les groupes de passages à retrouver et les éléments à couvrir dans la synthèse. « + » exige tous les groupes. « ou » permet une substitution dans le groupe entre parenthèses. En l’absence de « ou », seul le passage désigné est accepté, en HTML ou en PDF de la version référencée. Les détails supplémentaires d’une variante, par exemple le mode d’exercice de chaque essai dans `C-EAU`, ne sont exigés que si la question les demande.

| Cas | Question soumise au pilote | Passages requis dans les cinq premiers | Éléments attendus dans la réponse |
|---|---|---|---|
| Q1 | Chez l’adulte après l’effort, de combien la prise de glucides modifie-t-elle la vitesse de resynthèse du glycogène musculaire par rapport à de l’eau ? | `C-AGE` + (`C-EAU` ou `C-EAU-ABS`) | Donner une **différence de vitesse** à court terme, +23,5 [19,0 à 27,9] mmol/kg de muscle sec/h contre eau ou témoin sans nutriments, chez des adultes sans affection connue, fenêtre d’inclusion ≤ 8 h. |
| Q2 | Chez l’adulte, ajouter des protéines aux glucides accélère-t-il en moyenne la resynthèse du glycogène musculaire dans les huit heures suivant l’effort ? | `C-AGE` + (`C-MIX` ou `C-MIX-ABS`) | Sur 19 essais, +0,4 [−2,7 à +3,4] mmol/kg de muscle sec/h pour CHO+PRO par rapport aux CHO seuls. L’intervalle inclut zéro. Distinguer l’absence d’avantage moyen détecté d’une preuve d’équivalence. |
| Q3 | Pour la resynthèse du glycogène après l’effort chez l’adulte, quels essais divergent lorsque l’on compare **glucides avec protéines et glucides seuls** ? Que conclut l’analyse regroupée et comment les auteurs expliquent-ils ces écarts ? | `C-DEUX` + `C-UN` + (`C-MIX` ou `C-MIX-ABS`) | Identifier les deux essais en faveur du mélange (réf. 29 et 58) et celui en faveur des glucides seuls (réf. 56). Sur les 19 essais à court terme, donner la différence regroupée de +0,4 [−2,7 à +3,4] mmol/kg de muscle sec/h. Relier chaque hypothèse à son passage de discussion. Aucun mécanisme causal établi. |
| Q4 | Chez l’adulte, l’ajout de protéines aux glucides pendant une récupération courte prolonge-t-il le temps jusqu’à épuisement lors de l’effort suivant ? | `N-CRIT` + (`N-COURT` ou `N-FIG6`) | Pour ≤ 8 h, −0,64 min [−5,27 à +3,99] pour CHO+PRO par rapport à CHO seuls. Aucun allongement statistiquement détecté. |
| Q5 | Chez l’adulte qui reprend un effort d’endurance **après quatre heures de récupération**, quelle différence de temps jusqu’à épuisement peut-on attribuer à l’ajout de protéines aux glucides ? Le résultat après récupération longue s’applique-t-il à ces quatre heures ? | `N-COURT` + `N-LONG` + `N-CRIT` + `N-DUREES` | Citer explicitement les **§§3.4.1 et 3.4.2**. Quatre heures entrent dans le groupe court. Donner les deux différences et IC en minutes. Le −0,64 est regroupé sur plusieurs durées, le +10,59 concerne le groupe long. Aucune estimation regroupée propre à 4 h dans ces sections. Signaler **> 8 h** dans les résultats et **≥ 8 h** dans les méthodes, sans trancher le classement de 8 h exactement. |
| Q6 | Après quatre heures de récupération, quel temps sur 20 km les cyclistes de l’essai croisé de Flynn ont-ils réalisé selon le menu consommé ? | `F-PART` + `F-PLAN` + (`F-TEMPS` ou `F-TEMPS-ABS`) | Dans cet échantillon de 16 adultes actifs de loisir, associer 38,3 ± 4,4 min au menu à base de pommes de terre et 37,8 ± 3,9 min aux suppléments sportifs. Même distance et mêmes participants. La différence observée entre menus n’est pas significative. |
| Q7 | Quelle place les femmes occupaient-elles dans les comparaisons de Craven et dans l’essai de Flynn ? Que permet cette représentation ? | `C-FEM` + `F-PART` | Associer 9,3 % et 4,4 % aux bonnes comparaisons. Chez Flynn, 8 femmes et 8 hommes actifs de loisir. Craven n’a pas pu analyser l’influence du sexe. Le petit échantillon équilibré de Flynn ne suffit pas à généraliser à toutes les sportives. |
| Q8 | Peut-on appliquer à un coureur de **14 ans** les conclusions de ces revues sur le glycogène musculaire et le temps jusqu’à épuisement ? | `C-AGE` + `N-CRIT` | **Abstention explicite** sur l’effet chez cet adolescent. Les deux revues ont inclus des adultes ≥ 18 ans. Citer les deux critères pour expliquer la limite de population. |

### Abstention et contrôle des citations

Ces trois cas ont un verdict de synthèse chacun. Ils sont hors du dénominateur de recherche Q1–Q8.

| Cas | Entrée exacte | Attendu |
|---|---|---|
| Q9 | L’ajout de protéines aux glucides après un effort d’endurance réduit-il les blessures sur une saison chez l’adulte ? | **Abstention explicite.** Aucun passage du corpus ne soutient une conclusion sur l’incidence des blessures au cours d’une saison. Une absence de blessure à l’inclusion dans `F-PART` ne mesure pas ce résultat. |
| Q10a | Le passage `F-PART` de Flynn montre que le menu à base de pommes de terre améliore de 20 % le temps sur 20 km après quatre heures, par rapport aux suppléments sportifs. Confirmez-vous ? | Rejeter ce soutien précis : le passage existe et décrit les participants. Rectifier à partir de `F-PLAN` + (`F-TEMPS` ou `F-TEMPS-ABS`). Donner les deux temps avec leurs menus et préciser qu’ils n’étayent pas le gain de 20 %. Si le résultat manque dans les passages retrouvés, le dire et laisser la correction chiffrée incomplète. |
| Q10b | Vérifiez le gain de 20 % sur le contre-la-montre en vous appuyant sur le passage `F-TT-999`. | Rejeter **l’identifiant inexistant** après consultation du registre. Ne lui attribuer ni URL ni contenu et ne confirmer aucun gain. Une citation de remplacement ne valide pas l’identifiant soumis. |

## Barème fixé avant exécution

**Recherche lexicale.** Poser Q1–Q8 séparément, sans IDs ni corrigé. Rechercher dans les passages anglais des articles avec PostgreSQL et un petit lexique français–anglais (p. ex. « jusqu’à épuisement » / *time to exhaustion*). Le texte des questions, le corrigé et les reformulations de cette fiche restent hors index. Conserver les cinq premiers passages distincts dans l’ordre, avec ID, article, version, section et texte effectivement transmis. Une figure compte si ses données pertinentes sont lisibles dans le passage transmis. Un lien, une légende sans chiffres ou un paragraphe voisin non transmis ne suffit pas.

Une question vaut **1** si chacun de ses groupes obligatoires est couvert dans ces cinq résultats, **0** sinon. Un même passage retourné peut couvrir plusieurs repères si leurs contenus y figurent effectivement. Publier les huit verdicts et, pour chaque échec, le groupe manquant et son premier rang s’il est connu. **Acceptation : au moins 7/8, avec Q3 et Q8 réussies toutes les deux.**

**Synthèse.** Évaluer les 11 cas dans deux conditions et publier deux séries de résultats distinctes, avec le même modèle, les mêmes consignes et les mêmes questions. En première passe, fournir les passages canoniques du corrigé (première variante de chaque groupe). En seconde passe, fournir uniquement les passages réellement retrouvés. Pour Q9, la première passe n’a aucun passage pertinent. Pour Q10a, joindre dans les deux passes le passage contesté, identifié comme tel. Pour Q10b, soumettre la chaîne invalide dans les deux passes et rendre disponible la vérification d’existence dans le registre. Le texte de la question n’est jamais une preuve.

| Axe noté séparément, dans chaque passe | Règle de décision |
|---|---|
| Couverture des attendus | Cocher chaque élément de la ligne du corrigé. Une question est complète si tous ses éléments sont présents et justes, y compris la population, la durée, le comparateur et les unités quand ils conditionnent l’interprétation. Publier les éléments couverts/attendus par question et le nombre de questions complètes sur 11. Une abstention honnête devant un passage manquant peut être fidèle et laisser une réponse incomplète. |
| Fidélité des affirmations et des citations | Pour chaque affirmation importante, vérifier qu’un passage fourni dans la passe la soutient avec le bon résultat, le bon sens de comparaison et le bon degré de certitude. Exiger l’ID du passage, le DOI ou PMID, le lien et la section ou page. Compter séparément les affirmations soutenues/affirmations vérifiables, les affirmations sans preuve, les citations inventées et les citations hors sujet utilisées comme preuves. Une abstention sans affirmation scientifique a un ratio sans objet. |
| Acceptation de la synthèse | Exiger la couverture complète des éléments du corrigé pour déclarer la passe entièrement conforme, 100 % des affirmations scientifiques soutenues, **zéro citation inventée ou hors sujet**, abstentions explicites en **Q8 et Q9** et verdicts corrects **distincts** pour **Q10a** (pertinence) et **Q10b** (existence). Mentionner un passage pour en expliquer le rejet est correct. Conserver séparément les verdicts des deux passes et celui de la recherche. |

## Ticket prévu en fin de P2

**Dépendances.** Une décision de lancement distincte, une première inférence Python exploitable et la possibilité de tracer l’évaluation de P2. Le futur lot préparera le manifeste d’attribution et de versions, récupérera les textes autorisés, puis figera leurs empreintes et la correspondance entre segments et IDs avant toute mesure. Un changement d’article, de repère ou de règle après une exécution impose une version distincte du jeu. Les 11 cas documentaires sont séparés des 30 cas métier de P0.

| Livrable du futur lot lexical | Effort estimé |
|---|---:|
| Trois textes autorisés, manifeste de provenance et passages repérables | 3–5 h |
| Index PostgreSQL, lexique français–anglais et recherche des cinq premiers passages | 4–6 h |
| Synthèse avec citations vérifiables, limites de population et abstention | 4–6 h |
| Deux passes d’évaluation, traces de classement et de réponses, analyse des erreurs dans MLflow | 4–7 h |
| **Total du pilote lexical, compté une fois en fin de P2** | **15–24 h** |

Une comparaison avec des embeddings se décidera à partir des passages effectivement manqués par la recherche lexicale, par exemple si une paraphrase française échappe au lexique malgré la présence d’un passage pertinent en anglais. Le choix d’un modèle d’embeddings et sa mesure relèveraient d’un lot ultérieur. À ce stade, la vérification porte sur les références et la cohérence de la fiche. Collecte du corpus, indexation, inférence et tests du pilote restent à lancer.

[c1]: https://link.springer.com/content/pdf/10.1186/s40798-020-00297-0.pdf#page=1
[c3]: https://link.springer.com/content/pdf/10.1186/s40798-020-00297-0.pdf#page=3
[c6]: https://link.springer.com/content/pdf/10.1186/s40798-020-00297-0.pdf#page=6
[c8]: https://link.springer.com/content/pdf/10.1186/s40798-020-00297-0.pdf#page=8
[c9]: https://link.springer.com/content/pdf/10.1186/s40798-020-00297-0.pdf#page=9
[c13]: https://link.springer.com/content/pdf/10.1186/s40798-020-00297-0.pdf#page=13
[n3]: https://rcastoragev2.blob.core.windows.net/0e8265ea499bf5f4b9c0359d9b77bab2/PMC7284704.pdf#page=3
[n7]: https://rcastoragev2.blob.core.windows.net/0e8265ea499bf5f4b9c0359d9b77bab2/PMC7284704.pdf#page=7
[n11]: https://rcastoragev2.blob.core.windows.net/0e8265ea499bf5f4b9c0359d9b77bab2/PMC7284704.pdf#page=11
[f1]: https://link.springer.com/content/pdf/10.1007/s00421-020-04352-2.pdf#page=1
[f2]: https://link.springer.com/content/pdf/10.1007/s00421-020-04352-2.pdf#page=2
[f8]: https://link.springer.com/content/pdf/10.1007/s00421-020-04352-2.pdf#page=8
