"""
NOTE: This file cannot be run directly with artiq_run because:
1. It is an applet definition file, not an experiment file
2. It does not contain any class that inherits from EnvExperiment
3. It is meant to be loaded by code_applet.py, which is the actual experiment file

To run this applet:
1. Use artiq_run --device-db ../device_db.py code_applet.py instead
2. code_applet.py will load this file and create the applet
"""

from PyQt6 import QtWidgets
from artiq.applets.simple import SimpleApplet
from artiq.experiment import *

# A custom widget that displays a dataset value as a large label
# Inherits from QtWidgets.QLabel to create a text display widget
class DemoWidget(QtWidgets.QLabel):
    def __init__(self, args, ctl):
        # Initialize the parent QLabel
        QtWidgets.QLabel.__init__(self)
        # Store the dataset name from command line arguments
        self.dataset_name = args.dataset

    # Called automatically when the monitored dataset changes
    # Parameters:
    #   value: dict containing all datasets
    #   metadata: dataset metadata
    #   persist: persistence flag
    #   mods: modified fields
    def data_changed(self, value, metadata, persist, mods):
        try:
            # Try to get and convert the dataset value to string
            n = str(value[self.dataset_name])
        except (KeyError, ValueError, TypeError):
            # Display "---" if dataset is missing or invalid
            n = "---"
        # Wrap the value in HTML to make it larger
        n = "<font size=15>" + n + "</font>"
        # Update the label text
        self.setText(n)


def main():
    # Create a SimpleApplet with our custom widget
    applet = SimpleApplet(DemoWidget)
    # Register the dataset we want to monitor
    applet.add_dataset("dataset", "dataset to show")
    # Start the applet
    applet.run()

if __name__ == "__main__":
    main()
