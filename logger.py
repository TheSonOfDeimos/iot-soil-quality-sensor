import time

class Logger:
    # Severity levels
    DEBUG   = 10
    INFO    = 20
    WARNING = 30
    ERROR   = 40

    level_names = {
        DEBUG:   "DEBUG",
        INFO:    "INFO",
        WARNING: "WARN",
        ERROR:   "ERROR",
    }

    def __init__(self, level=INFO):
        self.level = level

    def set_level(self, level):
        self.level = level

    def log(self, level, msg):
        if level < self.level:
            return
        t = time.ticks_ms()  # uptime in ms
        level_name = self.level_names.get(level, "?")
        print(f"[{t:>8} ms ][ {level_name:5} ] {msg}")

    def debug(self, msg):   self.log(self.DEBUG, msg)
    def info(self, msg):    self.log(self.INFO, msg)
    def warning(self, msg): self.log(self.WARNING, msg)
    def error(self, msg):   self.log(self.ERROR, msg)

# --- Singleton instance ---
log = Logger()
