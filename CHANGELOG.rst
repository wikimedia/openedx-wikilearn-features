Change Log
##########

..
   All enhancements and patches to openedx_wikilearn_features will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
**********

*

1.0.4 - 2026-08-20
**********************************************

Fixed
=====

* A failed Meta request no longer looks like a successful sync. ``sync_translations``
  reports failure explicitly instead of returning ``None``, failed message groups are
  counted, and ``sync_translated_strings_to_edx_from_meta`` refuses to record a fetch
  date when every request failed.
* A transport error on one request no longer aborts a whole sync run through
  ``asyncio.gather``, and throttling or read only responses are retried with a backoff.
* ``get_course_by_id`` results are cached per run in the fetch call, which ran two
  uncached modulestore reads per translation row, and a course that is missing or has
  no language is skipped with a warning instead of aborting the run.
* Per run counters are no longer class attributes, so results of one run in a process
  do not leak into the next.
* ``mclimit`` lowered to 500, the documented maximum. Meta warned and clamped 5000.

Changed
=======

* Meta client logging is quieter and more useful. Request and response bodies moved to
  debug level, log lines identify the message group and language they refer to, the
  final reports are one line summaries with a breakdown by outcome, and login and CSRF
  tokens are no longer written to the logs.

1.0.3 - 2026-08-20
**********************************************

Fixed
=====

* ``sync_untranslated_strings_to_meta_from_edx`` ignored its ``--base-course-key``
  option because it read ``base-course-key`` instead of argparse's
  ``base_course_key`` dest, so the per course send triggered on every translated
  rerun creation swept every dirty block on the instance instead.
* Empty message keys are no longer sent to Meta. A single empty value made Meta
  reject the whole message bundle, which left the block's ``content_updated`` and
  ``mapping_updated`` flags set and permanently excluded it from the fetch call.

Added
=====

* ``--base-course-key`` option on ``sync_translated_strings_to_edx_from_meta``, to
  fetch translations for the reruns of a single base course.

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
