"""
Report Mongo storage use for the modulestore and contentstore, and optionally
prune data that no live course references any more.
"""
from logging import getLogger

from django.core.management.base import BaseCommand, CommandError
from opaque_keys.edx.locator import CourseLocator
from xmodule.contentstore.django import contentstore
from xmodule.modulestore.django import modulestore

LOGGER = getLogger(__name__)

MB = 1000000


class Command(BaseCommand):
    """
    Show where Mongo storage is going and, on request, reclaim the orphaned part.

    Split modulestore is append-only and delete_course only removes the course
    index entry, so structures, definitions and GridFS assets survive every
    deleted course, every failed rerun and every clone. Nothing prunes them, so
    an instance grows until writes are refused.

    Reports by default and changes nothing. Pruning is opt-in and split in two,
    because the two halves carry different risk:

      --prune-assets      deletes GridFS assets belonging to courses that no
                          longer exist. Safe: nothing live can reference them.
      --prune-structures  deletes structures that are not the current draft or
                          published version of a live course, and the definitions
                          only those structures used. This discards version
                          history, so Studio can no longer show or revert to
                          earlier versions of surviving courses.

    Usage:
        python manage.py cms mongo_storage_report
        python manage.py cms mongo_storage_report --quota-mb 512
        python manage.py cms mongo_storage_report --prune-assets
        python manage.py cms mongo_storage_report --prune-assets --prune-structures
    """

    help = "Report Mongo storage use and optionally prune orphaned modulestore and asset data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quota-mb",
            type=int,
            default=None,
            help="Storage quota in MB, to report headroom against. Atlas M0 is 512.",
        )
        parser.add_argument(
            "--prune-assets",
            action="store_true",
            help="Delete GridFS assets belonging to courses that no longer exist.",
        )
        parser.add_argument(
            "--prune-structures",
            action="store_true",
            help="Delete unreferenced structures and definitions. Discards version history.",
        )

    def handle(self, *args, **options):
        store = modulestore().default_modulestore
        connection = store.db_connection
        database = connection.database

        self._report_storage(database, options["quota_mb"])
        live_courses = self._live_course_keys(connection)
        self.stdout.write(f"Live courses: {len(live_courses)}")

        orphan_assets = self._report_orphan_assets(live_courses)
        keep_structures, keep_definitions = self._report_orphan_structures(connection, live_courses)

        if options["prune_assets"]:
            self._prune_assets(orphan_assets)
        if options["prune_structures"]:
            self._prune_structures(connection, keep_structures, keep_definitions, live_courses)

        if not (options["prune_assets"] or options["prune_structures"]):
            self.stdout.write("Report only. Pass --prune-assets and/or --prune-structures to reclaim.")
        else:
            self._report_storage(database, options["quota_mb"], label="after prune")
            self.stdout.write(
                "Note: on shared Atlas tiers deletes may not shrink the reported disk "
                "figure, because compact is unavailable there."
            )

    def _report_storage(self, database, quota_mb, label="current"):
        """
        Print database and per-collection sizes.
        """
        stats = database.command("dbstats")
        data_mb = stats.get("dataSize", 0) / MB
        index_mb = stats.get("indexSize", 0) / MB
        total_mb = data_mb + index_mb

        self.stdout.write(f"=== Storage ({label}), db {database.name}")
        for name in sorted(database.list_collection_names()):
            collection_stats = database.command("collstats", name)
            self.stdout.write(
                f"  {name:34s} n={collection_stats.get('count', 0):8d} "
                f"data={collection_stats.get('size', 0) / MB:9.1f}MB "
                f"index={collection_stats.get('totalIndexSize', 0) / MB:7.1f}MB"
            )
        self.stdout.write(f"  total data={data_mb:.1f}MB index={index_mb:.1f}MB sum={total_mb:.1f}MB")
        if quota_mb:
            self.stdout.write(
                f"  quota={quota_mb}MB used={100 * total_mb / quota_mb:.1f}% "
                f"headroom={quota_mb - total_mb:.1f}MB"
            )

    def _live_course_keys(self, connection):
        """
        Return the course keys that still have an index entry, as (org, course, run) tuples.
        """
        return {
            (entry["org"], entry["course"], entry["run"])
            for entry in connection.course_index.find({}, {"org": 1, "course": 1, "run": 1})
        }

    def _asset_course_keys(self):
        """
        Return every (org, course, run) that owns GridFS assets.
        """
        fs_files = contentstore().fs_files
        found = set()
        for prefix in ("content_son", "_id"):
            for triple in fs_files.aggregate([
                {"$group": {"_id": {
                    "org": f"${prefix}.org",
                    "course": f"${prefix}.course",
                    "run": f"${prefix}.run",
                }}},
            ]):
                key = triple.get("_id") or {}
                org, course, run = key.get("org"), key.get("course"), key.get("run")
                if org and course and run:
                    found.add((org, course, run))
        return found

    def _report_orphan_assets(self, live_courses):
        """
        Report and return the asset-owning course keys with no live course.
        """
        orphans = sorted(self._asset_course_keys() - live_courses)
        self.stdout.write(f"Asset owners with no live course: {len(orphans)}")
        for org, course, run in orphans:
            self.stdout.write(f"  orphaned assets: {org}/{course}/{run}")
        return orphans

    def _report_orphan_structures(self, connection, live_courses):
        """
        Report orphaned structures and definitions, returning what must be kept.
        """
        keep_structures = set()
        for entry in connection.course_index.find({}, {"versions": 1}):
            keep_structures.update((entry.get("versions") or {}).values())

        keep_definitions = set()
        for structure in connection.structures.find(
            {"_id": {"$in": list(keep_structures)}}, {"blocks": 1}
        ):
            for block in structure.get("blocks", []):
                if block.get("definition"):
                    keep_definitions.add(block["definition"])

        total_structures = connection.structures.count_documents({})
        total_definitions = connection.definitions.count_documents({})
        self.stdout.write(
            f"Structures: {total_structures} total, {len(keep_structures)} referenced, "
            f"{total_structures - len(keep_structures)} orphaned"
        )
        self.stdout.write(
            f"Definitions: {total_definitions} total, {len(keep_definitions)} referenced, "
            f"{total_definitions - len(keep_definitions)} orphaned"
        )
        return keep_structures, keep_definitions

    def _prune_assets(self, orphans):
        """
        Delete GridFS assets for courses that no longer exist.
        """
        if not orphans:
            self.stdout.write("No orphaned assets to delete.")
            return

        store = contentstore()
        for org, course, run in orphans:
            course_key = CourseLocator(org=org, course=course, run=run)
            store.delete_all_course_assets(course_key)
            self.stdout.write(f"  deleted assets: {course_key}")
        self.stdout.write(f"Deleted assets for {len(orphans)} course(s).")

    def _prune_structures(self, connection, keep_structures, keep_definitions, live_courses):
        """
        Delete structures and definitions that no live course references.
        """
        if live_courses and not (keep_structures and keep_definitions):
            raise CommandError(
                "Refusing to prune: there are live courses but the reference walk found "
                "nothing to keep. The stored document shape is not what this command "
                "expects, and deleting now would destroy live course data."
            )

        structures = connection.structures.delete_many({"_id": {"$nin": list(keep_structures)}})
        definitions = connection.definitions.delete_many({"_id": {"$nin": list(keep_definitions)}})
        self.stdout.write(
            f"Deleted {structures.deleted_count} structure(s) and "
            f"{definitions.deleted_count} definition(s)."
        )
