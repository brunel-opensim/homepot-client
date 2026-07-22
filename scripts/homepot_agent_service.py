r"""Windows service wrapper for the HOMEPOT Device Agent.

Installs, starts, stops, and removes the agent as a Windows service
using pywin32 (``win32serviceutil``).

Usage::

    python homepot-agent-service.py install
    python homepot-agent-service.py start
    python homepot-agent-service.py stop
    python homepot-agent-service.py remove

Service recovery (automatic restart) must be configured manually
or via ``install-agent.ps1``::

    sc failure HomepotAgent reset=86400 actions=restart/60000/restart/60000/restart/60000
"""

import asyncio
import logging
import os
import sys
import threading

logger = logging.getLogger(__name__)

# Try to import pywin32 – fail early with a clear message
try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
except ImportError:
    sys.exit(
        "pywin32 is required.  Install with: pip install homepot-client[agent]"
    )


class HomepotAgentService(win32serviceutil.ServiceFramework):
    """Windows Service that runs the HOMEPOT Device Agent."""

    _svc_name_ = "HomepotAgent"
    _svc_display_name_ = "HOMEPOT Device Agent"
    _svc_description_ = (
        "Managed endpoint runtime for HOMEPOT device management. "
        "Handles enrolment, heartbeat, telemetry, and command execution."
    )

    def __init__(self, args: list[str]) -> None:
        """Initialize the service and create the stop event."""
        win32serviceutil.ServiceFramework.__init__(self, args)
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._shutdown_event: asyncio.Event | None = None
        self._agent_thread: threading.Thread | None = None

    def SvcDoRun(self) -> None:
        """Entry point when the service is started by the SCM."""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self._report_status(win32service.SERVICE_RUNNING)
        self._run_agent()

    def SvcStop(self) -> None:
        """Request graceful shutdown when the SCM stops the service."""
        self._report_status(win32service.SERVICE_STOP_PENDING)
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, ""),
        )
        if self._shutdown_event is not None:
            self._shutdown_event.set()
        win32event.SetEvent(self._stop_event)

    def _report_status(self, state: int) -> None:
        """Report service status to the SCM."""
        if hasattr(self, "CreateServiceEntry"):
            self.CreateServiceEntry()
        self.ReportServiceStatus(
            win32service.SERVICE_WIN32_OWN_PROCESS,
            state,
            win32service.SERVICE_ACCEPT_STOP,
            win32service.NO_ERROR,
        )

    def _run_agent(self) -> None:
        """Run the agent in a dedicated thread with its own event loop."""
        self._shutdown_event = asyncio.Event()

        def _thread_target() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                from homepot.agent.real_device_agent import run_agent

                loop.run_until_complete(run_agent(shutdown_event=self._shutdown_event))
            except Exception as exc:
                logger.exception("Agent runtime failed: %s", exc)
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_ERROR_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, f"Agent runtime failed: {exc}"),
                )
            finally:
                loop.close()

        self._agent_thread = threading.Thread(target=_thread_target, daemon=True)
        self._agent_thread.start()
        win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)


def _configure_python_exe() -> str:
    """Return the path to ``pythonw.exe`` for the current environment."""
    if hasattr(sys, "frozen"):
        exe = sys.executable
    else:
        base = os.path.dirname(sys.executable)
        exe = os.path.join(base, "pythonw.exe")
    if not os.path.exists(exe):
        exe = sys.executable
    return exe


def main() -> None:
    """Entry point for the Windows service wrapper."""
    if len(sys.argv) == 1:
        import inspect
        print(inspect.cleandoc(__doc__))
        return

    # Set up minimal logging so pywin32 can report events
    logging.basicConfig(level=logging.INFO)

    # Hook the service into the pywin32 service framework.
    # win32serviceutil.HandleCommandLine inspects sys.argv and calls
    # the corresponding methods (install, start, stop, remove, etc.).
    sys.argv[0] = _configure_python_exe()
    win32serviceutil.HandleCommandLine(HomepotAgentService)


if __name__ == "__main__":
    main()
