## Quoi et pourquoi

<!-- Ce que change cette PR et la raison. Lien vers l'issue si applicable. -->

> Titre de la PR au format Conventional Commits (`feat(tasks): …`, `fix: …`) :
> il devient le message du commit squashé et détermine la version publiée.

## Checklist

- [ ] Les tests passent (`uv run python manage.py test`) et les nouveaux comportements sont testés
- [ ] Migrations propres : générées, commitées, `makemigrations --check` vert, pas de migration éditée après merge
- [ ] Aucun secret commité (clés, mots de passe, URL de base réelle, `.env`)
- [ ] Respecte [`permissions/SKILL.md`](../.claude/skills/permissions/SKILL.md) : querysets filtrés par famille, rôles vérifiés côté serveur (HTMX compris), tests d'accès inter-familles
- [ ] UI (si applicable) : respecte [`design-system/SKILL.md`](../.claude/skills/design-system/SKILL.md) (tokens, contrastes, bonne famille de gabarits, mouvement réduit)
- [ ] Pas de script ou style inline sans nonce, rien qui exige d'assouplir la CSP

## Captures (si UI)

<!-- Vue parent mobile et/ou affichage partagé tablette. -->
