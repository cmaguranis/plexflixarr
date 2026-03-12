import logging
import re

_RESET = "\033[0m"

_LEVEL_COLORS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[35m",  # magenta
}

# 256-color palette for package names (avoid 0-15 which vary per terminal theme)
_PKG_PALETTE = [
    "\033[38;5;33m",  # blue
    "\033[38;5;38m",  # teal
    "\033[38;5;135m",  # purple
    "\033[38;5;166m",  # orange
    "\033[38;5;105m",  # violet
    "\033[38;5;43m",  # seafoam
    "\033[38;5;172m",  # amber
    "\033[38;5;67m",  # steel blue
]

# Distinct colors for job IDs so each job stands out
_JOB_PALETTE = [
    "\033[38;5;208m",  # orange
    "\033[38;5;51m",  # aqua
    "\033[38;5;201m",  # pink
    "\033[38;5;118m",  # lime
    "\033[38;5;226m",  # yellow
    "\033[38;5;165m",  # purple
    "\033[38;5;45m",  # sky blue
    "\033[38;5;214m",  # gold
    "\033[38;5;197m",  # hot pink
    "\033[38;5;82m",  # bright green
]

_JOB_RE = re.compile(r"\[job (\d+)\]")


def _pkg_color(name: str) -> str:
    parts = name.split(".")
    key = parts[1] if len(parts) > 1 and parts[0] == "src" else parts[0]
    return _PKG_PALETTE[hash(key) % len(_PKG_PALETTE)]


class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        r = logging.makeLogRecord(record.__dict__)

        level_color = _LEVEL_COLORS.get(r.levelname, "")
        if level_color:
            r.levelname = f"{level_color}{r.levelname}{_RESET}"

        pkg_color = _pkg_color(r.name)
        r.name = f"{pkg_color}{r.name}{_RESET}"

        result = super().format(r)

        def _color_job(m: re.Match) -> str:
            job_id = int(m.group(1))
            c = _JOB_PALETTE[job_id % len(_JOB_PALETTE)]
            return f"{c}[job {job_id}]{_RESET}"

        return _JOB_RE.sub(_color_job, result)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        ColorFormatter(
            fmt="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logging.basicConfig(level=level, handlers=[handler])
