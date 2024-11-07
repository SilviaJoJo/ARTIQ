"""
This file simulates a quantum physics experiment that studies atomic state transitions
by scanning frequencies and measuring fluorescence (brightness).
"""

import time
import random
import numpy as np
from scipy.optimize import curve_fit
from artiq.experiment import *

# Mathematical model for the fluorescence signal
# Simulates the response of an atom to different frequencies
def model(x, F0):
    # Fixed parameters of the model
    t = 0.02    # Evolution time
    tpi = 0.03  # Pi pulse time
    A = 80      # Maximum fluorescence
    B = 40      # Minimum fluorescence
    
    # Returns a Lorentzian-like function that describes the atomic response
    # x: frequency being tested
    # F0: resonance frequency (center of the curve)
    return A + (B - A)/2/(4*tpi**2*(x - F0)**2+1)*(
        1 - np.cos(np.pi*t/tpi*np.sqrt(4*tpi**2*(x - F0)**2 + 1))
    )


class FloppingF(EnvExperiment):
    """Flopping F simulation - Simulates frequency scanning of atomic transitions"""

    def build(self):
        # Device initialization
        self.setattr_device("ccb")       # Core Control Bus - for creating applets
        self.setattr_device("scheduler") # Scheduler - for experiment timing

        # Experiment parameters
        # 1. Scan Parameter (Scannable)
        self.setattr_argument("frequency_scan", Scannable(
            default=RangeScan(1000, 2000, 100)))
        # - Displays as scan range settings in GUI
        # - Becomes an iterable object during runtime

        # 2. Numeric Parameter (NumberValue)
        self.setattr_argument("F0", NumberValue(1500, min=1000, max=2000))
        # - Displays as a numeric input field in GUI
        # - Becomes a single numeric value during runtime

        # 3. Noise amplitude parameter
        self.setattr_argument("noise_amplitude", NumberValue(
            0.1, min=0, max=100, step=0.01))

    def run(self):
        # Get the total number of frequency points to scan
        l = len(self.frequency_scan)
        
        # Initialize three datasets with NaN values:
        # 1. X-axis data (frequencies to be tested)
        self.set_dataset("flopping_f_frequency",
                         np.full(l, np.nan),
                         broadcast=True, archive=False)
        # 2. Y-axis data (measured brightness values)
        self.set_dataset("flopping_f_brightness",
                         np.full(l, np.nan),
                         broadcast=True)
        # 3. Fitted curve data (will be filled during analysis)
        self.set_dataset("flopping_f_fit", np.full(l, np.nan),
                         broadcast=True, archive=False)

        # Create a real-time plotting applet using the Core Control Bus (ccb)
        # This will display:
        # - brightness values vs. frequency
        # - fitted curve overlaid on the data
        self.ccb.issue("create_applet", "flopping_f",
           "${artiq_applet}plot_xy "
           "flopping_f_brightness --x flopping_f_frequency "
           "--fit flopping_f_fit")

        # Main experimental loop: scan through each frequency point
        for i, f in enumerate(self.frequency_scan):
            # Calculate simulated brightness with added random noise
            m_brightness = model(f, self.F0) + self.noise_amplitude*random.random()
            
            # Update the datasets point by point
            # This allows real-time visualization of the data
            self.mutate_dataset("flopping_f_frequency", i, f)
            self.mutate_dataset("flopping_f_brightness", i, m_brightness)
            
            # Simulate measurement time delay
            time.sleep(0.1)
            
        # Schedule the next run of this experiment in 20 seconds
        self.scheduler.submit(due_date=time.time() + 20)

    def analyze(self):
        # Get the brightness dataset for analysis
        brightness = self.get_dataset("flopping_f_brightness")
        try:
            frequency = self.get_dataset("flopping_f_frequency", archive=False)
        except KeyError:
            # If frequency dataset is missing, reconstruct it from frequency_scan
            
            # Syntax: np.fromiter(iterable, dtype)
            # - iterable: self.frequency_scan (contains the frequency points)
            # - dtype: np.float (converts all values to floating point)
            # This creates a NumPy array directly from the frequency_scan iterator
            frequency = np.fromiter(self.frequency_scan, np.float)
            
            # Verify that reconstructed frequency array matches brightness array shape
            assert frequency.shape == brightness.shape
            
            # Store the reconstructed frequency data
            self.set_dataset("flopping_f_frequency", frequency,
                             broadcast=True, archive=False)

        # Fit experimental data to the model
        # Syntax: curve_fit(model_function, x_data, y_data, p0=initial_guess)
        # Returns: popt (optimal parameters), pcov (covariance matrix)
        popt, pcov = curve_fit(model, frequency, brightness,
                               p0=[self.get_dataset("flopping_freq", 1500.0,
                                                    archive=False)])
        
        # Calculate standard error of the fit parameters
        # np.sqrt(np.diag(pcov)) extracts the standard deviations from covariance matrix
        perr = np.sqrt(np.diag(pcov))
        
        # If fit error is acceptable, save results
        if perr < 0.1:
            F0 = float(popt)
            self.set_dataset("flopping_freq", F0, persist=True, archive=False)
            # Generate points for the fitted curve
            self.set_dataset("flopping_f_fit",
                             np.array([model(x, F0) for x in frequency]),
                             broadcast=True, archive=False)
