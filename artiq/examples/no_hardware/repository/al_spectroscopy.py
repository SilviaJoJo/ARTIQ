"""
Aluminum Ion Spectroscopy Experiment

Experimental Principle:
1. Laser Cooling and Trapping:
   - First cool and trap aluminum ions using laser cooling
   - Reduces ion motion to improve spectroscopy precision
   
2. Spectroscopy Process:
   - Apply spectroscopy laser to probe the ion's energy levels
   - The frequency is set to 432 MHz to match specific transitions
   - Secondary control (spectroscopy_b) fine-tunes the measurement
   
3. State Detection:
   - Use state detection laser to determine ion's quantum state
   - Collect fluorescence using PMT (Photomultiplier Tube)
   - Low photon count (<10) indicates ion in ground state (state 0)
   - High photon count (>15) indicates ion in excited state
   
4. Measurement Statistics:
   - Experiment repeats 100 times for statistical significance
   - Counts how often ion is found in ground state
   - Results help determine transition properties

Hardware Requirements:
- Laser cooling system
- Spectroscopy laser with precise frequency control
- State detection laser
- PMT for fluorescence detection
- Mains synchronization for noise reduction
"""

# To run this experiment:
# artiq_run --device-db ../device_db.py al_spectroscopy.py

from artiq.experiment import *


class AluminumSpectroscopy(EnvExperiment):
    """Aluminum spectroscopy (simulation)"""

    def build(self):
        # Initialize all required devices
        self.setattr_device("core")                # Main ARTIQ core device
        self.setattr_device("mains_sync")          # Synchronization with mains power
        self.setattr_device("laser_cooling")       # Laser for cooling the atoms
        self.setattr_device("spectroscopy")        # Main spectroscopy laser
        self.setattr_device("spectroscopy_b")      # Secondary spectroscopy control
        self.setattr_device("state_detection")     # Laser for state detection
        self.setattr_device("pmt")                 # Photomultiplier tube for detection
        
        # Set initial frequency for spectroscopy (432 MHz)
        self.setattr_dataset("spectroscopy_freq", 432*MHz)
        
        # Define acceptable photon count ranges
        self.setattr_argument("photon_limit_low", NumberValue(10))   # Lower threshold
        self.setattr_argument("photon_limit_high", NumberValue(15))  # Upper threshold

    @kernel
    def run(self):
        state_0_count = 0
        for count in range(100):
            # Synchronize with power line (60 Hz) to reduce electrical noise
            # Wait for next rising edge with timeout of one power cycle (1/60 s)
            # (1/60) s is the period of the power line
            self.mains_sync.gate_rising(1*s/60)
            
            # Schedule experiment start at a precise time:
            # 1. now_mu() gets current time
            # 2. timestamp_mu() converts the time to precise machine units
            # 3. +100us is then added to this precise timestamp
            # 4. at_mu() schedules an absolute time point for next operation (delay here)
            # This ensures high-precision timing control
            at_mu(self.mains_sync.timestamp_mu(now_mu()) + 100*us)
            delay(10*us)
            
            # Apply cooling laser pulse
            # 100 MHz = 10 ns period
            # 100 us duration = 10,000 cycles
            self.laser_cooling.pulse(100*MHz, 100*us)
            delay(5*us)
            
            # Perform spectroscopy sequence
            with parallel:
                # Block 1: Main spectroscopy pulse
                # Apply spectroscopy laser at 432 MHz for 100 us
                self.spectroscopy.pulse(self.spectroscopy_freq, 100*us)
                
                # Block 2: Secondary control sequence
                with sequential:
                    # Wait for half the main pulse duration
                    delay(50*us)
                    # Then adjust secondary parameter
                    self.spectroscopy_b.set(200)  # Set secondary parameter (don't know what this is)
            
            delay(5*us)
            
            # State detection loop
            while True:
                delay(5*us)
                with parallel:
                    # Apply state detection laser
                    self.state_detection.pulse(100*MHz, 10*us)
                    # Count photons using PMT
                    photon_count = self.pmt.count(self.pmt.gate_rising(10*us))
                # Exit loop if photon count is outside acceptable range
                if (photon_count < self.photon_limit_low or
                        photon_count > self.photon_limit_high):
                    break
            
            # State detection principle:
            # - When atom is in ground state (state 0): low fluorescence
            #   * Atom cannot absorb detection laser
            #   * Results in low photon count (<10)
            # - When atom is in excited state: high fluorescence
            #   * Atom can absorb and re-emit photons
            #   * Results in high photon count (>15)
            
            # If photon count is below lower limit, atom is in ground state
            if photon_count < self.photon_limit_low:  # typically < 10 photons
                state_0_count += 1
        
        # Print final results: number of times atom was found in state 0
        print(state_0_count)
