from artiq.experiment import *
from artiq.sim import devices   # Import simulation devices


class SimpleSimulation(EnvExperiment):
    """Simple simulation"""

    def build(self):
        # Create device manager
        self.dmgr = dict()
        
        # Add core device
        self.dmgr["core"] = devices.Core(self.dmgr)
        self.setattr_device("core")
        
        # Create simulated wave output devices
        for wo in "abcd":
            # Create simulated WaveOutput device
            self.dmgr[wo] = devices.WaveOutput(self.dmgr, wo)
            # Make it accessible as self.a, self.b, etc.
            setattr(self, wo, self.dmgr[wo])

    @kernel
    def run(self):
        with parallel:
            with sequential:
                # Generate pulses on channels a and b
                self.a.pulse(100*MHz, 20*us)  # 100 MHz pulse for 20 microseconds
                self.b.pulse(200*MHz, 20*us)  # 200 MHz pulse for 20 microseconds
            with sequential:
                # Generate pulses on channels c and d
                self.c.pulse(300*MHz, 10*us)  # 300 MHz pulse for 10 microseconds
                self.d.pulse(400*MHz, 20*us)  # 400 MHz pulse for 20 microseconds


# For direct execution (not through ARTIQ master)
if __name__ == "__main__":
    # Create and run experiment
    exp = SimpleSimulation(dict())
    exp.run()
