"""Pic de somme RSS pour le processus qui écoute et ses descendants."""

import re
import subprocess
import threading


SAMPLE_INTERVAL = .25
LISTENER = ("/usr/sbin/lsof", "-nP", "-a", "-iTCP@127.0.0.1:11434", "-sTCP:LISTEN", "-Fpc")


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=.7).stdout


def server_identity():
    try:
        rows = command(*LISTENER).splitlines()
        processes = "\n".join(row for row in rows if row.startswith(("p", "c")))
        listener = re.fullmatch(r"p([1-9][0-9]*)\ncollama", processes)
        if not listener:
            return None
        pid = int(listener[1])
        signature = command("/bin/ps", "-ww", "-p", str(pid), "-o", "lstart=", "-o", "command=").strip()
        # lstart précède les arguments. Accepter le binaire Ollama dans le PATH ou dans un bundle.
        fields = signature.split(maxsplit=5)
        if len(fields) == 6 and re.fullmatch(r"(?:.*/)?ollama serve(?: .*)?", fields[5]):
            return pid, signature
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def tree_rss(rows, root_pid):
    children = {}
    resident_sizes = {}
    for line in rows.splitlines():
        pid, parent, rss = map(int, line.split())
        resident_sizes[pid] = rss
        children.setdefault(parent, []).append(pid)
    if root_pid not in resident_sizes:
        return None
    seen = set()
    pending = [root_pid]
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        pending.extend(children.get(pid, ()))
    return sum(resident_sizes[pid] for pid in seen)


class RssSampler:
    def __init__(self, identity):
        self.identity = identity
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.sample_until_stopped)
        self.peak = None
        self.samples = 0
        self.identity_lost = False

    def __enter__(self):
        if self.identity:
            self.thread.start()
        return self

    def __exit__(self, *_):
        if self.identity:
            self.stopped.set()
            self.thread.join()
            if server_identity() != self.identity:
                self.identity_lost = True

    def sample_until_stopped(self):
        while not self.stopped.is_set():
            try:
                pid, signature = self.identity
                observed = command("/bin/ps", "-ww", "-p", str(pid), "-o", "lstart=", "-o", "command=").strip()
                if observed != signature:
                    self.identity_lost = True
                    return
                rss = tree_rss(command("/bin/ps", "-axo", "pid=,ppid=,rss="), pid)
                if rss is not None and not self.stopped.is_set():
                    self.samples += 1
                    self.peak = rss if self.peak is None else max(self.peak, rss)
            except (OSError, ValueError, subprocess.SubprocessError):
                # Un échantillon absent ne vaut pas zéro.
                pass
            self.stopped.wait(SAMPLE_INTERVAL)

    def result(self):
        known = self.identity is not None and not self.identity_lost
        return {
            "server_pid": self.identity[0] if known else None,
            "peak_tree_rss_kib": self.peak if known else None,
            "rss_samples": self.samples if known else None,
        }
