from artiq.experiment import *


class TerminateAll(EnvExperiment):
    """
    An experiment that terminates all running experiments except itself.
    Provides both graceful and immediate termination options.
    """
    def build(self):
        # Request access to the scheduler device
        # The scheduler is used to manage running experiments
        self.setattr_device("scheduler")

        # Add a boolean argument to choose termination method
        # True: graceful termination (default)
        # False: immediate termination
        self.setattr_argument("graceful_termination", BooleanValue(True))

    def run(self):
        # Select termination method based on argument
        if self.graceful_termination:
            # request_termination: Asks experiments to terminate gracefully
            # Allows experiments to clean up resources
            terminate = self.scheduler.request_termination
        else:
            # delete: Immediately terminates experiments
            # May leave resources in undefined states
            terminate = self.scheduler.delete

        # Get all running experiment RIDs (Runtime IDs)
        # scheduler.get_status() returns dict of all running experiments
        for rid in self.scheduler.get_status().keys():
            # Skip terminating ourselves (avoid self-termination)
            if rid != self.scheduler.rid:
                # Terminate the experiment using chosen method
                terminate(rid)


"""
Usage and Purpose:
1. This experiment is used to stop all other running experiments
2. Two termination modes:
   - Graceful (default): Allows experiments to clean up
   - Immediate: Forces experiments to stop immediately

Key Components:
1. scheduler device:
   - Manages experiment execution
   - Provides status information
   - Controls experiment lifecycle

2. graceful_termination argument:
   - True: Uses request_termination (safe)
   - False: Uses delete (forced)

3. RID (Runtime ID):
   - Unique identifier for each running experiment
   - self.scheduler.rid is this experiment's own ID
   - Used to avoid self-termination

Common Use Cases:
1. Emergency stop of all experiments
2. Clearing the experiment queue
3. System reset/cleanup
"""
