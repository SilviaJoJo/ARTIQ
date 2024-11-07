import io
import numpy as np
import matplotlib.pyplot as plt
from artiq.experiment import *


class Thumbnail(EnvExperiment):
    """
    A demonstration experiment that creates a thumbnail image.
    Shows how to generate, save, and store a plot as binary data in ARTIQ.
    """
    def build(self):
        # No build parameters needed for this demo
        pass

    def run(self):
        # No experiment execution needed
        # All processing is done in analyze()
        pass

    # def analyze(self):
        # Create a simple line plot
        # plt.plot([x1, x2, x3, ...]) creates a line plot with y values
        # x-axis will be automatically generated as [0, 1, 2, ...]
        # plt.plot([1, 2, 0, 3, 4])

        # # Create a binary buffer to store the image
        # # BytesIO provides a file-like interface for binary data in memory
        # f = io.BytesIO()

        # # Save the plot to the buffer as PNG format
        # # This avoids saving to disk, keeping everything in memory
        # plt.savefig(f, format="PNG")

        # # Reset buffer position to start
        # # This is necessary because savefig() moves the position to the end
        # f.seek(0)

        # # Store the image data in ARTIQ's dataset
        # # np.void() wraps the binary data for storage
        # # set_dataset stores the data with name "thumbnail"
        # self.set_dataset("thumbnail", np.void(f.read()))

    def analyze(self):
        # Create plot
        plt.plot([1, 2, 0, 3, 4])
        
        # Save to file (optional, for debugging)
        plt.savefig('debug_plot.png')
        
        # Original thumbnail creation code
        f = io.BytesIO()
        plt.savefig(f, format="PNG")
        f.seek(0)
        self.set_dataset("thumbnail", np.void(f.read()))


"""
Usage and Purpose:
1. This experiment demonstrates how to:
   - Create matplotlib plots in ARTIQ
   - Convert plots to binary data
   - Store binary data in ARTIQ datasets

2. The process flow:
   - Generate a simple plot
   - Convert plot to PNG format in memory
   - Store the PNG data in ARTIQ's dataset system

3. The stored thumbnail can be:
   - Displayed in ARTIQ's GUI
   - Retrieved later for analysis
   - Used as a quick visual reference for the experiment

4. Key techniques:
   - Using BytesIO for in-memory file operations
   - Converting matplotlib plots to binary data
   - Using np.void for binary data storage
"""
