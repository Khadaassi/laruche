# Sauvegarde de La Ruche

Chaque **dimanche à 4 h (heure de Paris en hiver)**, le workflow GitHub « Sauvegarde
hebdomadaire » copie toute la base Neon (familles, tâches, étoiles, recettes, objectifs…),
la **chiffre** et la garde **90 jours** dans GitHub (onglet *Actions* du dépôt privé →
le dernier run → *Artifacts*). On peut aussi la lancer à la main : *Actions* →
« Sauvegarde hebdomadaire » → *Run workflow*.

## Mise en place (une seule fois)

Dans GitHub : *Settings* → *Secrets and variables* → *Actions* → *New repository secret* :

| Nom | Valeur |
|---|---|
| `BACKUP_DATABASE_URL` | Neon → projet → *Connect* → décocher **Connection pooling** → copier l'URL (`postgresql://…@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`, **sans** `-pooler`) |
| `BACKUP_PASSPHRASE` | une longue phrase secrète, **notée aussi ailleurs** (gestionnaire de mots de passe) : sans elle, la sauvegarde est illisible |

Puis lancer le workflow une fois à la main pour vérifier qu'il est vert.

## Restaurer

1. Télécharger l'artefact (`laruche-AAAA-MM-JJ.dump.gpg`) depuis le run voulu.
2. Déchiffrer (outils PostgreSQL **18** ou plus, comme le serveur Neon) : `gpg --decrypt laruche-AAAA-MM-JJ.dump.gpg > laruche.dump` (demande la phrase).
3. Créer une base vide (nouvelle branche Neon de préférence), puis :
   `pg_restore --no-owner --no-privileges --clean --if-exists -d "URL_DE_LA_BASE" laruche.dump`
4. Pointer `DATABASE_URL` de Render vers cette base si besoin, redéployer.
