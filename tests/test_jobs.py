"""Background jobs: a cancelled job does not run the step that would save its result."""

from site_agent.drafting import JobRunner
from site_agent.errors import SiteAgentError


def test_a_job_cancelled_while_it_runs_does_not_run_its_finish_step():
    runner = JobRunner(inline=True)
    saved = []

    def work():
        for job_id in list(runner._jobs):  # the only job: cancel it while its work is still running
            runner.cancel(job_id)
        return "a late draft"

    job_id = runner.start(work, lambda result: saved.append(result) or "saved")
    assert saved == []
    assert runner.status(job_id)["state"] == "cancelled"


def test_a_finished_job_runs_its_finish_step_once_and_keeps_its_result():
    runner = JobRunner(inline=True)
    saved = []
    job_id = runner.start(lambda: "text", lambda result: saved.append(result) or "saved-id")
    assert saved == ["text"]
    status = runner.status(job_id)
    assert status["state"] == "done" and status["result"] == "saved-id"


def test_a_finish_step_that_refuses_is_reported_as_the_job_error():
    runner = JobRunner(inline=True)

    def refuse(_result):
        raise SiteAgentError("the state folder is not writable")

    job_id = runner.start(lambda: "text", refuse)
    status = runner.status(job_id)
    assert status["state"] == "failed" and status["error"] == "the state folder is not writable"


def test_status_of_an_unknown_job_is_none():
    runner = JobRunner(inline=True)
    assert runner.status("no-such-job") is None
