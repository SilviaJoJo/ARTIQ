from time import sleep

import numpy as np

from artiq.experiment import *


class Histograms(EnvExperiment):
    """Histograms demo"""
    def run(self):
        # Define histogram parameters
        nbins = 50     # Number of bins in histogram
        npoints = 20   # Number of measurements to take

        # Create histogram bin boundaries
        # np.linspace: Generate evenly spaced numbers over interval [-10, 30]
        # nbins + 1: Need n+1 boundaries to create n bins
        bin_boundaries = np.linspace(-10, 30, nbins + 1)
        self.set_dataset("hd_bins", bin_boundaries,
                         broadcast=True, archive=False)

        # Initialize array for x-axis positions
        xs = np.empty(npoints)        # Create empty array
        xs.fill(np.nan)              # Fill with NaN values
        self.set_dataset("hd_xs", xs,
                         broadcast=True, archive=False)

        # Initialize 2D array for histogram counts
        # Shape: (npoints, nbins) - stores histogram data for each measurement
        self.set_dataset("hd_counts", np.empty((npoints, nbins)), 
                         broadcast=True, archive=False)

        # Main measurement loop
        for i in range(npoints):
            # Generate histogram from normal distribution
            # np.random.normal(i, size=1000): Generate 1000 points with mean=i
            # histogram: array of counts in each bin
            # _: bin edges (discarded since we already have bin_boundaries)
            histogram, _ = np.histogram(np.random.normal(i, size=1000),
                                        bin_boundaries)
            
            # Update histogram data for current measurement
            self.mutate_dataset("hd_counts", i, histogram)
            
            # Update x-axis position (cycles through 0-7)
            self.mutate_dataset("hd_xs", i, i % 8)
            
            # Add delay between measurements
            sleep(0.3)
