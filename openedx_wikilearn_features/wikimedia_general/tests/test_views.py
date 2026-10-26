"""
Tests for `wikimedia_general.api.v0.views`.
"""
from common.djangoapps.student.tests.factories import (
    CourseAccessRoleFactory,
    CourseEnrollmentFactory,
    UserFactory,
)
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from rest_framework.test import APIClient

COURSE_ID = "course-v1:A+B+C"
URL = f"/wikimedia_general/api/v0/mention_users/{COURSE_ID}/"


class MentionUsersViewTest(TestCase):
    def setUp(self):
        self.course = CourseOverviewFactory.create(id=CourseKey.from_string(COURSE_ID))
        other_course = CourseOverviewFactory.create(id=CourseKey.from_string("course-v1:X+Y+Z"))

        self.requester = UserFactory(username="Jane Requester")
        CourseEnrollmentFactory(user=self.requester, course=self.course, is_active=True)

        self.learner = UserFactory(username="Jane Doe")
        CourseEnrollmentFactory(user=self.learner, course=self.course, is_active=True)

        self.staff = UserFactory(username="Jane Staff")
        CourseAccessRoleFactory(user=self.staff, course_id=self.course.id, role="staff")

        self.other_course_learner = UserFactory(username="Jane Elsewhere")
        CourseEnrollmentFactory(user=self.other_course_learner, course=other_course, is_active=True)

        self.client = APIClient()
        self.client.force_authenticate(user=self.requester)

    def _usernames(self, response):
        return [result["username"] for result in response.json()["results"]]

    def test_returns_matching_course_members_without_requester(self):
        response = self.client.get(URL, {"search": "jane"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._usernames(response), ["Jane Doe", "Jane Staff"])

    def test_filters_by_search(self):
        response = self.client.get(URL, {"search": "doe"})
        self.assertEqual(self._usernames(response), ["Jane Doe"])

    def test_empty_search_returns_no_results(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": []})

    def test_non_member_is_forbidden(self):
        self.client.force_authenticate(user=self.other_course_learner)
        response = self.client.get(URL, {"search": "jane"})
        self.assertEqual(response.status_code, 403)

    def test_course_team_member_can_search(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(URL, {"search": "jane"})
        self.assertEqual(self._usernames(response), ["Jane Doe", "Jane Requester"])

    def test_anonymous_user_is_rejected(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(URL, {"search": "jane"})
        self.assertIn(response.status_code, (401, 403))

    def test_unknown_course_returns_no_access(self):
        response = self.client.get("/wikimedia_general/api/v0/mention_users/course-v1:No+Such+Course/", {"search": "jane"})
        self.assertEqual(response.status_code, 403)
