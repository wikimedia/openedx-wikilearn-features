from lms.djangoapps.instructor_task.subtasks import SubtaskStatus


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

    def to_dict(self):
        """
        Output a dict representation of an EnhancedSubtaskStatus object.

        Overrides base class to include failure and skip details.
        """
        d = super().to_dict().copy()
        d['failure_details'] = self.failure_details
        d['skip_details'] = self.skip_details
        return d

    def increment(
        self,
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
        Update the result of a subtask with additional results.
        Extends the base method to also handle details lists.
        """
        super().increment(
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            retried_nomax=retried_nomax,
            retried_withmax=retried_withmax,
            state=state
        )
        if failure_details:
            self.failure_details.extend(failure_details)
        if skip_details:
            self.skip_details.extend(skip_details)

    def add_failure_detail(self, email, reason):
        """Add a single failure detail (email, reason)."""
        self.failure_details.append((email, reason))

    def add_skip_detail(self, email, reason):
        """Add a single skip detail (email, reason)."""
        self.skip_details.append((email, reason))
