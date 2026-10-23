"""
Tests for `wikimedia_general.utils`.
"""
from unittest.mock import MagicMock, patch

from common.djangoapps.student.tests.factories import (
    CourseAccessRoleFactory,
    CourseEnrollmentFactory,
    UserFactory,
)
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory

from openedx_wikilearn_features.wikimedia_general.utils import (
    get_course_members,
    get_mentioned_users_list,
    is_course_completed,
    is_course_member,
)

UTILS = "openedx_wikilearn_features.wikimedia_general.utils"
COURSE_ID = "course-v1:A+B+C"


class CourseMembersTest(TestCase):
    def setUp(self):
        self.course = CourseOverviewFactory.create(id=CourseKey.from_string(COURSE_ID))
        other_course = CourseOverviewFactory.create(id=CourseKey.from_string("course-v1:X+Y+Z"))

        self.learner = UserFactory(username="Jane Doe")
        CourseEnrollmentFactory(user=self.learner, course=self.course, is_active=True)

        self.staff = UserFactory()
        CourseAccessRoleFactory(user=self.staff, course_id=self.course.id, role="staff")

        self.instructor = UserFactory()
        CourseAccessRoleFactory(user=self.instructor, course_id=self.course.id, role="instructor")

        self.unenrolled = UserFactory()
        CourseEnrollmentFactory(user=self.unenrolled, course=self.course, is_active=False)

        self.inactive_user = UserFactory(is_active=False)
        CourseEnrollmentFactory(user=self.inactive_user, course=self.course, is_active=True)

        self.other_course_learner = UserFactory()
        CourseEnrollmentFactory(user=self.other_course_learner, course=other_course, is_active=True)

        self.beta_tester = UserFactory()
        CourseAccessRoleFactory(user=self.beta_tester, course_id=self.course.id, role="beta_testers")

    def test_get_course_members(self):
        self.assertCountEqual(
            get_course_members(self.course.id),
            [self.learner, self.staff, self.instructor],
        )

    def test_member_with_enrollment_and_role_is_returned_once(self):
        CourseEnrollmentFactory(user=self.staff, course=self.course, is_active=True)
        self.assertEqual(list(get_course_members(self.course.id)).count(self.staff), 1)

    def test_is_course_member(self):
        self.assertTrue(is_course_member(self.learner, self.course.id))
        self.assertTrue(is_course_member(self.staff, self.course.id))
        self.assertFalse(is_course_member(self.unenrolled, self.course.id))
        self.assertFalse(is_course_member(self.other_course_learner, self.course.id))
        self.assertFalse(is_course_member(self.beta_tester, self.course.id))

    def test_get_mentioned_users_list_only_returns_course_members(self):
        def mention(username):
            return f'<span class="wikilearn-mention" data-username="{username}">@{username}</span>'

        post_body = "<p>{} {} {} @{}</p>".format(
            mention("Jane Doe"),
            mention(self.other_course_learner.username),
            mention("nobody"),
            self.staff.username,  # plain text, not a mention
        )
        self.assertEqual(get_mentioned_users_list(post_body, self.course.id), [self.learner])

    def test_get_mentioned_users_list_without_mentions(self):
        self.assertEqual(get_mentioned_users_list("<p>no mentions</p>", self.course.id), [])


@patch(f"{UTILS}.CourseGradeFactory")
class IsCourseCompletedTest(TestCase):
    def _grade(self, mock_factory, passed, letter_grade):
        mock_factory.return_value.read.return_value = MagicMock(passed=passed, summary={"grade": letter_grade})

    def test_passed_with_custom_grade_cutoffs(self, mock_factory):
        self._grade(mock_factory, passed=True, letter_grade="A")
        self.assertTrue(is_course_completed(MagicMock(), COURSE_ID))

    def test_passed_with_default_grade_cutoffs(self, mock_factory):
        self._grade(mock_factory, passed=True, letter_grade="Pass")
        self.assertTrue(is_course_completed(MagicMock(), COURSE_ID))

    def test_not_passed(self, mock_factory):
        self._grade(mock_factory, passed=False, letter_grade=None)
        self.assertFalse(is_course_completed(MagicMock(), COURSE_ID))

    def test_passed_none_returns_false(self, mock_factory):
        self._grade(mock_factory, passed=None, letter_grade=None)
        self.assertIs(is_course_completed(MagicMock(), COURSE_ID), False)

    def test_grade_read_error(self, mock_factory):
        mock_factory.return_value.read.side_effect = Exception("boom")
        self.assertFalse(is_course_completed(MagicMock(), COURSE_ID))
