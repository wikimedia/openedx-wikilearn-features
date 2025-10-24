def update_task_dict(task_dict):
    """
    Update a task dictionary to ensure it includes all fields from EnhancedSubtaskStatus.

    This function modifies the input dictionary in place.
    """
    task_dict['skip_details'] = []
    task_dict['failure_details'] = []
    return task_dict


def get_detailed_message(task_output):
    """
    Extract a detailed message from the task output.
    """
    failure_info = task_output.get('failure_details', [])
    skip_info = task_output.get('skip_details', [])
    detailed_failure_msg = ""
    detailed_skip_msg = ""

    if failure_info:
        detailed_failure_msg = "Detailed Failures: " + ", ".join(
            [f"{email}: {reason}" for email, reason in failure_info])

    if skip_info:
        detailed_skip_msg = "Detailed Skips: " + ", ".join([f"{reason}: {email}" for email, reason in skip_info])

    detailed_msg = "; ".join(filter(None, [detailed_failure_msg, detailed_skip_msg]))

    if not detailed_msg:
        detailed_msg = "No detailed failure or skip information available."

    return detailed_msg
