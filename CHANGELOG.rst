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
