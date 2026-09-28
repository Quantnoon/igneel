"""Windowed launcher for the live trading bot."""

from pathlib import Path
import queue
import sys
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk


if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))


class _QueueWriter:
    def __init__(self, output_queue):
        self.output_queue = output_queue

    def write(self, text):
        if text:
            self.output_queue.put(text)
        return len(text)

    def flush(self):
        pass


class BotWindow:
    def __init__(self, root):
        self.root = root
        self.output_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.close_when_stopped = False
        self.worker_error = None
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.root.title("Igneel Trading Bot")
        self.root.geometry("900x560")
        self.root.minsize(560, 320)
        self._set_icon()

        container = ttk.Frame(root, padding=10)
        container.pack(fill=tk.BOTH, expand=True)
        self.status = tk.StringVar(value="Starting bot…")
        ttk.Label(container, textvariable=self.status).pack(anchor=tk.W, pady=(0, 8))

        log_frame = ttk.Frame(container)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        sys.stdout = _QueueWriter(self.output_queue)
        sys.stderr = _QueueWriter(self.output_queue)
        self.worker = threading.Thread(target=self._run_bot, name="live-bot", daemon=False)
        self.worker.start()
        self.root.after(100, self._drain_output)

    def _set_icon(self):
        bundle_dir = getattr(sys, "_MEIPASS", None)
        icon_path = (
            Path(bundle_dir) / "igneel.ico"
            if bundle_dir
            else Path(__file__).resolve().parent / "igneel.ico"
        )
        if icon_path.is_file():
            self.root.iconbitmap(default=str(icon_path))

    def _run_bot(self):
        try:
            from live_bot.live_bot import run_bot

            run_bot(stop_event=self.stop_event)
        except BaseException as exc:
            self.worker_error = exc
            traceback.print_exc(file=sys.stderr)
        finally:
            self.output_queue.put(None)

    def _append_output(self, text):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text)
        line_count = int(self.log.index("end-1c").split(".")[0])
        if line_count > 10000:
            self.log.delete("1.0", "%d.0" % (line_count - 10000))
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _drain_output(self):
        finished = False
        while True:
            try:
                item = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                finished = True
            else:
                self._append_output(item)

        if finished or not self.worker.is_alive():
            self.status.set("Stopped" if self.stop_event.is_set() else "Bot exited")
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            if self.close_when_stopped:
                self.root.destroy()
            elif self.worker_error is not None:
                messagebox.showerror(
                    "Bot stopped unexpectedly",
                    "The bot encountered an error. Details are shown in the log window.",
                    parent=self.root,
                )
            return

        if self.stop_event.is_set():
            self.status.set("Stopping after the current signal pass…")
        self.root.after(100, self._drain_output)

    def _on_close(self):
        if not self.worker.is_alive():
            self.root.destroy()
            return
        if not messagebox.askyesno(
            "Stop trading bot?",
            "The bot will finish its current signal pass before it stops. Continue?",
            parent=self.root,
        ):
            return
        self.close_when_stopped = True
        self.stop_event.set()
        self.status.set("Stopping after the current signal pass…")


def main():
    root = tk.Tk()
    BotWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
