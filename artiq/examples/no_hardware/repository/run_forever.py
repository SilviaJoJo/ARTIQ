from itertools import count
from time import sleep

from artiq.experiment import *


class RunForever(EnvExperiment):
    """
    A demonstration experiment that runs indefinitely until terminated.
    Shows how to implement graceful termination handling in ARTIQ.
    """
    def build(self):
        self.setattr_device("scheduler")

    def run(self):
        try:
            for i in count():
                self.scheduler.pause()
                sleep(1)
                print("ping", i)
        except TerminationRequested:
            print("Terminated gracefully")
