"""
core/db_worker.py
─────────────────
Async database worker: runs all heavy SQLite queries on a dedicated
background thread and posts results back to the Tk main thread via
`widget.after(0, callback)`.

Usage
-----
    from core.db_worker import db_worker

    def on_result(rows, error):
        if error:
            show_error(error)
        else:
            refresh_grid(rows)

    db_worker.run(
        query=lambda: my_db_read(),   # any zero-arg callable
        on_done=on_result,            # called on the Tk thread
        tk_widget=self,               # any live Tk widget (for .after)
    )
"""

import queue
import threading
from typing import Callable, Any, Optional


class _DbWorker(threading.Thread):
    """
    Single daemon thread that drains a job queue.
    Each job is a (query_fn, on_done, tk_widget) tuple.

    query_fn  : () -> Any          — executed on this background thread
    on_done   : (result, error)    — scheduled on the Tk thread via after(0)
    tk_widget : ctk/tk widget      — used solely for .after(); must be alive
                                     when on_done fires (checked defensively).
    """

    def __init__(self):
        super().__init__(daemon=True, name="DbWorker")
        self._queue: queue.Queue = queue.Queue()
        self.start()

    # ── Public API ────────────────────────────────────────────────────────────

    def run_query(
        self,
        query_fn: Callable[[], Any],
        on_done: Callable[[Any, Optional[Exception]], None],
        tk_widget,
    ) -> None:
        """
        Enqueue a DB job.

        Parameters
        ----------
        query_fn   : Zero-argument callable that performs the DB work.
                     Must be thread-safe (i.e. open its own connection via
                     db.get_connection() — do NOT share connections across
                     threads with sqlite3).
        on_done    : Called on the Tk main thread with (result, error).
                     ``error`` is None on success, an Exception on failure.
        tk_widget  : Any live Tk widget; used to post the callback via after().
        """
        self._queue.put((query_fn, on_done, tk_widget))

    # ── Thread body ───────────────────────────────────────────────────────────

    def run(self):
        while True:
            try:
                query_fn, on_done, widget = self._queue.get(block=True)
                try:
                    result = query_fn()
                    error  = None
                except Exception as exc:
                    result = None
                    error  = exc
                finally:
                    self._queue.task_done()

                # Post callback to the Tk event loop
                try:
                    if widget.winfo_exists():
                        widget.after(0, lambda r=result, e=error: on_done(r, e))
                except Exception:
                    pass  # widget destroyed before callback — silently skip
            except Exception:
                pass  # queue.Empty or unexpected error — keep draining


# Module-level singleton — import and use directly
db_worker = _DbWorker()
