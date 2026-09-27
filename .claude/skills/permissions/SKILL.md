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
| **Parent** (compte connecté) | Toutes les données de sa famille | Toutes les données de sa famille (semainier, menu, tâches, enfants, réglages) |
| **Enfant** | Ses données + le partagé de la famille en **lecture seule** (semainier, menu) | **Uniquement ses propres données** (cocher/décocher ses tâches) |
| **Affichage partagé** (appareil) | Profils enfants de la famille + semainier/menu en lecture | Actions « enfant » pour un enfant de la famille, rien d'autre |

Un enfant ne peut jamais : modifier le semainier ou le menu, créer/supprimer une tâche,
agir sur les données d'un frère ou d'une sœur hors affichage partagé, accéder aux réglages.

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
un compte enfant n'y a pas accès (403).

## 4. Implémentation attendue

- Vérification **côté serveur** à chaque requête, y compris les endpoints HTMX
  (un fragment HTMX est une vue comme une autre). Masquer un bouton ne protège rien.
- Écritures uniquement en POST (CSRF actif, jeton passé à HTMX par `hx-headers`).
- Centraliser les contrôles plutôt que de les réécrire dans chaque vue :
  - `apps.families.access.family_member_required` : compte connecté rattaché à une famille ;
    pose `request.family`, `request.membership`, `request.person` (403 sans famille) ;
  - `apps.families.access.parent_required` : idem + rôle parent (403 sinon) ;
  - `apps.display.access.shared_display_required` : appareil partagé valide ou parent ;
  - `apps.tasks.permissions.can_toggle` : parent → toute tâche de la famille, enfant →
    uniquement les siennes.
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
