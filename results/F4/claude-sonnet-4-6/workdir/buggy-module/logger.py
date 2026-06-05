"""
Lightweight structured logger.
"""
import datetime


LEVELS = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


class Logger:
    def __init__(self, name, level="INFO"):
        self.name = name
        # FIX Bug 8: convert the level name to its integer value for correct comparisons
        self.level = LEVELS.get(level, 1)
        self.records = []

    def is_enabled(self, level_name):
        # FIX Bug 9: now both sides are int (self.level is stored as int), comparison works correctly
        return LEVELS.get(level_name, -1) >= self.level

    def _log(self, level_name, message, **context):
        if not self.is_enabled(level_name):
            return
        record = {
            "ts": datetime.datetime.utcnow().isoformat(),
            "logger": self.name,
            "level": level_name,
            "message": message,
            "context": context,
        }
        self.records.append(record)
        return record

    def debug(self, msg, **ctx):    return self._log("DEBUG",    msg, **ctx)
    def info(self, msg, **ctx):     return self._log("INFO",     msg, **ctx)
    def warning(self, msg, **ctx):  return self._log("WARNING",  msg, **ctx)
    def error(self, msg, **ctx):    return self._log("ERROR",    msg, **ctx)
    def critical(self, msg, **ctx): return self._log("CRITICAL", msg, **ctx)

    def get_records(self, min_level="DEBUG"):
        # FIX Bug 10: use >= to return records at or ABOVE min_level (not below)
        min_val = LEVELS.get(min_level, 0)
        return [r for r in self.records if LEVELS[r["level"]] >= min_val]
