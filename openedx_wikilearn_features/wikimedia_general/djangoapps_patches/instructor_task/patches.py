import logging
from lms.djangoapps.instructor_task.subtasks import SubtaskStatus

log = logging.getLogger(__name__)

class EnhancedSubtaskStatus(SubtaskStatus):
    """
    Extended SubtaskStatus that includes failure and skip details for more granular reporting.

    Extra SubtaskStatus values are:
    'failure_details' : list of tuples (email, name, reason) for each failed recipient
    'skip_details' : list of tuples (email, name, reason) for each skipped recipient
    """

    def __init__(
        self,
        task_id,
        attempted=None,
        succeeded=0,
        failed=0,
        skipped=0,
        retried_nomax=0,
        retried_withmax=0,
        state=None,
        failure_details=None,
        skip_details=None
    ):
        """
        Construct an EnhancedSubtaskStatus object.
        """
        super().__init__(
            task_id=task_id,
            attempted=attempted,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            retried_nomax=retried_nomax,
            retried_withmax=retried_withmax,
            state=state
        )
        self.failure_details = failure_details or []
        self.skip_details = skip_details or []

    def add_failure_detail(self, email, reason):
        """Add a single failure detail (email, reason)."""
        log.info("Adding failure detail: %s - %s", email, reason)
        self.failure_details.append((email, reason))

    def add_skip_detail(self, email, reason):
        """Add a single skip detail (email, reason)."""
        log.info("Adding skip detail: %s - %s", email, reason)
        self.skip_details.append((email, reason))
