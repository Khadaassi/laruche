---
name: domain-model
description: Modèle de domaine de La Ruche (familles, membres, personnes, tâches du jour, appareils partagés) et choix techniques associés. À lire avant de créer ou modifier un modèle Django ou une migration.
---

# Modèle de domaine — La Ruche

État à la fin de la **Phase 3** (étoiles, roue du samedi). Les règles d'accès qui
s'appliquent à ces modèles sont dans `permissions/SKILL.md`.

## Vue d'ensemble

```
accounts.User ──1:1── families.FamilyMembership ──N:1── families.Family
      │                    (role: parent | child)            │
      └──0..1:1── families.Person ──N:1──────────────────────┘
                        │  (name, avatar_color, role affiché)
                        └──1:N── tasks.Task ──1:N── tasks.TaskCompletion (task, date)

display.SharedDisplayDevice ──N:1── families.Family   (jeton d'appareil, révocable)

families.Person (enfant) ──1:N── school.SchoolDaySchedule   (jour de semaine, midi, étude)
                         └─1:N── school.SchoolDayOverride   (date précise, remplace la semaine type)

families.Family ──1:N── household.HouseholdChore ──N:1── families.Person (assigné, parent ou enfant)
                              └──1:N── household.ChoreCompletion (chore, date)

families.Family ──1:N── celebrations.Celebration (nom, date)
                              ├──1:N── CelebrationTodo (titre, qui, fait)
                              ├──1:N── GiftItem (cadeau, pour qui, apporté par, acheté)
                              └──1:N── RecipeIdea (nom, notes)

stars.StarSpend (famille, total, motif) ──1:N── stars.StarDebit (enfant, montant)
   (étoiles gagnées : déduites des TaskCompletion / ChoreCompletion des enfants)

families.Family ──1:N── saturday.SaturdayActivity (catalogue : saison, lieu, prix, étoiles, dernière fois)
                └──1:N── saturday.SaturdayPlan (samedi, statut, activité, tirages, dépense d'étoiles)
```

| App | Modèle | Rôle |
|---|---|---|
| `accounts` | `User` | Compte. Connexion par e-mail (`username` = e-mail en minuscules). Propriété `user.family`. |
| `families` | `Family` | Foyer. `name`, `invite_code` unique (normalisé : majuscules, sans espaces ni tirets). |
| `families` | `FamilyMembership` | Rattache **un compte à une seule famille** (OneToOne) avec son `role` (`parent` / `child`). Pilote les permissions. |
| `families` | `Person` | Membre **tel qu'affiché** (colonne, avatar, tâches). Lié à un `User` s'il a un compte, sinon non (jeune enfant). `role` affiché, `avatar_color`. |
| `tasks` | `Task` | Tâche récurrente d'une personne : `title`, `period` (matin/midi/soir), `weekdays` (masque de bits), `position`. |
| `tasks` | `TaskCompletion` | « Fait » pour une tâche **à une date**. Absence de ligne = à faire. Unique `(task, date)`. `completed_by` vide si coché depuis l'affichage partagé. |
| `school` | `SchoolDaySchedule` | Semaine type d'un enfant : `weekday` (0 = lundi), `lunch` (cantine / sandwich-APC / autre / pas d'école), `lunch_note`, `study`. Unique `(person, weekday)`. Pas de ligne = rien à afficher. |
| `school` | `SchoolDayOverride` | Exception pour une **date** : mêmes champs, remplace la semaine type ce jour-là. Unique `(person, date)`. |
| `household` | `HouseholdChore` | Tâche de ménage : `title`, `assignee` (toute `Person`, parent compris), `weekdays` (masque), `interval_weeks` (1 ou 2), `start_date`. Porte `family` directement. |
| `household` | `ChoreCompletion` | « Fait » pour une tâche de ménage à une date. Unique `(chore, date)`. |
| `celebrations` | `Celebration` | Fête datée (`name`, `date`), `recurs_yearly` (chaque année), `previous` (occurrence de l'année d'avant, OneToOne). |
| `celebrations` | `CelebrationTodo` | Préparatif unique : `title`, `assignee` (facultatif), `done`. |
| `celebrations` | `GiftItem` | Cadeau : `item`, `recipient` / `recipient_name`, `buyer` / `buyer_name` (personne de la famille ou nom libre), `done` (acheté). |
| `celebrations` | `RecipeIdea` | Idée de recette : `name`, `notes` libres. |
| `stars` | `StarSpend` / `StarDebit` | Dépense d'étoiles de la famille et part de chaque enfant. Les étoiles gagnées ne sont pas stockées. |
| `saturday` | `SaturdayActivity` | Activité du catalogue : `name`, `season` (toutes / 4 saisons), `place` (sortie / maison), `is_free`, `price` indicatif, `star_cost` (0 = pas d'étoiles), `last_done_on`. Catalogue de départ (18 activités) à la création d'une famille. |
| `saturday` | `SaturdayPlan` | Un samedi d'une famille (unique `(family, date)`) : `status` (tirage en cours / prévu / fait), activité proposée puis validée, `activity_name` (copie pour l'historique), `spins` (≤ 3), `star_spend`. |
| `display` | `SharedDisplayDevice` | Tablette commune autorisée par un parent. Stocke l'empreinte SHA-256 du jeton, `last_used_at`, `revoked_at`. |

## Règles métier

- **Inscription** : deux choix explicites dans le formulaire.
  - **Créer une famille** (`families.services.create_family`) : un nom suffit ; le
    **code d'invitation est toujours généré** (10 caractères aléatoires, alphabet de 31
    signes sans 0/O/1/I/L, soit ~8·10¹⁴ possibilités). Il n'est jamais choisi par
    l'utilisateur, donc jamais devinable ; il s'affiche dans les réglages du parent.
  - **Rejoindre une famille** (`families.services.join_family`) : avec le code donné par
    un parent. Un code inconnu est refusé (rien n'est créé) et compte comme une
    tentative pour le rate-limit.
- **Premier inscrit = parent**, les suivants entrent en `child`. La ligne `Family` est
  verrouillée (`select_for_update`) pendant l'inscription pour éviter deux « premiers ».
  Si une famille existe mais n'a plus aucun membre, le prochain inscrit redevient parent.
- **Compte enfant** : aucune vue dédiée ; il utilise l'écran partagé (voir « Choix
  techniques »), et n'a accès ni aux réglages, ni à la gestion des tâches, ni à
  l'activation d'un appareil.
- **Promotion** : un parent passe un compte `child` en `parent` depuis les réglages
  (`promote_to_parent`) ; le `role` de sa `Person` suit.
- **Code d'invitation régénérable** par un parent (10 caractères aléatoires, alphabet
  sans 0/O/1/I/L). L'ancien code cesse aussitôt de fonctionner.
- **Personne sans compte** : un parent peut ajouter un enfant sans compte (réglages).
- **Couleurs d'avatar** : `terracotta`, `honey`, `honey_dark`, `ink_soft`, attribuées
  en cycle à la création. Classes fond/texte dans `families.models.AVATAR_CLASSES`,
  contrastes conformes à la charte. **`sage` exclu** : il signifie « validé ».

## Périodes de la journée (`tasks/periods.py`)

Calculées sur l'**heure serveur** (`TIME_ZONE = Europe/Paris`, `timezone.localtime()`) :

| Période | De | À |
|---|---|---|
| Matin (`morning`) | 04:00 | 11:00 |
| Midi (`noon`) | 11:00 | 17:00 |
| Soir (`evening`) | 17:00 | 04:00 le lendemain |

Entre minuit et 4 h, on reste « soir », mais la date des validations est celle du jour
civil (`localdate()`). Cas marginal assumé.

## Tâches du jour (`tasks/selectors.py`)

- `tasks_for_day(family, day, people=None, period=None)` : tâches de la famille prévues
  ce jour-là (filtre sur le bit du jour de la semaine), annotées `is_done` via
  `Exists(TaskCompletion(date=day))`. Une seule requête.
- `group_by_period` (toujours les 3 périodes, dans l'ordre) et `group_by_person` (une
  colonne par personne, même sans tâche).
- `tasks.services.set_done(task, day, done)` **fixe** l'état (idempotent) au lieu de
  l'inverser : un double envoi ne produit pas une double bascule.

## École : cantine, APC, étude (`school/selectors.py`)

- **Résolution d'une journée** : exception datée si elle existe, sinon semaine type,
  sinon rien. `school_days_range(family, start, days)` calcule toute une période en deux
  requêtes (utilisé par l'accueil, l'écran partagé et le semainier).
- **Semaine type** saisie du lundi au vendredi (« — » = rien ce jour-là, « Pas d'école »
  = affiché explicitement, ex. le mercredi). Une exception peut viser n'importe quelle date,
  week-end compris ; en saisir une pour un jour qui en a déjà une la **remplace**.
- **Pattern d'exception** : le brief évoquait un `TaskException` existant ; il n'existait
  pas. Le mécanisme est donc créé ici (ligne datée prioritaire sur la règle
  hebdomadaire) et pourra être repris pour les tâches si besoin.
- **Badges** : sur la colonne de chaque enfant (écran partagé) et dans « Aujourd'hui à
  l'école » (accueil parent) : midi (cantine, sandwich, précision libre, pas d'école) et
  « Étude ce soir ». Alvéole miel + icône + texte, jamais la couleur seule.

## « À préparer pour demain » (`core/preparation.py`)

Rappels **calculés**, jamais saisis, affichés sur l'accueil parent (filtrés par le
sélecteur de personne) :
- sandwich à préparer (midi « Sandwich (APC) » demain) ;
- « Pas d'école » demain, **seulement si c'est une exception** (un mercredi habituel n'est
  pas une nouvelle) ;
- midi ailleurs avec précision (« Midi de Lina : chez mamie ») ;
- fête demain, avec le nombre de préparatifs restants.
Sur l'écran partagé, chaque colonne affiche un rappel court (« Demain : sandwich »).
Cette section n'existait pas avant la Phase 2 : elle est créée ici.

## Ménage et semainier (`household/`)

- **Récurrence simple** : « tous les jours », « chaque semaine » (jours choisis) ou
  « une semaine sur deux » (jours choisis, compté à partir de la semaine de création).
  Stockée comme les tâches enfants (masque de jours) + `interval_weeks`.
- **Pas de rotation automatique** : assignation fixe par tâche. Une rotation demande des
  règles d'équité (absences, âges, échanges) qui méritent une conception à part ; une
  rotation naïve produirait surtout des corrections manuelles.
- **Assignation à toute personne**, parents compris (contrairement aux tâches enfants).
- **Cochage** : un parent coche tout depuis le semainier. Une tâche de ménage **assignée
  à un enfant** apparaît aussi sur sa colonne de l'écran partagé (« Ménage du jour ») et
  s'y coche exactement comme ses tâches du jour (même règle de colonne, compte dans
  « X tâches restantes »). Une tâche de ménage **assignée à un parent** n'apparaît jamais
  sur l'écran partagé et n'y est pas cochable.
- **Semainier** (`/semaine/`, remplace la page « à venir ») : un bloc par jour avec fêtes,
  école de chaque enfant et ménage (cochable par un parent). Navigation de semaine en
  semaine (`?semaine=AAAA-MM-JJ`). Même assemblage (`household/week.py`) pour la version
  tablette en lecture seule (`/affichage/semaine/`, une colonne par jour).

## Fêtes (`celebrations/`)

- **Onglet dédié « Fêtes »** dans la nav parent, à la place de « Courses » (qui n'était
  qu'une page « à venir ») : la barre reste à 5 entrées lisibles sur téléphone. La liste
  de cadeaux couvre une partie du besoin « courses » pour les fêtes ; une vraie liste de
  courses pourra reprendre une place plus tard.
- **Préparatifs : modèle dédié**, pas `tasks.Task` : une tâche enfant est récurrente
  (jours, période) avec une validation par jour, un préparatif est unique et coché une
  fois pour toutes.
- **Cadeaux et recettes** : personne de la famille **ou** nom libre (grand-mère, tante…),
  car les invités ne sont pas dans l'app. Les recettes sont du texte libre, sans
  ingrédients structurés.
- **Récurrence annuelle (option « Chaque année »)**, pour les cas simples comme les
  anniversaires. Une fois la date passée, la fête est recréée l'année suivante, même jour
  et même mois (un 29 février devient le 28 hors année bissextile ; si l'app n'a pas été
  ouverte depuis plus d'un an, les années manquées sont sautées). Les fêtes dont la date
  change (Aïd) restent sans récurrence et se créent à la main : aucun calcul de calendrier
  religieux.
  - **Ce qui est repris** : nom, récurrence et **idées de recettes** (souvent les mêmes
    d'une année sur l'autre : un point de départ utile, qu'on supprime facilement).
  - **Ce qui repart de zéro** : **préparatifs** (liste vierge, comme demandé) et
    **cadeaux** : les cadeaux sont propres à chaque année (on n'offre pas deux fois le
    même vélo), les recopier créerait surtout du nettoyage.
  - **Déclenchement paresseux**, sans tâche planifiée (l'offre gratuite de Render n'en a
    pas) : `celebrations.services.roll_over_recurring(family, today)` est appelé par les
    vues qui listent des fêtes (Fêtes, semainier, « à préparer pour demain », écran
    partagé). Idempotent : `previous` est un OneToOne, une occurrence n'a qu'une suite.
- Suppression d'une fête : page de confirmation (pas de `confirm()` JS), supprime aussi
  ses préparatifs, cadeaux et recettes.

## Étoiles (`stars/`) — socle posé en Phase 3

Le brief de la Phase 3 supposait un système d'étoiles existant ; il n'y avait que
l'affichage « Fait ! +1 » et la progression **du jour** en alvéoles. Le socle est posé
ici, au plus simple et fidèle à ce que l'interface promettait déjà :

- **Gain** : +1 étoile par tâche du jour cochée **par/pour un enfant** (`TaskCompletion`
  d'une tâche d'une `Person` enfant) et +1 par tâche de ménage d'un enfant cochée
  (`ChoreCompletion`). Les étoiles **gagnées ne sont pas stockées** : elles se déduisent
  des validations existantes. Décocher retire l'étoile, sans double comptabilité.
- **Dépense** : un registre (`StarSpend` + une ligne `StarDebit` par enfant). Solde d'un
  enfant = gagnées − dépensées. Un décochage après une dépense peut rendre un solde
  négatif (cas marginal) : le pot ne compte que les soldes positifs.
- **Palier** : tous les 10 étoiles **gagnées** (`STAR_TIER`). Le palier mesure l'effort
  cumulé et ne recule jamais quand on dépense : dépenser pour la famille ne fait pas
  « perdre » un palier (aucune mécanique culpabilisante).

## Roue du samedi (`saturday/`)

### Financement d'une activité familiale en étoiles — choix retenu

**Pot commun, contribution proportionnelle au solde de chacun.**

- Le **pot** = somme des soldes positifs des enfants de la famille. Une activité qui coûte
  N étoiles est **possible si le pot ≥ N**, sinon elle est exclue du tirage et refusée à la
  validation.
- À la validation (« On y va ! »), N est réparti entre les enfants **au prorata de leur
  solde** (méthode du plus fort reste, arrondi équitable, jamais plus que le solde d'un
  enfant). Exemple : soldes 10 / 5 / 0, coût 6 → 4 / 2 / 0.
- Chaque contribution est enregistrée (qui a donné combien), visible par les parents et
  affichée sur le plan (« Lina 4 ★, Noah 2 ★ »).

**Pourquoi** :
- Une activité familiale concerne tout le monde : un pot commun la rend accessible dès que
  la famille a, ensemble, assez d'étoiles.
- Une part **égale** exigée de chaque enfant bloquerait toute la fratrie à cause d'un seul
  (et le désignerait) : contraire à la règle « jamais d'animation ni de mécanique
  culpabilisante ». Au prorata, un enfant à 0 étoile ne bloque rien et ne « doit » rien.
- Pas de saisie de contributions volontaires : ce serait une négociation à chaque samedi.
  Le calcul est automatique, prévisible et explicable aux enfants.
- Le solde de chacun reste individuel (ses étoiles, son palier) : rien ne change pour
  l'existant.
- **Annuler** un plan (avant le samedi) **rembourse** exactement les contributions.

### Tirage

- **Samedi visé** : aujourd'hui si on est samedi, sinon le prochain samedi.
- **Saison** du samedi visé (hémisphère nord, saisons météorologiques) : printemps
  mars–mai, été juin–août, automne septembre–novembre, hiver décembre–février. Les
  activités « toutes saisons » sont toujours éligibles.
- **Filtres** : coût (gratuit / peu importe / j'ai des étoiles à dépenser) et lieu
  (sortie / maison / peu importe). « Gratuit » = ni prix ni coût en étoiles. Une activité
  en étoiles n'est éligible que si le pot peut la payer.
- **Pondération contre les répétitions** : fenêtre de **8 semaines**. Poids = 1 si jamais
  faite ou faite il y a 8 semaines et plus, sinon proportionnel au temps écoulé, avec un
  plancher de 0,1 (faite la semaine dernière ≈ 10 fois moins probable, jamais impossible :
  si c'est la seule éligible, elle sort quand même).
- **Relances** : 3 tirages maximum par samedi (le premier + **2 relances**), comptés
  côté serveur quel que soit le changement de filtres. La 4e tentative est refusée avec un
  message clair. Annuler un plan validé rouvre le tirage (décision explicite d'un parent).
- Le serveur tire ; le navigateur ne fait qu'animer la roue vers le résultat déjà choisi
  (aucune triche possible en rechargeant). Pas d'IA : tirage pondéré classique.

### Catalogue de départ

18 activités génériques (pas d'adresse), pensées pour la région lilloise : musée,
médiathèque, jeux de société, ciné maison, pâtisserie, chasse au trésor, piscine,
pique-nique, ferme pédagogique, fête foraine, vélo sur voie verte, parc d'attractions,
forêt, match de foot, cirque, marché de Noël, patinoire, cabane en couvertures. Chaque
saison a au moins une activité « maison » (le tirage n'est jamais vide par mauvais temps).
Ajouté à la création de chaque famille, et par migration de données aux familles
existantes (sans doublon : seulement si la famille n'a encore aucune activité).

### Animation

La roue est dessinée en SVG côté serveur (secteurs, libellés, rotation finale) : pas de
style inline, CSP intacte. Le composant Alpine `wheel` applique la rotation via le CSSOM,
puis révèle le résultat avec une célébration (confettis hexagonaux en CSS, une seule fois).
En mouvement réduit (système ou `data-motion="reduced"`), la roue est posée directement sur
le résultat, sans rotation ni confettis. Quand peu d'activités sont éligibles, la roue est
garnie d'autres activités de la saison, pour le décor seulement.

### Plan du samedi

- « On y va ! » → plan validé (et étoiles déduites), affiché sur l'accueil parent et sur
  l'écran partagé (lecture seule pour les enfants).
- Une fois le samedi passé, ou sur « C'est fait », le plan passe dans l'historique et la
  date de dernière réalisation de l'activité est mise à jour (report paresseux, comme les
  fêtes annuelles). Un tirage non validé est abandonné une fois le samedi passé.

## Choix techniques documentés

**Authentification : vues maison sur `django.contrib.auth`, pas django-allauth.**
Besoin limité (e-mail + mot de passe + code famille) ; allauth ajouterait une dépendance,
ses gabarits et du JS à adapter à la CSP stricte, pour des fonctions dont on n'a pas
besoin aujourd'hui (connexion sociale, MFA). On garde `LoginView`/`LogoutView` de Django,
un `LoginForm` qui normalise l'e-mail et une vue d'inscription. À reconsidérer si l'on
veut la vérification d'e-mail, la réinitialisation de mot de passe ou la connexion Google.

**Rate-limit (django-ratelimit), sur les échecs seulement** (`apps/core/ratelimit.py`) :

| Action | Limites (une seule saturée suffit à bloquer) |
|---|---|
| Connexion | 20 échecs / 15 min par IP ; 10 échecs / 15 min par compte visé (e-mail) |
| Rejoindre une famille (code inconnu) | 10 / h par IP ; 100 / h au total (toutes IP) |
| Sortie du mode tablette (mot de passe parent) | 10 / 15 min par IP ; 5 / 15 min par appareil |

Une réussite ne consomme rien. Une fois bloqué, le mot de passe n'est même pas vérifié
(réponse 429). L'IP vient de la première entrée de `X-Forwarded-For` derrière Render,
qui peut être falsifiée : c'est pourquoi chaque action a aussi une limite indépendante
de l'IP (compte, appareil, ou plafond global qui borne la recherche d'un code). Les
compteurs vivent dans le cache mémoire du processus : valable avec **un seul worker
gunicorn sur une seule instance** ; ils repartent à zéro au redémarrage. Au-delà,
passer à un cache partagé (Redis).

**`username` = e-mail normalisé.** Évite un modèle `User` sans `username` (migration
lourde) tout en garantissant l'unicité de l'e-mail par la contrainte existante.

**Un compte = une famille (`OneToOneField`).** La famille de la requête n'est jamais
ambiguë. Des familles recomposées (un compte dans deux foyers) demanderaient de passer
en `ForeignKey` + choix de la famille active en session.

**`Person` séparé de `User`.** Permet d'afficher des enfants sans compte ; le rôle affiché
de la personne et le rôle de permission de l'appartenance sont distincts mais maintenus
synchronisés à la promotion.

**`Task` rattachée à la famille via `person`**, sans champ `family` dupliqué qui pourrait
diverger. Le point d'entrée des vues est `Task.objects.for_family(family)`.

**Jours de la semaine en masque de bits** (`PositiveSmallIntegerField`, bit 0 = lundi)
plutôt qu'un `ArrayField` : portable (SQLite en dev, Postgres en prod), filtrable en SQL
(`bitand`), contrainte de base `1 ≤ weekdays ≤ 127`.

**Une ligne de validation par jour** plutôt qu'un booléen sur la tâche : pas de remise à
zéro nocturne, et l'historique servira aux paliers d'étoiles.

**Affichage partagé : jeton d'appareil dédié, pas la session du parent.** Pour une
tablette posée toute la journée, laisser une session parent ouverte donnerait accès aux
réglages à n'importe qui. Un parent active le mode depuis ses réglages : l'appareil reçoit
un cookie `HttpOnly`/`Secure`/`SameSite=Lax` d'un an contenant un jeton aléatoire (seule
son empreinte est en base), la session parent est fermée. L'appareil n'a que le privilège
« enfant ». Sortie : « Mode parent » → mot de passe d'un parent de **cette** famille, qui
révoque l'appareil. Un parent connecté peut aussi ouvrir `/affichage/` en aperçu.

**Un seul chemin d'accès enfant : l'écran partagé (Phase 1.1).** Les enfants partagent un
même écran, en même temps ; aucun usage individuel sur un appareil personnel n'est prévu.
Un compte enfant n'a donc pas d'écran à lui : il est envoyé sur `/affichage/`, voit les
colonnes de tous les enfants de la famille et ne coche que la sienne. Pas de seconde
implémentation (vue « mono-enfant » ou accueil enfant) : même vue, même gabarit, même
endpoint que l'appareil partagé ; seule la liste des colonnes cochables change. Les
comptes enfants continuent d'exister parce que l'inscription par code les crée (tout
inscrit après le premier entre en `child`) et qu'ils restent la porte d'entrée avant une
promotion en parent ; le rôle `Person.role = child` sans compte reste le cas courant.

**Mobile vs tablette : deux URL, pas de détection user-agent.** `/` (vue parent) et
`/affichage/` (écran partagé). Les adaptations à la largeur passent par les breakpoints
Tailwind : lien vers l'affichage partagé visible à partir de `md` sur l'accueil parent ;
sur un écran étroit, les colonnes enfants restent côte à côte et défilent horizontalement.

**Rafraîchissement de l'écran partagé : un rechargement au changement de période**
(composant Alpine `periodClock`), pas de sondage régulier : la base Neon doit pouvoir
s'endormir (quota de 100 h de calcul par mois). Conséquence : une tâche cochée depuis un
téléphone n'apparaît sur la tablette qu'à la prochaine interaction ou période.

**Cochage optimiste.** La case change d'état immédiatement (`:has(:checked)` en CSS),
HTMX envoie l'état voulu (`hx-swap="none"`) et la réponse ne remplace que les compteurs
(`hx-swap-oob`). En cas de refus ou d'erreur réseau, `app.js` remet la case dans son état.

**URL en français** pour ce que voit l'utilisateur (`/connexion/`, `/reglages/`,
`/affichage/`) ; noms d'URL, code et modèles en anglais (`tasks:toggle`).

## Évolutions prévues

- Moteur de routines personnalisables (Phase 2) : remplacera ou enrichira `Task`.
- Semainier, menu, courses : pages « à venir » dans la nav parent.
- Paliers d'étoiles : s'appuieront sur l'historique `TaskCompletion`.
