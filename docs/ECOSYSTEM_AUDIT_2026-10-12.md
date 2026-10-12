# Audit général de l’écosystème Existence — 12 octobre 2026

Cet audit classe les produits selon leur aptitude à être utilisés maintenant, leur
cohérence avec les autres univers et le risque avant une diffusion plus large.
Les notes ne sont pas des promesses de parité avec des logiciels installés depuis
des années : elles indiquent où chaque produit est réellement prêt et quel
chantier apporte le plus de valeur.

## Décisions de version

### Nebula 26.4.1 — correctif, avant 26.5.0

La 26.4.0 a beaucoup étendu le moteur de dessin. La 26.4.1 doit rester une
version courte de stabilisation, sans nouvelle fonction majeure : session réelle
à la tablette, gros PSD, Undo/Redo, visibilité des calques, démarrage et
raccourcis. Après cette qualification, la 26.5.0 devient la grande version
painting : comportement des médiums, assistants, bibliothèque de ressources,
qualité de la toile et constance du geste.

## Priorités transversales

1. **Fiabilité livrée.** Chaque univers doit avoir une commande de vérification,
   une ouverture sans erreur, un format versionné et une restauration de session
   sûre.
2. **Installation et mises à jour.** Existence devient la source unique pour
   télécharger, préparer, mettre à jour et retirer les applications sans casser
   un répertoire contenant du travail local.
3. **Wormholes et ressources.** Un lien en direct doit annoncer sa version, son
   profil couleur et son état de synchronisation ; aucun export manuel ne doit
   être requis dans le parcours normal.
4. **Performances mesurées.** Toute promesse de fluidité doit être associée à un
   fichier, une machine et une mesure reproductible.

## État par application

| Application | Usage actuel | État | Priorité | Prochain chantier qui compte |
| --- | --- | --- | --- | --- |
| Nebula 26.4.0 | Dessin raster | Solide en progression | P0 | 26.4.1 de stabilisation, puis 26.5 painting |
| Nova 26.3.0 | RAW et photo produit | Prête pour un flux encadré | P0 | Qualifier tes DNG réels, export boutique et gestion de séries |
| Ephemeris 26.2.0 | Mise en page / impression | Fondation avancée | P0 | Typographie, prépresse et finition du PDF de production |
| Existence 26.1 | Hub et écosystème | En consolidation | P0 | Catalogue installé/mis à jour, état des liens et publication des paquets |
| StarDust 26.1 | Création de ressources | Très prometteur | P1 | Performance du graphe, publication de ressources, contrats avec Nebula |
| Atlas 26.1 | Illustration vectorielle | Base propre | P1 | Rendu GPU, import SVG et finition de l’édition vectorielle |
| Cosmos 26.0 | Connaissances / notes | Fonctionnel et riche | P2 | Qualification des gros coffres, synchronisation et moins de complexité UI |
| Pulsar 0.3 alpha | Animation / compositing | Alpha | P1 | Compositeur GPU, précompositions, masques et rendu asynchrone |
| Singularity 26.1.0 | Export d’images statiques | PNG, JPEG, WebP, lots et rapports | P2 | Qualifier les profils d’export et les gros lots réels |

## Constats détaillés

### Nebula

La 26.4.0 est devenue une base sérieuse de painting : pinceau natif, dynamique
stylet, `.abr`, textures, symétrie radiale, historique solide, 26 modes de
fusion et optimisation des gros PSD. Le cap est correct : Nebula ne doit pas
se diluer en clone de Photoshop orienté photomontage. Les manques qui restent
pour en faire une référence du dessin sont la profondeur des médiums, une
bibliothèque de ressources mature, les assistants et une qualification longue
sur matériel de production.

### Nova

Nova est l’un des produits les plus proches d’un usage concret : RAW/DNG,
réglages non destructifs, masques, catalogue, XMP, exports par lot et lien
vivant avec Nebula/Ephemeris sont présents. Les 49 tests sont verts. La
priorité n’est pas d’ajouter des panneaux : il faut qualifier le flux de photos
produit réel, la cohérence des exports sRGB, les profils d’impression et le
traitement d’une série complète sans surprise.

### Ephemeris

La base document, styles, liens, préflight, packaging, CMJN et lien Nova est
plus avancée que sa présentation ne le laisse penser. Les 67 tests sont verts.
Le risque avant une utilisation professionnelle proche d’InDesign reste dans la
mise en forme : composition typographique, débordements, styles complexes,
PDF/X avec intention de sortie, polices et gestion des erreurs de liens. C’est
le chantier professionnel prioritaire après la stabilisation de Nebula.

### Existence

Le hub possède désormais un catalogue capable de télécharger depuis des sources
officielles, d’installer dans une zone temporaire puis de publier une
installation complète, de vérifier le runtime Python, de protéger les dossiers
modifiés lors d’une mise à jour et de désinstaller sans supprimer un processus
ouvert. Il reste à publier un catalogue distant signé, les paquets stables et
une vue consolidée des mises à jour de tout l’écosystème.

### StarDust

StarDust a une vraie proposition différenciante : fabriquer des pinceaux,
fusions, palettes, gradients, scripts et textures procédurales par graphe, puis
les publier comme ressources compatibles. Les 19 tests ciblés sont verts. Le
point à surveiller est la multiplication de modules et de nœuds : le contrat de
ressource, l’aperçu instantané, les migrations et la publication doivent rester
plus simples que le graphe lui-même.

### Atlas

Atlas a une base C++ vectorielle saine, des tests natifs verts, un format `.atlas`
versionné et un pont correct vers Nebula. Son principal écart est structurel :
le rendu courant repose encore sur Cairo/CPU et l’import SVG est volontairement
partiel. Le renderer GPU et une meilleure fidélité SVG seront bien plus utiles
que de nouveaux outils isolés.

### Cosmos

Cosmos est riche : notes, graphes, import Notion, bases de données, navigation
et coffre local. Ses documents annoncent une architecture performante, mais le
projet manque actuellement de tests automatisés facilement exécutables depuis
le dépôt. Avant d’ajouter des vues, il faut transformer les vérifications de
coffres importants, d’imports et de fermeture en tests de CI reproductibles.

### Pulsar

Pulsar est clairement déclaré alpha, ce qui est sain. Le modèle, la timeline,
l’import média et le rendu headless sont déjà structurés ; le test C++ passe.
Mais le compositeur final reste CPU, sans précompositions ni masques, et les
effets sont encore déclaratifs. Il ne doit pas être présenté comme un outil de
production 4K avant un compositeur GPU et une file de rendu réellement robuste.

### Singularity

Singularity fait correctement de la conversion WebP simple mais ne possède ni
documentation produit ni tests automatisés visibles. Sa prochaine version doit
être un outil de livraison fiable : presets web, conversions par lot annulables,
rapport de sortie, conservation contrôlée des métadonnées et tests d’images.

## Vérification effectuée pour cet audit

- Nova : 49 tests, 1 ignoré — réussis.
- StarDust : 19 tests — réussis.
- Ephemeris : 67 tests — réussis.
- Atlas : 4 tests CTest — réussis.
- Pulsar : 1 test CTest — réussi.
- Singularity : les deux points d’entrée Python compilent.
- Existence : 99 tests ciblés — réussis lors de la dernière passe.

## Ordre de travail recommandé

1. Terminer la qualification Nebula 26.4.1 avec tes vérifications.
2. Passer Ephemeris en parcours de mise en page réellement utilisable pour tes
   publications, avec Nova comme source d’images liée.
3. Finir Nova sur tes DNG et tes exports de produits.
4. Publier Existence comme hub stable de mise à jour, avec paquets et catalogue
   distant signé.
5. Faire évoluer StarDust et Nebula ensemble autour des ressources de painting.
6. Donner à Atlas son renderer GPU ; ne lancer Pulsar qu’après ce noyau commun.
7. Stabiliser Singularity, puis Cosmos, autour de cas d’usage précis plutôt que
   d’augmenter leur surface fonctionnelle.
