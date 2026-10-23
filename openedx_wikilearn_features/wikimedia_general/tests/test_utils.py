"""
Tests for `wikimedia_general.utils`.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from openedx_wikilearn_features.wikimedia_general.utils import is_course_completed

UTILS = "openedx_wikilearn_features.wikimedia_general.utils"
COURSE_ID = "course-v1:A+B+C"


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
