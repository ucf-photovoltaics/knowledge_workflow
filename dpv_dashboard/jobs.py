"""One local supervised process tree, with durable job history and cancellation.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from uuid import uuid4
from dpv_dashboard import model
from dpv_dashboard.auth import redact


class Jobs:
    def __init__(self):
        self.lock = threading.RLock()
        self.process = None
        self.job = None

    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, project, action, domain=None, stage=None):
        model.require_editor()
        with self.lock:
            if self.running():
                raise ValueError("A dashboard job is running. Cancel it or wait before starting another.")
            if not project["domains"]:
                raise ValueError("Add a domain first.")
            root = model.project_path(project["id"])
            identifier = uuid4().hex
            log = root / "jobs" / f"{identifier}.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, "-u", "-m", "dpv_dashboard.worker", project["id"], action]
            if domain:
                command += ["--domain", domain]
            if stage:
                command += ["--stage", stage]
            self.job = {"id": identifier, "project": project["id"], "action": action, "domain": domain,
                        "stage": stage, "status": "running", "started": model.now(), "log": str(log)}
            self.handle = log.open("w", encoding="utf-8")
            options = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
            self.process = subprocess.Popen(command, cwd=model.ROOT, stdout=self.handle, stderr=subprocess.STDOUT, **options)
            self.job["pid"] = self.process.pid
            model.write(root / "job.json", self.job)
            threading.Thread(target=self._wait, args=(self.process, self.job, self.handle), daemon=True).start()

    def _wait(self, process, job, handle):
        code = process.wait()
        with self.lock:
            handle.close()
            if job["status"] != "cancelled":
                job["status"] = "completed" if code == 0 else "failed"
            job.update(finished=model.now(), exit_code=code)
            root = model.project_path(job["project"])
            model.write(root / "job.json", job)
            model.write(root / "jobs" / f"{job['id']}.json", job)
            active = model.read(root / "active.json", {})
            if active.get("folder"):
                folder = model.inside(root, str(os.path.relpath(active["folder"], root)))
                state = model.read(folder / "dashboard.json", {})
                if state.get("stages", {}).get(active["stage"], {}).get("status") == "running":
                    model.stage_state(folder, active["stage"], "cancelled" if job["status"] == "cancelled" else "interrupted")

    def cancel(self, project_id):
        with self.lock:
            if not self.running() or self.job["project"] != project_id:
                raise ValueError("This project has no running dashboard job.")
            self.job["status"] = "cancelled"
            if os.name == "nt":
                result = subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode and self.process.poll() is None:
                    self.job["status"] = "running"
                    raise ValueError("Windows could not stop the dashboard process tree. Check that this app has permission to stop its child processes.")
            else:
                os.killpg(self.process.pid, signal.SIGTERM)

    def log(self, project):
        job = model.read(model.project_path(project["id"]) / "job.json", {})
        if not job.get("log"):
            return "No jobs have been launched for this project."
        path = model.inside(model.project_path(project["id"]), os.path.relpath(job["log"], model.project_path(project["id"])))
        try:
            with path.open("rb") as handle:
                handle.seek(max(0, path.stat().st_size - 24000))
                return redact(handle.read().decode("utf-8", errors="replace"))
        except OSError:
            return "Job log is not available."


JOBS = Jobs()
