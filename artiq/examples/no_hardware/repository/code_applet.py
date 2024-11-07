import os
import time

from artiq.experiment import *


# Do the applet source code path determination on import.
# ARTIQ imports the experiment, then changes the current
# directory to the results, then instantiates the experiment.
# In Python __file__ is a relative path which is not updated
# when the current directory is changed.
#
# Get the absolute path of custom_applet.py to ensure we can find it
# regardless of the current working directory
custom_applet = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                             "custom_applet.py"))


class CreateCodeApplet(EnvExperiment):
    def build(self):
        # Initialize the Core Control Bus device
        self.setattr_device("ccb")

    def run(self):
        # Read the custom applet source code
        with open(custom_applet) as f:
            # Issue command to create a new applet
            # Parameters:
            # - "create_applet": command type
            # - "code_applet_example": applet name
            # - "code_applet_dataset": dataset name this applet will use
            # - code=f.read(): the actual applet code
            # - group="autoapplet": applet group name
            self.ccb.issue("create_applet", "code_applet_example",
               "code_applet_dataset", code=f.read(), group="autoapplet")
            
            # Countdown from 9 to 0, updating the dataset each second
            for i in reversed(range(10)):
                self.set_dataset("code_applet_dataset", i,
                                 broadcast=True, archive=False)
                time.sleep(1)
            
            # Issue command to disable/destroy the applet
            # Parameters:
            # - "disable_applet": command type
            # - "code_applet_example": applet name to disable
            # - group="autoapplet": applet group name
            self.ccb.issue("disable_applet", "code_applet_example",
                           group="autoapplet")
