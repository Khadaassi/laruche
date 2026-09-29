---
name: domain-model
description: Modèle de domaine de La Ruche (familles, membres, personnes, tâches du jour, appareils partagés) et choix techniques associés. À lire avant de créer ou modifier un modèle Django ou une migration.
---

# Modèle de domaine — La Ruche

État à la fin de la **Phase 4** (menu de la semaine, recettes, liste de courses).
Les règles d'accès qui
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
                              │                 └─N:0..1── families.Person (en alternance avec)
                              ├──1:N── household.ChoreCompletion (chore, date)
                              └──1:N── household.ChoreSwap (chore, semaine : échange des rôles)

families.Family ──1:N── celebrations.Celebration (nom, date)
                              ├──1:N── CelebrationTodo (titre, qui, fait)
                              ├──1:N── GiftItem (cadeau, pour qui, apporté par, acheté)
                              └──1:N── RecipeIdea (nom, notes)

stars.StarSpend (famille, total, motif) ──1:N── stars.StarDebit (enfant, montant)
families.Person (enfant) ──1:N── stars.DayStar (date, fêtée)   (une étoile par journée complète)
                         └─0..1── stars.StarOpeningBalance (étoiles, motif)   (solde de départ)

families.Family ──1:N── saturday.SaturdayActivity (catalogue : saison, lieu, prix, étoiles, dernière fois)
                └──1:N── saturday.SaturdayPlan (samedi, statut, activité, tirages, dépense d'étoiles)

families.Family ──1:N── meals.Recipe (nom, préparation, favori)
                │            ├──1:N── RecipeIngredient (nom, quantité, unité)
                │            └──1:N── RecipeStep (n°, texte)
                ├──1:N── meals.MealSlot (date, déjeuner/dîner, recette OU repas libre)
                ├──1:N── shopping.ShoppingItem (article, quantité, unité, origine, état)
                └──1:1── shopping.ShoppingTransfer (dernière semaine envoyée aux courses)
```

| App | Modèle | Rôle |
|---|---|---|
| `accounts` | `User` | Compte. Connexion par **identifiant court ou e-mail** : `login_name` facultatif, unique, en minuscules (« khadija », « enfants ») ; `username` = e-mail en minuscules (ou `username` interne aléatoire pour un compte écran partagé, sans e-mail). Propriété `user.family`. |
| `families` | `Family` | Foyer. `name`, `invite_code` unique (normalisé : majuscules, sans espaces ni tirets). |
| `families` | `FamilyMembership` | Rattache **un compte à une seule famille** (OneToOne) avec son `role` (`parent` / `child` / `display`). Pilote les permissions. `display` = compte « écran partagé » : jamais de `Person`, au plus un par famille. |
| `families` | `Person` | Membre **tel qu'affiché** (colonne, avatar, tâches). Lié à un `User` s'il a un compte, sinon non (jeune enfant). `role` affiché, `avatar_color`. |
| `tasks` | `Task` | Tâche récurrente d'une personne : `title`, `period` (matin/midi/soir), `weekdays` (masque de bits), période facultative `start_date` / `end_date`, `position` (ordre choisi par le parent). |
| `tasks` | `TaskCompletion` | « Fait » pour une tâche **à une date**. Absence de ligne = à faire. Unique `(task, date)`. `completed_by` vide si coché depuis l'affichage partagé. |
| `school` | `SchoolDaySchedule` | Semaine type d'un enfant : `weekday` (0 = lundi), `lunch` (cantine / sandwich-APC / autre / pas d'école), `lunch_note`, `study`. Unique `(person, weekday)`. Pas de ligne = rien à afficher. |
| `school` | `SchoolDayOverride` | Exception pour une **date** : mêmes champs, remplace la semaine type ce jour-là. Unique `(person, date)`. |
| `household` | `HouseholdChore` | Tâche de ménage : `title`, `assignee` (toute `Person`, parent compris), `alternate` (facultatif : alternance hebdomadaire avec une autre personne, seulement si `interval_weeks = 1`, contrainte en base), `weekdays` (masque), `interval_weeks` (1 ou 2), `start_date`. Porte `family` directement. |
| `household` | `ChoreSwap` | Échange des rôles d'une tâche en alternance à partir de la semaine du lundi `week`. Unique `(chore, week)`. |
| `tasks` | `HomeworkCheck` | Réponse d'un enfant, un jour d'étude, à « As-tu fini tes devoirs à l'étude ? » : `person`, `date`, `finished`. Unique `(person, date)`. |
| `household` | `ChoreCompletion` | « Fait » pour une tâche de ménage à une date. Unique `(chore, date)`. |
| `celebrations` | `Celebration` | Fête datée (`name`, `date`), `recurs_yearly` (chaque année), `previous` (occurrence de l'année d'avant, OneToOne). |
| `celebrations` | `CelebrationTodo` | Préparatif unique : `title`, `assignee` (facultatif), `done`. |
| `celebrations` | `GiftItem` | Cadeau : `item`, `recipient` / `recipient_name`, `buyer` / `buyer_name` (personne de la famille ou nom libre), `done` (acheté). |
| `celebrations` | `RecipeIdea` | Idée de recette : `name`, `notes` libres. |
| `stars` | `DayStar` | Étoile d'une **journée complète** d'un enfant : `person`, `date`, `celebrated` (« Journée terminée ! » déjà montrée). Unique `(person, date)`. Jamais supprimée par un décochage. |
| `stars` | `StarOpeningBalance` | **Solde de départ** d'un enfant : `amount` (> 0), `reason`. Au plus un par enfant (OneToOne). Étoiles gagnées ailleurs avant La Ruche (reprise de notre-semaine). |
| `stars` | `StarSpend` / `StarDebit` | Dépense d'étoiles de la famille et part de chaque enfant. |
| `saturday` | `SaturdayActivity` | Activité du catalogue : `name`, `season` (toutes / 4 saisons), `place` (sortie / maison), `is_free`, `price` indicatif, `star_cost` (0 = pas d'étoiles), `last_done_on`. Catalogue de départ (18 activités) à la création d'une famille. |
| `saturday` | `SaturdayPlan` | Un samedi d'une famille (unique `(family, date)`) : `status` (tirage en cours / prévu / fait), activité proposée puis validée, `activity_name` (copie pour l'historique), `spins` (≤ 3), `star_spend`. |
| `meals` | `Recipe` | Recette de la famille : `name`, `prep_minutes` (facultatif), `is_favorite`. Tri : favoris d'abord, puis par nom. |
| `meals` | `RecipeIngredient` | Ingrédient : `name`, `quantity` (décimal > 0, **vide = à convenance**), `unit` (liste fermée, voir « Unités »). |
| `meals` | `RecipeStep` | Étape numérotée : `position` (1, 2, 3…), `text`. Unique `(recipe, position)`. |
| `meals` | `MealSlot` | Un repas du menu : `date`, `meal` (déjeuner / dîner), `kind` (recette / restes / extérieur / autre), `recipe` (si et seulement si `kind = recette`, contrainte en base), `note` libre. Unique `(family, date, meal)`. Pas de ligne = rien de prévu. |
| `shopping` | `ShoppingItem` | Article de **la** liste de la famille : `name`, `quantity`, `unit`, `origin` (menu / ajouté à la main), `status` (à acheter / acheté / déjà à la maison), `recurring` (produit habituel, ajouts manuels seulement), `merge_key` et `recipes` (articles du menu). |
| `shopping` | `ShoppingTransfer` | Dernier transfert menu → courses d'une famille (OneToOne) : `week` (lundi), `transferred_at`. |
| `absences` | `Absence` | Période d'absence : `person` (vide = **toute la famille**), `kind` (vacances / malade / absent), `note`, `start_date` ≤ `end_date` (bornes incluses). |
| `agenda` | `Event` | Rendez-vous / activité à heure fixe : `title`, `people` (M2M, vide = toute la famille), `start_time` < `end_time`, `weekdays` + `start_date` / `end_date` (une seule fois = début = fin), `location`. |
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

## Saisie et tri des tâches (`tasks/forms.py`)

- **Plusieurs personnes d'un coup** : le formulaire de création propose toutes les
  personnes de la famille en puces ; une `Task` est créée **par personne** (le modèle reste
  une tâche = une personne : cochage, étoiles et colonnes n'en dépendent pas). La
  modification porte sur une seule tâche, qui garde sa personne.
- **Raccourcis de jours** (`ScheduleFieldsMixin`, réutilisable) : *Tous les jours*,
  *Jours d'école* (**lundi, mardi, jeudi, vendredi** : le mercredi est sans école, comme
  dans la semaine type), *Week-end*, *Personnalisé* (les puces des 7 jours n'apparaissent
  qu'alors, en CSS). Le raccourci n'est pas stocké : seul le masque l'est, et un masque
  connu est réaffiché sous son raccourci.
- **Dates précises** : *Toujours* ou *Sur une période* (du… au…, bornes incluses ; un seul
  jour = même date deux fois). Combinée aux jours : « du 12 au 16 octobre, jours d'école ».
  Contrainte en base `end_date ≥ start_date`. `Task.objects.scheduled_on(jour)` applique
  jours **et** période ; c'est le seul filtre utilisé pour « tâches du jour » et pour
  refuser le cochage d'une tâche hors période.
- **Tri** (parents seulement, Réglages → Tâches) : flèches ↑ / ↓ par tâche, à l'intérieur
  d'une même personne et d'une même période. Le déplacement renumérote tout le groupe
  (0, 1, 2…) puis échange deux voisins : pas de trou ni de doublon de `position`. Cet ordre
  est celui de l'accueil parent et de l'écran partagé. Des boutons plutôt qu'un
  glisser-déposer : accessibles au clavier et au lecteur d'écran, sans bibliothèque JS.

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

## Devoirs les jours d'étude

- Une tâche enfant est « devoirs » si son intitulé contient « devoir » (accents et casse
  ignorés, `Task.is_homework`) : aucun réglage en plus, la case « Étude le soir » de
  l'école suffit.
- Jour d'étude de l'enfant (étude cochée **et** école ce jour-là, pas absent) : sur sa
  colonne de l'écran partagé, les devoirs passent **en tête** de la liste et, tant qu'ils
  ne sont pas cochés, la question « As-tu fini tes devoirs à l'étude ? » est posée **avant
  la routine** (période où se trouvent les devoirs, en pratique le soir).
  « Oui » coche ses devoirs du jour (et donne l'étoile si la journée est complète) ;
  « Pas encore » ne change rien. Une seule réponse par jour (`HomeworkCheck`), la question
  ne revient pas.

## Ménage et semainier (`household/`)

- **Récurrence simple** : « tous les jours », « chaque semaine » (jours choisis) ou
  « une semaine sur deux » (jours choisis, compté à partir de la semaine de création).
  Stockée comme les tâches enfants (masque de jours) + `interval_weeks`.
- **Alternance hebdomadaire entre deux personnes** (facultative, `alternate`) : pour les
  rôles que les enfants s'échangent chaque semaine (lave-vaisselle / table). `assignee` a
  la tâche la semaine de `start_date` (semaine de création), `alternate` la suivante, et
  ainsi de suite ; le changement se fait le **lundi**, pour toute la semaine.
  `HouseholdChore.person_on(jour)` donne la personne chargée ; toutes les lectures
  (semainier, écran partagé, étoile du jour, absences, cochage) passent par elle, jamais
  par `assignee` directement (`ChoreOccurrence.person`).
  - Pas de rotation à plus de deux personnes, ni d'alternance « une semaine sur deux ».
  - **Échange par un parent** (Réglages → Ménage, « Échanger les rôles ») : inverse
    l'alternance **à partir de la semaine en cours**, pour toutes les tâches de la même
    paire d'un coup. Stocké comme un `ChoreSwap` par tâche et par semaine : la personne
    d'une semaine dépend de la parité des semaines écoulées **et** du nombre d'échanges
    antérieurs ou égaux. Les semaines passées ne changent donc jamais (les cochages
    restent attribués à la bonne personne) ; refaire l'échange la même semaine l'annule.
  - Absence : la tâche de la semaine est suspendue pour la personne chargée, **pas**
    reportée sur l'autre (même règle que sans alternance).
  - Les cochages (`ChoreCompletion`) ne stockent pas la personne : un échange en milieu de
    semaine réattribue les jours déjà cochés de cette semaine à l'autre enfant. Les étoiles
    déjà gagnées (`DayStar`) restent acquises.
- **Assignation à toute personne**, parents compris (contrairement aux tâches enfants).
- **Cochage** : un parent coche tout depuis le semainier. Une tâche de ménage **assignée
  à un enfant** apparaît aussi sur sa colonne de l'écran partagé (« Ménage du jour ») et
  s'y coche exactement comme ses tâches du jour (même règle de colonne, compte dans
  « X tâches restantes »). Une tâche de ménage **assignée à un parent** n'apparaît jamais
  sur l'écran partagé et n'y est pas cochable.
- **Semainier** (`/semaine/`) : **grille horaire** des 7 jours (voir « Rendez-vous et
  grille horaire »), puis le détail du jour choisi (`?jour=AAAA-MM-JJ`) avec fêtes,
  absences, école, ménage (cochable par un parent) et dîner. Navigation de semaine en
  semaine (`?semaine=AAAA-MM-JJ`). Même assemblage (`household/week.py`) pour la version
  tablette en lecture seule (`/affichage/semaine/`, même grille en grand).

## Fêtes (`celebrations/`)

- **Onglet dédié « Fêtes »** dans la nav parent, à la place de « Courses » (qui n'était
  qu'une page « à venir ») : la barre reste à 5 entrées lisibles sur téléphone. La liste
  de courses est arrivée en Phase 4 dans l'onglet « Cuisine » (voir design-system).
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

- **Gain (Phase 5) : +1 étoile par journée complète**, pas par tâche. La routine reste
  détaillée (beaucoup de micro-tâches) : une étoile par tâche aurait rendu les étoiles
  quasi gratuites. Voir « Étoile du jour » ci-dessous.
- **Dépense** : un registre (`StarSpend` + une ligne `StarDebit` par enfant). Solde d'un
  enfant = gagnées − dépensées. Les étoiles gagnées ne reculent jamais (un décochage ne
  retire rien), donc un solde ne devient pas négatif par décochage ; le pot ne compte de
  toute façon que les soldes positifs.
- **Palier** : tous les 10 étoiles **gagnées** (`STAR_TIER`). Le palier mesure l'effort
  cumulé et ne recule jamais quand on dépense : dépenser pour la famille ne fait pas
  « perdre » un palier (aucune mécanique culpabilisante).
- **Célébration de palier** (`TierCelebration`, une ligne par enfant : dernier palier
  fêté). Quand l'écran partagé affiche une colonne (chargement ou réponse au cochage) et
  que le palier atteint dépasse le dernier fêté, `claim_tier_celebration` avance le
  compteur par un UPDATE conditionnel atomique : seule la requête qui l'avance montre la
  célébration. D'où : une seule fois par palier, pas de doublon au re-render ni entre deux
  écrans, pas de nouvelle fête après un décochage/recochage, une seule célébration (la
  plus haute) si plusieurs paliers sont franchis d'un coup. Un palier atteint ailleurs
  (parent qui coche sur son téléphone) est fêté au prochain affichage de l'écran partagé.

### Étoile du jour (`stars/services.py`, Phase 5)

**`stars.selectors.day_progress(person, day) -> (cochées, prévues)`** : la journée
**entière** de la personne, quelle que soit la période affichée :
- ses tâches du jour, **matin + midi + soir** (`tasks_for_day(family, day, people=[person])`,
  donc mêmes règles que l'affichage : jours de la semaine, période de dates `start_date` /
  `end_date`, absence de la personne ou de toute la famille) ;
- **plus** le ménage qui lui est assigné ce jour-là (`chores_by_day`, même filtre
  d'absence, récurrence une semaine sur deux comprise). Le ménage d'un frère ou d'une
  sœur ne compte pas.

**`stars.services.award_day_star(person, day) -> bool`**, appelée après **chaque cochage**
(`done=True`) d'une tâche ou d'un ménage, par les quatre points d'écriture :
`display:toggle`, `display:toggle_chore` (écran partagé), `tasks:toggle` (accueil parent)
et `household:toggle` (semainier). Elle crée `DayStar(person, day)` si et seulement si :
1. la personne est un **enfant** (un parent ne gagne jamais d'étoile) ;
2. `day` n'est **pas dans le futur** (le semainier permet de cocher un ménage à venir :
   une journée n'est pas « terminée » avant d'avoir eu lieu) ;
3. `prévues > 0` (absent, malade ou rien de prévu : pas d'étoile, et rien de perdu) ;
4. `cochées == prévues`.

Elle renvoie `True` **seulement pour l'appel qui crée l'étoile**. Garanties :
- **Une étoile par jour et par enfant, jamais plus** : `get_or_create` sur une contrainte
  unique `(person, date)` ; deux cochages simultanés (deux écrans) n'en créent qu'une.
- **Idempotente** : tout cocher, décocher puis recocher une tâche ne redonne rien.
- **Jamais retirée** : décocher après coup ne touche pas `DayStar` (même esprit que « la
  dépense ne fait pas reculer le palier »). Modifier ou supprimer une tâche non plus.
- Décocher ne fait qu'arrêter le calcul : aucune étoile n'est attribuée au décochage.
- Pas de recalcul rétroactif : une journée devenue complète autrement que par un cochage
  (tâche supprimée le soir même) ne donne son étoile qu'au prochain cochage de ce jour.

**Étoiles gagnées** = nombre de `DayStar` de l'enfant **+ son solde de départ**
(`StarOpeningBalance`, s'il existe), calculé par `balances` en requêtes groupées.
Le palier (`STAR_TIER = 10`), la pastille, la page du samedi et le pot en découlent sans
autre changement : 10 journées complètes = un palier.

**Célébration « Journée terminée ! »** : `claim_day_celebration(person, today)` passe
`celebrated` à vrai par un UPDATE conditionnel atomique, appelé par l'écran partagé à
l'affichage de chaque colonne (chargement ou réponse au cochage). Seul l'appel qui le fait
avancer montre l'encart : une seule fois par journée, même entre deux écrans ou après un
recochage. Un jour complété depuis le téléphone d'un parent est fêté au prochain affichage
de l'écran partagé ; le parent voit, lui, la même célébration plein écran dans la réponse
de son cochage, puis la ligne « Journée terminée pour Lina : +1 étoile », sans consommer la
fête des enfants. Si l'étoile du jour fait aussi franchir un palier, une seule célébration
(plein écran, avec « Palier N atteint ! »).

**Solde de départ** (`services.grant_opening_balance(person, amount, reason)`) : reprend
tel quel un total d'étoiles gagné dans une autre application (pas recalculé, pas
approximé). Compte comme des étoiles gagnées : solde, pot, roue et palier. Refusé (rien
n'écrit) pour un parent, un montant ≤ 0 ou un enfant qui en a déjà un (contrainte
OneToOne en base, en plus du contrôle). Le palier atteint par ce seul solde est marqué
comme déjà fêté (`TierCelebration`) : l'écran partagé ne fête que les paliers franchis
ensuite dans La Ruche. Pas d'interface : saisi par le script de reprise (ou l'admin).

**Reprise des données (migration `stars.0003`)** : aucune étoile n'est recalculée à partir
des anciennes validations (l'ancienne règle comptait une étoile par tâche). Les soldes
repartent de zéro sur les données de test existantes.

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
- **Deux points d'entrée, un seul flux** : le téléphone du parent (`/samedi/`) et
  l'écran partagé (`/affichage/samedi/`, onglet « Samedi »). Sur l'écran partagé, un parent
  confirme avec son mot de passe (même mécanisme et même rate-limit que la sortie du mode
  tablette, `display/parent_check.py`) ; la session de l'écran reçoit pour **10 minutes**
  le droit de lancer la roue au nom de ce parent (`display/wheel_unlock.py`), sans autre
  privilège parent et sans connecter le parent. Le droit est consommé par « On y va ! ».
  Tirage, 3 tours et validation passent par les mêmes fonctions (`draw_context`,
  `perform_spin`, `accept`). Un parent connecté en aperçu n'a pas à confirmer.
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

## Menu, recettes et courses (`meals/`, `shopping/`) — Phase 4

Deux apps : `meals` (recettes, menu) et `shopping` (liste de courses, transfert). La liste
dépend du menu, jamais l'inverse. Toutes deux portent `family` directement.

### Recettes

- **Étapes = liste ordonnée** (`RecipeStep`, une ligne par étape), pas un bloc de texte.
  Saisie mobile dans un seul champ « une étape par ligne » (plus simple au doigt qu'un
  formulaire à lignes multiples sans JS) ; la numérotation tapée à la main (« 1. », « - »)
  est retirée et les étapes sont renumérotées à l'enregistrement (`Recipe.replace_steps`).
- **Ingrédients quantifiés** (`quantity` + `unit`) : c'est ce qui permet l'addition aux
  courses. Ajout / suppression un par un sur la fiche (même pattern que les sous-éléments
  des fêtes). Quantité vide = « à convenance » (sel, poivre).
- **Pas de nombre de portions ni de mise à l'échelle** : une recette de famille est écrite
  pour la famille. À ajouter si le besoin apparaît (multiplier les quantités au transfert).
- **Supprimer une recette la retire du menu** (`MealSlot.recipe` en CASCADE), après une page
  de confirmation qui liste les repas concernés. Les articles déjà sur la liste restent.
- Distinct de `celebrations.RecipeIdea` (idée libre pour une fête, sans ingrédients) : les
  deux coexistent, sans lien.

### Unités (`meals/units.py`)

Liste fermée : pièce(s), g, kg, ml, cl, l, c. à soupe, c. à café, paquet(s), boîte(s).

- **Conversion simple à l'intérieur d'une grandeur** : masse (g ↔ kg) et volume
  (ml ↔ cl ↔ l). Rien d'autre ne se convertit (une cuillère de farine n'a pas de poids
  fiable, une « pièce » d'oignon non plus).
- **Unités non convertibles pour un même ingrédient → lignes séparées**, pour ne jamais
  inventer une équivalence : « Farine · 200 g » et « Farine · 2 c. à soupe ».
- **Unité du résultat** : si toutes les lignes ont la même unité, on la garde
  (20 cl + 25 cl = 45 cl ; 1 kg + 1 kg = 2 kg). Sinon : kg / l dès 1000 g / 1000 ml,
  cl pour un volume rond, sinon g / ml (250 g + 1 kg = 1,25 kg ; 25 cl + 0,5 l = 75 cl).
- **Même ingrédient** = même nom **normalisé** (`normalize_name`) : casse, accents,
  espaces et « œ » ignorés (« Crème fraîche » = « creme fraiche »). **Pas de gestion des
  pluriels** (« tomate » ≠ « tomates ») : trop de mots invariables (ananas, pois, radis)
  pour une règle simple ; mieux vaut saisir le même mot dans les recettes.
- Ingrédients sans quantité du même nom → une seule ligne sans quantité.

### Menu de la semaine

- Deux créneaux par jour, **déjeuner et dîner**. Chacun : une recette de la famille, ou un
  repas libre (**restes**, **extérieur**, **autre** + texte obligatoire), avec une précision
  facultative (« Restes · du couscous »). Choisir « Rien de prévu » supprime la ligne.
- Vue semaine avec navigation `?semaine=AAAA-MM-JJ`, **même pattern que le semainier**
  (`household.views.requested_monday`, gabarit `parent/_week_nav.html`). Assemblage partagé
  parent / écran partagé : `meals/week.py` (`build_menu_week`).
- **Accueil parent : carte « Ce soir au menu »** (`dinner_of`), avec lien vers la recette et
  sa durée ; sans dîner prévu, lien direct vers le créneau du soir.
- Écran partagé : onglet **Menu** en lecture seule (`/affichage/menu/`), une colonne par jour.

### Liste de courses et transfert menu → courses (`shopping/transfer.py`)

- **Une seule liste par famille** (pas d'historique de listes) : c'est l'usage réel au
  magasin. Deux origines, affichées dans **deux sections distinctes** avec leur libellé :
  « Du menu de la semaine » (avec les recettes concernées) et « Habituels et ajouts ».
- **Produits habituels** = ajout manuel coché « Produit habituel » (`recurring`). « Retirer
  les articles achetés » supprime les achats, sauf les habituels qui **repassent « à
  acheter »** : la liste par défaut se reconstitue d'elle-même chaque semaine.
- **« Déjà à la maison »** (articles du menu) : l'article quitte la liste active pour une
  section repliée, **sans être supprimé** ni toucher au menu. Le transfert suivant le
  retrouve et le laisse de côté. « Remettre à acheter » le fait revenir.
- **Transfert = aperçu puis confirmation**, jamais d'écriture directe
  (`/courses/envoyer-le-menu/?semaine=…`) : `week_needs` additionne les ingrédients des
  recettes de la semaine (une recette prévue deux fois compte deux fois), `build_plan`
  compare aux articles « menu » existants (retrouvés par `merge_key` = nom normalisé +
  grandeur) et range chaque ligne :
  | Situation | Effet à la confirmation |
  |---|---|
  | Nouvel ingrédient | ajouté « à acheter » |
  | Article **à acheter**, quantité changée | quantité mise à jour (listé dans l'aperçu) |
  | Article **acheté ou « à la maison »**, même quantité | inchangé, reste coché (dit dans l'aperçu) |
  | Article **acheté ou « à la maison »**, **quantité changée** | **conflit : choix obligatoire** |
  | Article à acheter / à la maison qui n'est plus au menu | retiré de la liste (listé) |
  | Article acheté qui n'est plus au menu | gardé coché (vous l'avez acheté) |
  | Produit ajouté à la main | **jamais touché**, même s'il porte le même nom |
- **Retransfert sur un article déjà coché — comportement explicite** : pour chaque conflit,
  l'aperçu affiche « Acheté : 7 · au menu maintenant : 10 » et deux boutons sans valeur par
  défaut, **« Garder coché »** (la quantité suit le menu, l'article reste acheté) ou
  **« Remettre à acheter »**. Sans réponse, rien n'est écrit et la question est reposée
  (400). On ne demande rien pour un article coché dont la quantité n'a pas changé : le
  redemander à chaque envoi serait du bruit, et l'aperçu dit qu'il reste coché.
  « À la maison » suit la même règle que « acheté » (même risque : 2 boîtes à la maison,
  3 au menu).
- `apply_transfer` recalcule le plan **sous verrou de la famille** : si le menu ou la liste
  a changé entre l'aperçu et la confirmation et qu'un nouveau conflit apparaît, il est
  refusé (`MissingDecision`) et reposé, jamais tranché en silence.
- L'écran Courses signale « **Le menu a changé** » quand le menu de la semaine du dernier
  envoi (si elle n'est pas passée) donnerait un plan avec des changements.
- Un article du menu modifié à la main (quantité) garde sa `merge_key` : le transfert
  suivant proposera la quantité du menu (visible dans l'aperçu). Un article du menu
  supprimé revient au transfert suivant s'il est toujours au menu (« À la maison » est
  fait pour le mettre de côté).
- Le cochage d'un article est optimiste (HTMX, 204), comme les préparatifs de fêtes.

## Vacances et absences (`absences/`)

« Changer une journée » (vacances, enfant malade) = une **absence datée**, pas une
modification des tâches : les tâches restent telles quelles et reprennent seules à la fin.

- **Qui** : toute la famille (`person` vide, typiquement les vacances) ou une ou plusieurs
  personnes (une ligne par personne). Motif : Vacances, Malade, Absent, + précision libre.
- **Effets ces jours-là, pour la personne** (ou tout le monde) :
  - tâches du quotidien **suspendues** : absentes de l'accueil, de l'écran partagé et des
    compteurs, et **non cochables** (404 sur `tasks:toggle` / `display:toggle`) ;
  - ménage qui lui est assigné suspendu (semainier, colonne de l'enfant, cochage refusé) ;
  - école : l'absence remplace la journée (`SchoolDay.absence`, badge « Malade · gastro ») ;
    pas de rappel « sandwich » ni « pas d'école » pour demain ;
  - colonne de l'écran partagé : « Malade : pas de tâches aujourd'hui », sans alerte ni
    couleur d'erreur (règle « jamais culpabilisant »).
- **Étoiles : rien n'est perdu.** Les validations passées restent ; une tâche suspendue
  n'est simplement pas due. Pas de rattrapage automatique.
- Résolution en une requête sur une période (`absences_range`), une absence personnelle
  primant sur celle de la famille pour l'affichage du motif.
- Accès : Réglages → Vacances et absences, et carte « Absences aujourd'hui » de l'accueil
  (lien « Vacances, malade ? Changer une journée »).
- Pas de calendrier des vacances scolaires importé : les dates se saisissent (une fois par
  période de vacances).

## Rendez-vous et grille horaire (`agenda/`)

- **Nouveau type, à côté des tâches** : un rendez-vous (dentiste, foot, piano, marché) a
  une **heure de début et de fin** ; les tâches du quotidien et le ménage restent sans heure
  (période matin/midi/soir pour les tâches) et ne sont pas placés dans la grille.
- **Qui** : toute la famille (`people` vide) ou une ou plusieurs personnes (un seul
  rendez-vous partagé, pas une copie par personne).
- **Répétition** : *une seule fois* (une date) ou *chaque semaine* avec les mêmes
  raccourcis de jours et la même période facultative que les tâches (`ScheduleFieldsMixin`).
  Supprimer un rendez-vous répété supprime **toute la série** (pas d'exception par
  occurrence : à ajouter si le besoin apparaît). Une absence ne masque pas un rendez-vous
  (le médecin quand on est malade reste affiché).
- **Grille** (`agenda/grid.py`) : 7 h → 22 h par demi-heures (30 lignes). Le serveur calcule
  ligne, hauteur et voie de chaque bloc ; le gabarit n'a que des classes Tailwind
  (`row-start-N`, `row-span-N`, `col-start-N`, safelist dans `tailwind.config.js`), aucun
  style inline. Les rendez-vous qui se chevauchent sont **côte à côte** (3 voies au plus).
  Un rendez-vous qui déborde de 7 h–22 h est collé au bord, avec son heure réelle.
- **Les 7 jours toujours visibles, sans défilement horizontal**, à toutes les largeurs :
  sur téléphone les colonnes sont étroites (titre tronqué, icônes seules dans la ligne
  « journée »), les libellés apparaissent à partir de `md` ; le détail complet est dans le
  panneau du jour choisi.
- Ligne **« Jour »** au-dessus des heures : fêtes, absences, ménage (nombre ; noms sur
  l'écran partagé), dîner du menu.

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
| Connexion | 20 échecs / 15 min par IP ; 10 échecs / 15 min par compte visé (identifiant et e-mail du même compte comptent ensemble) |
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

**Identifiant court (`login_name`), en plus de l'e-mail.** Usage familial : on se connecte
avec « khadija » ou « enfants » plutôt qu'une adresse. Champ facultatif, unique sur toute
l'application, 2 à 30 signes `[a-z0-9._-]`, stocké en minuscules. Le formulaire de
connexion accepte l'un ou l'autre (`accounts.forms.resolve_login` : un « @ » = e-mail,
sinon identifiant traduit en `username`) ; un identifiant inconnu donne le même message
qu'un mauvais mot de passe. Même résolution pour la cible du rate-limit, afin qu'on ne
double pas les essais en alternant identifiant et e-mail. Un parent donne ou retire les
identifiants des comptes de sa famille (Réglages → Comptes et identifiants).

**Compte « écran partagé » (`Role.DISPLAY`).** Équivalent, avec identifiant + mot de
passe, d'un appareil partagé : utile sur un ordinateur de la maison où l'on préfère se
connecter plutôt que d'activer le mode tablette. Créé par un parent (Réglages → Affichage
partagé), un seul par famille, sans e-mail ni `Person` (donc sans colonne à lui). À la
connexion, l'accueil le renvoie sur `/affichage/` ; toutes les colonnes y sont cochables
(`tickable_person_id = None`), aucune vue parent (403). « Mode parent » demande le mot de
passe d'un parent de la famille, déconnecte le compte et connecte ce parent.

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
- Menu : portions et mise à l'échelle des quantités ; rayons du magasin pour trier la liste.
