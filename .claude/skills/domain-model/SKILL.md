---
name: domain-model
description: Modèle de domaine de La Ruche (familles, membres, tâches, semainier, menu…). Vide en Phase 0, rempli en Phase 1. À lire avant de créer ou modifier un modèle Django ou une migration.
---

# Modèle de domaine — La Ruche

_À remplir en Phase 1._

Aucun modèle métier n'existe en Phase 0. Seul `accounts.User` (vide, hérité de
`AbstractUser`) est en place, pour pouvoir y ajouter rôle et rattachement familial
sans migration depuis `auth.User`.

Contraintes déjà connues, à respecter lors de la conception :

- Toute donnée familiale est rattachée (directement ou indirectement) à une famille,
  et exposée via un manager filtrant par famille (voir `permissions/SKILL.md`).
- Les enfants n'ont pas de session individuelle sur l'écran partagé.
