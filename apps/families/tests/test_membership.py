from django.test import TestCase

from apps.families.models import (
    INVITE_CODE_ALPHABET,
    INVITE_CODE_LENGTH,
    AvatarColor,
    Family,
    FamilyMembership,
    Person,
    Role,
    normalize_invite_code,
)
from apps.families.services import (
    create_family,
    join_family,
    promote_to_parent,
    regenerate_invite_code,
)

from .factories import make_family, make_user


class CreateFamilyTests(TestCase):
    def test_creator_is_parent_with_generated_code(self):
        user = make_user(first_name="Sam")
        membership = create_family(user=user, name="Les Martin")
        family = membership.family
        self.assertEqual(membership.role, Role.PARENT)
        self.assertEqual(family.name, "Les Martin")
        self.assertEqual(len(family.invite_code), INVITE_CODE_LENGTH)
        self.assertTrue(set(family.invite_code) <= set(INVITE_CODE_ALPHABET))

    def test_each_family_gets_a_different_code(self):
        codes = {create_family(user=make_user(), name="X").family.invite_code for _ in range(5)}
        self.assertEqual(len(codes), 5)

    def test_person_created_with_account_and_role(self):
        user = make_user(first_name="Sam")
        create_family(user=user, name="Les Martin")
        person = Person.objects.get(user=user)
        self.assertEqual(person.name, "Sam")
        self.assertEqual(person.role, Role.PARENT)
        self.assertEqual(user.family, person.family)


class JoinFamilyTests(TestCase):
    def setUp(self):
        self.family = create_family(user=make_user(), name="Les Martin").family

    def test_following_members_join_as_children(self):
        code = self.family.invite_code
        m2 = join_family(user=make_user(), invite_code=code)
        m3 = join_family(user=make_user(), invite_code=code.lower())
        self.assertEqual((m2.role, m3.role), (Role.CHILD, Role.CHILD))
        self.assertEqual((m2.family, m3.family), (self.family, self.family))
        self.assertEqual(FamilyMembership.objects.filter(role=Role.PARENT).count(), 1)

    def test_unknown_code_joins_nothing(self):
        self.assertIsNone(join_family(user=make_user(), invite_code="INCONNU123"))
        self.assertIsNone(join_family(user=make_user(), invite_code=""))
        self.assertEqual(Family.objects.count(), 1)

    def test_first_member_of_an_empty_existing_family_is_parent(self):
        family = make_family(code="VIDE2026X")
        membership = join_family(user=make_user(), invite_code="VIDE2026X")
        self.assertEqual(membership.family, family)
        self.assertEqual(membership.role, Role.PARENT)

    def test_avatar_colors_cycle_through_tokens(self):
        join_family(user=make_user(), invite_code=self.family.invite_code)
        colors = list(self.family.people.values_list("avatar_color", flat=True))
        self.assertEqual(colors, [AvatarColor.TERRACOTTA, AvatarColor.HONEY])


class PromotionTests(TestCase):
    def test_promotion_updates_membership_and_person(self):
        family = create_family(user=make_user(), name="X").family
        child = make_user()
        membership = join_family(user=child, invite_code=family.invite_code)
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
