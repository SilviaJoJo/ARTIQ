"""
Tutorial on how to run this code:

1. Open a terminal and run the following command to start the remote execution controller:
   python3 -m artiq.examples.remote_exec_controller

2. In another terminal, run this script using the ARTIQ environment.

This script demonstrates remote execution with ARTIQ, allowing you to run experiments either locally or remotely.
"""

import time
import inspect

from sipyco.remote_exec import connect_global_rpc
from artiq.experiment import *
import remote_exec_processing

class RemoteExecDemo(EnvExperiment):
    def build(self):
        # Set up devices and arguments
        self.setattr_device("camera_sim")  # Simulated camera device
        self.setattr_device("scheduler")   # Scheduler device
        self.setattr_argument("remote_exec", BooleanValue(False))  # Argument to enable remote execution
        self.setattr_argument("show_picture", BooleanValue(True), "Local options")  # Option to show picture
        self.setattr_argument("enable_fit", BooleanValue(True), "Local options")  # Option to enable fitting
        if self.remote_exec:
            self.setattr_device("camera_sim_rexec")  # Remote execution camera device

    def prepare(self):
        # Prepare for remote execution if enabled
        if self.remote_exec:
            connect_global_rpc(self.camera_sim_rexec)  # Connect to remote execution RPC
            self.camera_sim_rexec.add_code(
                inspect.getsource(remote_exec_processing))  # Add processing code to remote execution

    def transfer_parameters(self, parameters):
        # Transfer parameters to datasets
        w, h, cx, cy = parameters
        self.set_dataset("rexec_demo.gaussian_w", w, archive=False, broadcast=True)  # Set Gaussian width
        self.set_dataset("rexec_demo.gaussian_h", h, archive=False, broadcast=True)  # Set Gaussian height
        self.set_dataset("rexec_demo.gaussian_cx", cx, archive=False, broadcast=True)  # Set Gaussian center x
        self.set_dataset("rexec_demo.gaussian_cy", cy, archive=False, broadcast=True)  # Set Gaussian center y

    def fps_meter(self):
        # Measure frames per second
        t = time.monotonic()
        if hasattr(self, "last_pt_update"):
            self.iter_count += 1
            dt = t - self.last_pt_update
            if dt >= 5:
                pt = dt/self.iter_count  # Calculate period time
                self.set_dataset("rexec_demo.picture_pt", pt, archive=False, broadcast=True)  # Set period time dataset
                self.last_pt_update = t
                self.iter_count = 0
        else:
            self.last_pt_update = t
            self.iter_count = 0

    def run_local(self):
        # Run the experiment locally
        while True:
            self.fps_meter()  # Update FPS meter
            data = self.camera_sim.get_picture()  # Get picture from simulated camera
            if self.show_picture:
                self.set_dataset("rexec_demo.picture", data,
                                 archive=False, broadcast=True)  # Broadcast picture data
            if self.enable_fit:
                p = remote_exec_processing.fit(data, self.get_dataset)  # Fit Gaussian to data
                self.transfer_parameters(p)  # Transfer fit parameters
            self.scheduler.pause()  # Pause the scheduler

    def run_remote(self):
        # Run the experiment remotely
        while True:
            self.fps_meter()  # Update FPS meter
            p = self.camera_sim_rexec.call("get_and_fit")  # Call remote method to get and fit data
            self.transfer_parameters(p)  # Transfer fit parameters
            self.scheduler.pause()  # Pause the scheduler

    def run(self):
        # Main run method to choose between local and remote execution
        try:
            if self.remote_exec:
                self.run_remote()  # Run remotely if remote_exec is enabled
            else:
                self.run_local()  # Otherwise, run locally
        except TerminationRequested:
            pass  # Handle termination request gracefully
