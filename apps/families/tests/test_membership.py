from django.test import TestCase

from apps.families.models import (
    INVITE_CODE_ALPHABET,
    AvatarColor,
    Family,
    FamilyMembership,
    Person,
    Role,
    normalize_invite_code,
)
from apps.families.services import (
    join_or_create_family,
    promote_to_parent,
    regenerate_invite_code,
)

from .factories import make_family, make_user


class JoinOrCreateFamilyTests(TestCase):
    def test_unknown_code_creates_family_and_first_member_is_parent(self):
        user = make_user(first_name="Sam")
        membership = join_or_create_family(
            user=user, invite_code="RUCHE2026", family_name="Les Martin"
        )
        self.assertEqual(membership.role, Role.PARENT)
        self.assertEqual(membership.family.name, "Les Martin")
        self.assertEqual(membership.family.invite_code, "RUCHE2026")

    def test_following_members_join_as_children(self):
        first = make_user()
        join_or_create_family(user=first, invite_code="RUCHE2026", family_name="Les Martin")
        second, third = make_user(), make_user()
        m2 = join_or_create_family(user=second, invite_code="RUCHE2026")
        m3 = join_or_create_family(user=third, invite_code="RUCHE2026")
        self.assertEqual((m2.role, m3.role), (Role.CHILD, Role.CHILD))
        self.assertEqual(Family.objects.count(), 1)
        self.assertEqual(FamilyMembership.objects.filter(role=Role.PARENT).count(), 1)

    def test_first_member_of_an_empty_existing_family_is_parent(self):
        family = make_family(code="VIDE2026X")
        membership = join_or_create_family(user=make_user(), invite_code="VIDE2026X")
        self.assertEqual(membership.family, family)
        self.assertEqual(membership.role, Role.PARENT)

    def test_person_created_with_account_and_role(self):
        user = make_user(first_name="Sam")
        join_or_create_family(user=user, invite_code="RUCHE2026", family_name="Les Martin")
        person = Person.objects.get(user=user)
        self.assertEqual(person.name, "Sam")
        self.assertEqual(person.role, Role.PARENT)
        self.assertEqual(user.family, person.family)

    def test_avatar_colors_cycle_through_tokens(self):
        join_or_create_family(user=make_user(), invite_code="RUCHE2026", family_name="X")
        join_or_create_family(user=make_user(), invite_code="RUCHE2026")
        colors = list(Person.objects.values_list("avatar_color", flat=True))
        self.assertEqual(colors, [AvatarColor.TERRACOTTA, AvatarColor.HONEY])


class PromotionTests(TestCase):
    def test_promotion_updates_membership_and_person(self):
        join_or_create_family(user=make_user(), invite_code="RUCHE2026", family_name="X")
        child = make_user()
        membership = join_or_create_family(user=child, invite_code="RUCHE2026")
        promote_to_parent(membership)
        membership.refresh_from_db()
        self.assertEqual(membership.role, Role.PARENT)
        self.assertEqual(Person.objects.get(user=child).role, Role.PARENT)


class InviteCodeTests(TestCase):
    def test_normalization(self):
        self.assertEqual(normalize_invite_code(" ruche-2026 x "), "RUCHE2026X")

    def test_saved_code_is_normalized(self):
        family = make_family(code="ab cd-efgh")
        self.assertEqual(family.invite_code, "ABCDEFGH")

    def test_regenerate_replaces_code(self):
        family = make_family(code="ANCIENCODE")
        regenerate_invite_code(family)
        family.refresh_from_db()
        self.assertNotEqual(family.invite_code, "ANCIENCODE")
        self.assertEqual(len(family.invite_code), 10)
        self.assertTrue(set(family.invite_code) <= set(INVITE_CODE_ALPHABET))


class UserFamilyPropertyTests(TestCase):
    def test_user_without_membership_has_no_family(self):
        self.assertIsNone(make_user().family)
