---
name: permissions
description: Règles d'autorisation de La Ruche — rôles parent/enfant, isolation des données par famille, écriture limitée aux données propres de l'enfant, et mode « affichage partagé » sur tablette commune sans session par enfant. À lire avant d'écrire ou relire une vue, un queryset, un formulaire, un endpoint HTMX ou un test d'accès.
---

# Permissions — La Ruche

Ces règles sont **non négociables**. Une PR qui les enfreint ne doit pas être fusionnée
(case dédiée dans le template de PR). Les noms de modèles ci-dessous (Family, Child…)
sont indicatifs : ils seront définis en Phase 1 dans `domain-model/SKILL.md`.

## 1. Isolation par famille — règle zéro

- **Chaque queryset** portant sur des données familiales est filtré par la famille de
  la requête. Jamais `Model.objects.get(pk=pk)` ni `Model.objects.all()` dans une vue.
- Passer par un point d'entrée unique (ex. manager `Model.objects.for_family(family)`),
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

1. Un **parent connecté** active le mode sur l'appareil (depuis ses réglages). Cela crée
   un **jeton d'appareil** lié à la famille, stocké côté serveur, révocable, avec date
   de dernière utilisation. La session parent est alors **fermée** sur cet appareil.
2. La session de l'appareil porte le rôle `shared_display` et la famille — **aucun**
   privilège parent.
3. Chaque action (ex. cocher une tâche) désigne l'enfant ciblé ; le serveur vérifie :
   l'enfant appartient à la famille de l'appareil **et** la tâche appartient à cet enfant.
   Une action d'une colonne ne peut pas modifier la tâche d'une autre colonne.
4. Actions autorisées : lecture des profils/semainier/menu, cocher/décocher une tâche
   d'un enfant. Tout le reste (création, suppression, réglages, données parent) est refusé.
5. **Sortie du mode** ou accès à la vue parent : ré-authentification parent (mot de passe
   ou code parent). Le code parent n'est jamais affiché ni stocké en clair.
6. Les parents voient la liste de leurs appareils partagés et peuvent en révoquer un
   (tablette perdue, etc.).

Limite assumée : sur un écran commun, un enfant peut physiquement toucher la colonne
d'un autre. C'est un choix produit (confiance familiale, simplicité) ; le serveur garantit
seulement que tout reste dans la famille et au niveau de privilège « enfant ».

## 4. Implémentation attendue

- Vérification **côté serveur** à chaque requête, y compris les endpoints HTMX
  (un fragment HTMX est une vue comme une autre). Masquer un bouton ne protège rien.
- Écritures uniquement en POST (CSRF actif, jeton passé à HTMX par `hx-headers`).
- Centraliser les contrôles (décorateurs/mixins du type `parent_required`,
  `shared_display_or_parent`) plutôt que de les réécrire dans chaque vue.
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
