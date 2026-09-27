---
name: domain-model
description: Modèle de domaine de La Ruche (familles, membres, personnes, tâches du jour, appareils partagés) et choix techniques associés. À lire avant de créer ou modifier un modèle Django ou une migration.
---

# Modèle de domaine — La Ruche

État à la fin de la **Phase 1** (fondations métier). Les règles d'accès qui
s'appliquent à ces modèles sont dans `permissions/SKILL.md`.

## Vue d'ensemble

```
accounts.User ──1:1── families.FamilyMembership ──N:1── families.Family
      │                    (role: parent | child)            │
      └──0..1:1── families.Person ──N:1──────────────────────┘
                        │  (name, avatar_color, role affiché)
                        └──1:N── tasks.Task ──1:N── tasks.TaskCompletion (task, date)

display.SharedDisplayDevice ──N:1── families.Family   (jeton d'appareil, révocable)
```

| App | Modèle | Rôle |
|---|---|---|
| `accounts` | `User` | Compte. Connexion par e-mail (`username` = e-mail en minuscules). Propriété `user.family`. |
| `families` | `Family` | Foyer. `name`, `invite_code` unique (normalisé : majuscules, sans espaces ni tirets). |
| `families` | `FamilyMembership` | Rattache **un compte à une seule famille** (OneToOne) avec son `role` (`parent` / `child`). Pilote les permissions. |
| `families` | `Person` | Membre **tel qu'affiché** (colonne, avatar, tâches). Lié à un `User` s'il a un compte, sinon non (jeune enfant). `role` affiché, `avatar_color`. |
| `tasks` | `Task` | Tâche récurrente d'une personne : `title`, `period` (matin/midi/soir), `weekdays` (masque de bits), `position`. |
| `tasks` | `TaskCompletion` | « Fait » pour une tâche **à une date**. Absence de ligne = à faire. Unique `(task, date)`. `completed_by` vide si coché depuis l'affichage partagé. |
| `display` | `SharedDisplayDevice` | Tablette commune autorisée par un parent. Stocke l'empreinte SHA-256 du jeton, `last_used_at`, `revoked_at`. |

## Règles métier

- **Inscription avec code famille** (`families.services.join_or_create_family`) :
  - code connu → le compte rejoint la famille ;
  - code inconnu → la famille est créée, **à condition** qu'un nom de famille soit
    fourni (une faute de frappe dans un code existant ne crée donc pas une famille
    fantôme) et que le code fasse **au moins 8 caractères** (il suffit à rejoindre
    la famille : il ne doit pas être devinable).
- **Premier inscrit = parent**, les suivants entrent en `child`. La ligne `Family` est
  verrouillée (`select_for_update`) pendant l'inscription pour éviter deux « premiers ».
  Si une famille existe mais n'a plus aucun membre, le prochain inscrit redevient parent.
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

## Choix techniques documentés

**Authentification : vues maison sur `django.contrib.auth`, pas django-allauth.**
Besoin limité (e-mail + mot de passe + code famille) ; allauth ajouterait une dépendance,
ses gabarits et du JS à adapter à la CSP stricte, pour des fonctions dont on n'a pas
besoin aujourd'hui (connexion sociale, MFA). On garde `LoginView`/`LogoutView` de Django,
un `LoginForm` qui normalise l'e-mail et une vue d'inscription. À reconsidérer si l'on
veut la vérification d'e-mail, la réinitialisation de mot de passe ou la connexion Google.

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

## Évolutions prévues (hors Phase 1)

- Moteur de routines personnalisables (Phase 2) : remplacera ou enrichira `Task`.
- Semainier, menu, courses : pages « à venir » dans la nav parent.
- Paliers d'étoiles : s'appuieront sur l'historique `TaskCompletion`.
