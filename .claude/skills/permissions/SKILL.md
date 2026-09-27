---
name: permissions
description: Règles d'autorisation de La Ruche — rôles parent/enfant, isolation des données par famille, écriture limitée aux données propres de l'enfant, et mode « affichage partagé » sur tablette commune sans session par enfant. À lire avant d'écrire ou relire une vue, un queryset, un formulaire, un endpoint HTMX ou un test d'accès.
---

# Permissions — La Ruche

Ces règles sont **non négociables**. Une PR qui les enfreint ne doit pas être fusionnée
(case dédiée dans le template de PR). Les modèles cités (`Family`, `FamilyMembership`,
`Person`, `Task`, `SharedDisplayDevice`) sont décrits dans `domain-model/SKILL.md`.
Un « enfant » est une `Person` de rôle `child` ; un « compte enfant » est un `User` dont
l'appartenance (`FamilyMembership.role`) vaut `child`.

## 1. Isolation par famille — règle zéro

- **Chaque queryset** portant sur des données familiales est filtré par la famille de
  la requête. Jamais `Model.objects.get(pk=pk)` ni `Model.objects.all()` dans une vue.
- Passer par un point d'entrée unique (`Person.objects.for_family(family)`,
  `Task.objects.for_family(family)`, `SharedDisplayDevice.objects.for_family(family)`),
  puis `get_object_or_404(qs, pk=pk)` sur ce queryset déjà filtré.
- Un objet d'une autre famille renvoie **404**, pas 403 (ne pas révéler qu'il existe).
- La famille vient **du serveur** (session / appareil partagé), jamais d'un paramètre
  d'URL, d'un champ caché ou d'un en-tête envoyé par le client.
- Les formulaires qui proposent des objets liés (ForeignKey, choix) filtrent aussi leurs
  querysets par famille.
- Admin Django : réservé aux superutilisateurs de l'équipe, jamais exposé aux familles.

## 2. Rôles

| Rôle | Lecture | Écriture |
|---|---|---|
| **Parent** (compte connecté) | Toutes les données de sa famille | Toutes les données de sa famille (semainier, ménage, école, fêtes, menu, tâches, enfants, réglages) |
| **Enfant** (compte connecté) | **L'écran partagé** : toutes les colonnes de tous les enfants de la famille, + semainier/menu en **lecture seule** | **Uniquement sa propre colonne** (cocher/décocher ses tâches) |
| **Affichage partagé** (appareil) | Profils enfants de la famille + semainier/menu en lecture | Actions « enfant » pour un enfant de la famille, rien d'autre |

Un compte enfant ne peut jamais : modifier le semainier ou le menu, créer/supprimer une
tâche, cocher la colonne d'un frère ou d'une sœur, accéder aux réglages, à la gestion des
tâches ni à l'activation d'un appareil partagé.

### Domaines de la Phase 2 (école, ménage, fêtes)

| Donnée | Parent | Enfant (compte) / appareil partagé |
|---|---|---|
| École : semaine type, exceptions | Lecture + écriture (Réglages → Cantine, APC et étude) | Lecture : badges du jour et rappel du lendemain sur sa colonne |
| Ménage | Lecture + écriture (Réglages → Ménage), cochage de toute tâche sur le semainier | Lecture du semainier (`/affichage/semaine/`) ; **cochage des tâches de ménage assignées à un enfant, sur sa colonne** (même règle que ses tâches : un compte enfant ne coche que la sienne). Ménage d'un parent : jamais visible ni cochable sur l'écran partagé (404) |
| Fêtes : préparatifs, recettes | Lecture + écriture | Lecture seule (`/affichage/fetes/`, fêtes à venir) |
| Fêtes : **cadeaux** | Lecture + écriture | **Jamais affichés** sur l'écran partagé : les enfants y verraient leurs surprises |

Endpoint : `display:toggle_chore` (`/affichage/enfants/<enfant>/menage/<tâche>/fait/`) :
enfant de la famille, `can_tick` (403 sinon), tâche de ménage **assignée à cet enfant** et
prévue aujourd'hui (404 sinon).

Choix : les enfants voient les préparatifs et les idées de recettes (esprit familial :
tout le monde sait ce qui se prépare), mais pas la liste de cadeaux. Aucune écriture enfant
sur ces domaines ; toutes les pages et endpoints parent de ces domaines sont
`parent_required` (403 pour un compte enfant). Les listes de personnes proposées dans les
formulaires (assigné, pour qui, apporté par, enfant d'une exception) sont filtrées par
famille, et chaque modèle revérifie dans `clean()` que la personne est de la famille.

### Roue du samedi et étoiles (Phase 3)

| Donnée / action | Parent | Enfant (compte) / appareil partagé |
|---|---|---|
| Catalogue d'activités | Lecture + écriture (Réglages → Activités du samedi) | Aucun accès |
| Tirage, relances, « On y va ! », « C'est fait », annulation | Oui (`/samedi/…`) | **Non** : le parent lance, tout le monde regarde (403 compte enfant, connexion demandée pour l'appareil) |
| Plan validé du samedi | Accueil parent | Bandeau en lecture seule sur l'écran partagé |
| Étoiles | Soldes de chaque enfant et pot commun (page du samedi) | Son solde et son palier sur sa colonne (lecture) |

La dépense d'étoiles n'a lieu qu'à la validation par un parent, sous verrou de la famille ;
le serveur refuse une activité que le pot ne peut pas payer. La limite de 3 tirages par
samedi est comptée côté serveur et ne se contourne pas en changeant de filtres ; un
tirage en cours ne peut pas être annulé (seul un plan validé l'est, étoiles remboursées).

### Un seul chemin d'accès enfant : l'écran partagé

Usage réel : les enfants n'ont pas d'appareil individuel. Ils partagent **un même écran**
(tablette ou ordinateur), en même temps, chacun cochant ses tâches. Il n'existe donc
**pas de vue « mono-enfant »** : tout accès enfant affiche l'écran partagé, avec les
colonnes de **tous** les enfants de la famille.

| Accès | Ce qui s'affiche | Colonnes cochables |
|---|---|---|
| Appareil partagé (jeton) | Écran partagé (Aujourd'hui, Semaine, Fêtes) | Toutes (les enfants se partagent l'écran) |
| Compte enfant connecté | Le même écran partagé | **Uniquement la sienne** (les autres en lecture seule, refusées côté serveur en 403) |
| Parent connecté | Vue parent ; écran partagé en aperçu | Toutes |

Un compte enfant qui ouvre une page parent (`/`) est redirigé vers `/affichage/` ; les
autres pages parent (réglages, tâches, semaine, menu, courses) lui renvoient 403. Il n'y a
pas d'implémentation parallèle « compte enfant » : même vue, même gabarit, même endpoint
de cochage que l'appareil partagé ; seule la règle « quelles colonnes sont cochables »
dépend du visiteur (`request.tickable_person_id`).

## 3. Mode « affichage partagé » (tablette commune)

Les enfants partagent **le même écran physique**. Il n'y a **pas de session par enfant**
sur cet écran et pas de connexion enfant séparée : l'écran montre les profils de tous
les enfants simultanément (une colonne chacun).

Principe retenu :

1. Un **parent connecté** active le mode sur l'appareil (Réglages → Affichage partagé). Cela crée
   un **jeton d'appareil** lié à la famille, stocké côté serveur, révocable, avec date
   de dernière utilisation. La session parent est alors **fermée** sur cet appareil.
2. La session de l'appareil porte le rôle `shared_display` et la famille — **aucun**
   privilège parent.
3. Chaque action (ex. cocher une tâche) désigne l'enfant ciblé ; le serveur vérifie :
   l'enfant appartient à la famille de l'appareil **et** la tâche appartient à cet enfant.
   Une action d'une colonne ne peut pas modifier la tâche d'une autre colonne.
4. Actions autorisées : lecture des profils/semainier/menu, cocher/décocher une tâche
   d'un enfant. Tout le reste (création, suppression, réglages, données parent) est refusé.
5. **Sortie du mode** ou accès à la vue parent : ré-authentification d'un parent **de la
   famille de l'appareil** (e-mail + mot de passe, `/affichage/quitter/`), qui révoque
   l'appareil. (Un « code parent » plus court n'est pas implémenté.)
6. Les parents voient la liste de leurs appareils partagés et peuvent en révoquer un
   (tablette perdue, etc.).

Limite assumée : sur un écran commun, un enfant peut physiquement toucher la colonne
d'un autre. C'est un choix produit (confiance familiale, simplicité) ; le serveur garantit
seulement que tout reste dans la famille et au niveau de privilège « enfant ».

Implémentation : `apps/display/access.py` (cookie `laruche_display`, décorateur
`shared_display_required`). Un parent connecté peut aussi ouvrir l'écran en aperçu ;
un compte enfant y accède aussi, avec sa seule colonne cochable (voir §2).

## 4. Implémentation attendue

- Vérification **côté serveur** à chaque requête, y compris les endpoints HTMX
  (un fragment HTMX est une vue comme une autre). Masquer un bouton ne protège rien.
- Écritures uniquement en POST (CSRF actif, jeton passé à HTMX par `hx-headers`).
- Toute saisie de secret (mot de passe, code famille) passe par un garde de
  `apps/core/ratelimit.py` (connexion, rejoindre une famille, sortie du mode tablette) ;
  une nouvelle entrée de ce type doit en ajouter un, avec son test.
- Centraliser les contrôles plutôt que de les réécrire dans chaque vue :
  - `apps.families.access.family_member_required` : compte connecté rattaché à une famille ;
    pose `request.family`, `request.membership`, `request.person` (403 sans famille) ;
  - `apps.families.access.parent_required` : idem + rôle parent (403 sinon) ;
  - `apps.display.access.shared_display_required` : appareil partagé valide, parent ou
    compte enfant ; pose `request.tickable_person_id` (None = toutes les colonnes) ;
  - points d'entrée par famille des nouveaux domaines : `SchoolDaySchedule.objects.for_family`,
    `SchoolDayOverride.objects.for_family`, `HouseholdChore.objects.for_family`,
    `Celebration.objects.for_family`, et `CelebrationTodo / GiftItem / RecipeIdea
    .objects.for_family` (filtrés via la fête), `SaturdayActivity.objects.for_family`,
    `SaturdayPlan.objects.for_family` ; les étoiles sont toujours calculées pour les
    enfants de la famille de la requête (`stars.selectors.balances(family)`) ;
  - `apps.display.access.can_tick(request, person)` : la colonne de cette personne
    est-elle cochable par ce visiteur (vérifié dans `display:toggle`, 403 sinon).
- Les vues parent (`/`, réglages, tâches, pages « à venir », `tasks:toggle`) sont
  réservées aux parents.
- **Tests obligatoires** pour toute vue touchant des données familiales :
  - accès d'une autre famille → 404 ;
  - enfant/affichage partagé tentant une écriture interdite → 403 ou 404 ;
  - action ciblant un enfant d'une autre famille → 404 ;
  - utilisateur anonyme → redirection vers la connexion.

## Checklist de relecture

- [ ] Tous les querysets de la vue/du formulaire sont filtrés par famille.
- [ ] La famille provient du serveur, pas de la requête.
- [ ] Le rôle est vérifié côté serveur, y compris pour le fragment HTMX.
- [ ] L'écriture d'un enfant ne porte que sur ses propres données.
- [ ] Les tests d'accès inter-familles et de rôle existent.
