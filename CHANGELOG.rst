Change Log
##########

This file includes a history of past releases. Changes that were not yet added to a release are in the
`changelog.d/ <https://github.com/wikimedia/openedx-wikilearn-features/tree/master/changelog.d>`_ folder.

..
   ⚠️ DO NOT ADD YOUR CHANGES TO THIS FILE! (unless you want to modify existing changelog entries in this file)
   Changelog entries are managed by scriv. After you have made some changes, create a changelog entry with:

       make changelog-entry

   Edit and commit the newly-created file in changelog.d.

   If you need to create a new release, bump the version in openedx_wikilearn_features/__init__.py,
   then collect changelog entries in the same commit with:

       make changelog

   This project adheres to Semantic Versioning (https://semver.org/).

.. scriv-insert-here
* Fix meta translations log messages that dropped or printed the wrong value.

Fixed
===== 

* Count a course as completed when the learner passed it, not only when their
  letter grade is "Pass", so courses with custom grade cutoffs are counted.

1.0.1 – 2026-07-07
**********************************************

Fixed
=====

* Fix ``WebpackBundleLookupError: Cannot resolve bundle DiscoverCourses`` on the
  Discover Courses page by building the ``DiscoverCourses`` bundle from the
  plugin's own webpack config and loading it directly in the template, matching
  the Translations app. Ported the Discover Courses React app from the
  react-router v5 API (``Switch``/``useHistory``) to v6 (``Routes``/``useNavigate``).

0.1.0 – 2025-09-18
**********************************************

Added
=====

* First release on PyPI.
