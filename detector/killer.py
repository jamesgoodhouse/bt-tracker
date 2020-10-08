import logging
import signal

class GracefulKiller:
    kill_now = False

    def __init__(self):
        for signame in {'SIGINT', 'SIGTERM'}:
            signal.signal(
                getattr(signal, signame),
                self.exit_gracefully,
            )

    def exit_gracefully(self, signum, frame):
        logging.debug("received '{}' signal".format(signal.strsignal(signum)))
        self.kill_now = True
