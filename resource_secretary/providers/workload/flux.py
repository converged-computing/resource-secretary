import os
import shlex
import time
from typing import Annotated, Any, Dict, List, Mapping, Optional, Union

from ..provider import BaseProvider, dispatch_tool, secretary_tool

JobSubmissionResult = Annotated[
    Dict[str, Any],
    "A dictionary containing 'success' (bool), 'error' (str or None), 'job_id' (int or None), and 'uri' (str).",
]

JobActionResponse = Annotated[
    Dict[str, Any],
    "A structured response containing 'success' (bool), a descriptive 'message' (str), and the 'job_id' and an 'error' if the action was not successful.",
]

JobInfoResult = Annotated[
    Dict[str, Any],
    "A structured report containing success status, error details, and a dictionary of job metadata (state, status, result, returncode, runtime, etc).",
]

LogLinesResult = Annotated[
    Dict[str, Any],
    "A dictionary containing 'success' (bool), 'error' (str or None), 'lines' (list of strings), and 'complete' (bool).",
]


class FluxProvider(BaseProvider):
    """
    The Flux provider interacts with the Flux Framework using native Python bindings.
    It provides modular tools for deep investigation of scheduler state,
    resource utilization, and queue parameters.
    """

    def __init__(self):
        super().__init__()
        self.available: bool = False
        self.handle = None

    @property
    def name(self) -> str:
        return "flux"

    def probe(self) -> bool:
        """
        Checks for the presence of the 'flux' Python library and an active session.
        Sets the public self.handle if successful.

        Returns:
            bool: True if the flux library is importable and a handle can be created.
        """
        try:
            import flux

            # Attempt to create a handle to verify the session is active
            self.handle = flux.Flux()
            self.available = True
        except (ImportError, RuntimeError, Exception):
            self.available = False
        return self.available

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        High-level capacity and versioning for the Hub.

        Returns:
            Dict: Static manifest including total core and node counts.
        """
        if not self.available or not self.handle:
            return {"installed": False}

        import flux.resource

        try:
            listing = flux.resource.list.resource_list(self.handle).get()
            return {
                "system_type": "flux",
                "total_cores": listing.all.ncores,
                "total_nodes": listing.all.nnodes,
                "status": "online",
            }
        except Exception:
            return {"status": "error", "message": "Failed to query flux resources"}

    # Secretary Tools

    @secretary_tool
    def get_resource_status(self) -> Dict[str, Any]:
        """
        Retrieves detailed real-time availability of cores and nodes.

        Returns:
            Dict: A detailed status including 'free_cores', 'up_nodes', and
                  the 'resource_status' execution list (nodelists).
                  Use this to verify if specific nodes are available for a job.
        """
        import flux.resource

        listing = flux.resource.list.resource_list(self.handle).get()
        resource_status = self.handle.rpc("sched-fluxion-resource.status").get()

        return {
            "free_cores": listing.free.ncores,
            "up_nodes": listing.up.nnodes,
            "resource_status": resource_status,
        }

    @secretary_tool
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Retrieves statistics from the Fluxion queue manager.

        Returns:
            Dict: Detailed queue depth, job counts (pending, running), and
                  policy-specific timing information. Use this to estimate
                  current cluster pressure and potential wait times.
        """
        # queue depth is returning a value I do not understand.
        response = self.handle.rpc("sched-fluxion-qmanager.stats-get").get()
        results = {}
        for name, queue in response.items():
            if "queue_depth" in queue:
                del queue["queue_depth"]
            results[name] = queue
        return results

    @secretary_tool
    def get_scheduler_params(self) -> Dict[str, Any]:
        """
        Retrieves the active configuration parameters for the Fluxion scheduler.

        Returns:
            Dict: Includes the 'match-format', 'traverser' type, and 'policy'
                  settings. Use this to determine if the scheduler logic
                  aligns with specific user-requested job shapes.
        """
        return self.handle.rpc("sched-fluxion-resource.params").get()

    @secretary_tool
    def get_resource_utilization_stats(self) -> Dict[str, Any]:
        """
        Retrieves low-level graph and matching statistics for the resources.

        Returns:
            Dict: Includes 'match' success/fail rates and 'graph-uptime'.
                  Use this to diagnose if the scheduler is failing to place
                  jobs due to high fragmentation or resource errors.
        """
        return self.handle.rpc("sched-fluxion-resource.stats-get").get()

    # Dispatch Tools

    @dispatch_tool
    def submit_job(
        self,
        command: List[str],
        uri: Optional[str] = None,
        num_tasks: int = 1,
        cores_per_task: int = 1,
        gpus_per_task: Optional[int] = None,
        num_nodes: int = 1,
        exclusive: bool = False,
        duration: Optional[Union[int, float, str]] = None,
        environment: Optional[Mapping[str, str]] = None,
        env_expand: Optional[Mapping[str, str]] = None,
        cwd: Optional[str] = None,
        rlimits: Optional[Mapping[str, int]] = None,
        name: Optional[str] = None,
        input: Optional[Union[str, os.PathLike]] = None,
        output: Optional[Union[str, os.PathLike]] = None,
        error: Optional[Union[str, os.PathLike]] = None,
        label_io: bool = False,
        unbuffered: bool = False,
        queue: Optional[str] = None,
        bank: Optional[str] = None,
    ) -> JobSubmissionResult:
        """
        Creates a Jobspec from a command and submits it to Flux. This is from flux-mcp.

        Args:
            command: Command to execute (iterable of strings).
            uri: Optional Flux URI. If not provided, uses local instance.
            num_tasks: Number of tasks to create.
            cores_per_task: Number of cores to allocate per task.
            gpus_per_task: Number of GPUs to allocate per task.
            num_nodes: Distribute allocated tasks across N individual nodes.
            exclusive: Always allocate nodes exclusively.
            duration: Time limit in Flux Standard Duration (str), seconds (int/float), or timedelta.
            environment: Mapping of environment variables for the job.
            env_expand: Mapping of environment variables containing mustache templates.
            cwd: Set the current working directory for the job.
            rlimits: Mapping of process resource limits (e.g. {"nofile": 12000}).
            name: Set a custom job name.
            input: Path to a file for job input.
            output: Path to a file for job output (stdout).
            error: Path to a file for job error (stderr).
            label_io: Label output with the source task IDs.
            unbuffered: Disable output buffering.
            queue: Set the queue for the job.
            bank: Set the bank for the job.

        Returns:
            Dictionary containing the success status and Job ID or error message.
        """
        import flux.job

        if isinstance(command, str):
            command = shlex.split(command)
        try:
            jobspec = flux.job.JobspecV1.from_command(
                command=command,
                num_tasks=num_tasks,
                cores_per_task=cores_per_task,
                gpus_per_task=gpus_per_task,
                num_nodes=int(num_nodes),
                exclusive=exclusive,
            )

            # Map additional attributes to jobspec
            if environment is not None:
                jobspec.environment = environment
            if duration is not None:
                jobspec.duration = duration
            if cwd is not None:
                jobspec.cwd = cwd
            if env_expand is not None:
                jobspec.env_expand = env_expand
            if rlimits is not None:
                jobspec.rlimits = rlimits
            if input is not None:
                jobspec.input = input
            if output is not None:
                jobspec.output = output
            if error is not None:
                jobspec.error = error
            if queue is not None:
                jobspec.queue = queue
            if bank is not None:
                jobspec.bank = bank
            if unbuffered is not None:
                jobspec.unbuffered = unbuffered
            if label_io is not None:
                jobspec.label_io = label_io
            if name is not None:
                jobspec.name = name

            jobid = flux.job.submit(self.handle, jobspec)
            return {"success": True, "error": None, "job_id": int(jobid), "uri": uri or "local"}
        except Exception as e:
            return {"success": False, "error": str(e), "job_id": None, "uri": uri or "local"}

    @dispatch_tool
    def cancel_job(self, job_id: Union[int, str], uri: Optional[str] = None) -> JobActionResponse:
        """
        Cancels a specific Flux job.

        Args:
            job_id: The ID of the job to cancel.
            uri: Optional Flux URI.
        """
        import flux.job

        try:
            jid = flux.job.JobID(job_id)
            flux.job.cancel(self.handle, jid)
            return {
                "success": True,
                "message": f"Job {job_id} cancellation requested.",
                "job_id": int(jid),
            }
        except Exception as e:
            return {"success": False, "error": str(e), "message": "Cancellation had an error."}

    @dispatch_tool
    def get_job_info(self, job_id: Union[int, str], uri: Optional[str] = None) -> JobInfoResult:
        """
        Retrieves status and metadata about a specific job.

        Args:
            job_id: The ID of the job.
            uri: Optional Flux URI.
        """
        import flux.job

        try:
            jid = flux.job.JobID(job_id)
            info = dict(flux.job.get_job(self.handle, jid))
            return {"success": True, "error": None, "info": info}
        except Exception as e:
            return {"success": False, "error": str(e), "info": None}

    @dispatch_tool
    def get_job_logs(
        self, job_id: Union[int, str], uri: Optional[str] = None, delay: Optional[int] = None
    ) -> LogLinesResult:
        """
        Retrieves the output logs (stdout/stderr) associated with a specific Flux job.
        If you set the delay, it will cut early and you may not get a complete log.
        If logs are not complete, you might consider waiting and trying again.

        This function monitors the job's event log for output events. It can either
        wait until the job finishes or stop after a specified delay.

        Args:
            job_id: The unique identifier of the job (integer or f58 string).
            uri: Optional Flux handle URI. If omitted, connects to the local instance.
            delay: The maximum time in seconds to spend collecting logs. If None,
               the function blocks until the job event stream is closed.

        Returns:
           A dictionary containing:
            - 'success' (bool): True if the log retrieval was initiated without error.
            - 'error' (str or None): A descriptive error message if retrieval failed.
            - 'lines' (list[str] or None): A list of strings, where each string is
               a chunk of output data captured from the job's 'guest.output' stream.
            - 'return_code' (str or None): 0 if successful and no error.
        """
        import flux.job

        lines = []
        start = time.time()
        complete = False
        try:
            jid = flux.job.JobID(job_id)
            event_watch = flux.job.event_watch(self.handle, jid, "guest.output")

            if event_watch is None:
                return {
                    "success": False,
                    "error": "Job not ready or does not exist",
                    "lines": None,
                    "complete": False,
                }

            complete = True
            for line in event_watch:
                if not line:
                    continue
                if "data" in line.context:
                    lines.append(line.context["data"])

                if delay is not None and (time.time() - start) > delay:
                    complete = False
                    break
            return {"success": True, "error": None, "lines": lines, "complete": complete}
        except Exception as e:
            return {"success": False, "error": str(e), "lines": None, "complete": complete}
