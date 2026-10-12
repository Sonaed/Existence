# Socle transversal Existence

La commande commune de contrôle est :

```bash
python /home/deanos/Documents/Existence/tools/verify_ecosystem.py --root /home/deanos/Documents
```

Elle est non destructive : elle vérifie les points d’entrée, les formats et
versions déclarés, ainsi que le mécanisme de reprise connu. Une absence de
manifest ou de reprise est affichée comme un avertissement à traiter, jamais
masquée par une promesse de fiabilité.

Atlas et Pulsar restaurent uniquement le dernier document déjà enregistré :
le chemin de session est écrit de façon atomique et un fichier manquant est
ignoré. Cette reprise ne crée jamais de document ni n'écrase un travail local.

Les performances sont publiées sous `existence.benchmark.v1`. Chaque mesure
doit déclarer l’application, le scénario, le fichier d’entrée, la commande,
le nombre d’échantillons, la révision source et la machine. Une mesure sans ces
champs ne peut pas servir de revendication de fluidité.

```bash
python /home/deanos/Documents/Existence/tools/verify_benchmarks.py --root /home/deanos/Documents
```

Les liens directs utilisent `existence.wormhole-link.v2`. Ils annoncent la
révision de ressource, le mode couleur, le profil ICC et le statut d’application
de chaque côté. Les liens historiques restent lisibles ; la mise à jour de leur
schéma se fait en mémoire jusqu’à leur prochaine publication.
