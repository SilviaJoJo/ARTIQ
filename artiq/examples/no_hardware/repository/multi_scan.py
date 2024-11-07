from artiq.experiment import *


class MultiScan(EnvExperiment):
    """
    Demonstrates multi-dimensional parameter scanning.
    This experiment scans three parameters (a, b, c) simultaneously.
    """
    def build(self):
        # Define three scannable parameters a, b, c
        # Each parameter will scan from 0 to 10 with 4 points
        # RangeScan(start, stop, npoints):
        # - start: beginning value (0)
        # - stop: ending value (10)
        # - npoints: number of points to scan (4)
        self.setattr_argument("a", Scannable(default=RangeScan(0, 10, 4)))
        self.setattr_argument("b", Scannable(default=RangeScan(0, 10, 4)))
        self.setattr_argument("c", Scannable(default=RangeScan(0, 10, 4)))

    def run(self):
        # Create a MultiScanManager to handle multiple parameter scanning
        # Each tuple contains:
        # - parameter name (string)
        # - parameter scan object (self.a, self.b, self.c)
        msm = MultiScanManager(
            ("a", self.a),
            ("b", self.b),
            ("c", self.c),
        )

        # Iterate through all combinations of scan points
        # This will generate 4 x 4 x 4 = 64 combinations total
        # point is a namespace object containing current values of a, b, c
        for point in msm:
            print("a={} b={} c={}".format(point.a, point.b, point.c))


"""
Output Analysis:

1. Step Size Calculation:
   - For each parameter (a, b, c):
   - step = (stop - start) / (npoints - 1)
   - step = (10 - 0) / (4 - 1) = 3.3333...
   - Points: [0, 3.3333, 6.6667, 10]

2. Scanning Pattern:
   - Total combinations: 4 x 4 x 4 = 64 points
   - Nested loop structure:
     c: innermost loop (changes fastest)
     b: middle loop
     a: outermost loop (changes slowest)

3. Example Output Sequence:
   First set (a=0):
   a=0.0 b=0.0 c=0.0
   a=0.0 b=0.0 c=3.3333
   a=0.0 b=0.0 c=6.6667
   a=0.0 b=0.0 c=10.0
   
   Next b increment:
   a=0.0 b=3.3333 c=0.0
   ...

4. Pattern Analysis:
   - c cycles through all values for each b value
   - b cycles through all values for each a value
   - a changes only after all b,c combinations are done
   - Each parameter takes exactly 4 values
   - Values are equally spaced between start and stop

5. Use Cases:
   - Parameter space exploration
   - Finding optimal parameter combinations
   - Studying parameter interactions
   - Systematic measurements over a range of conditions
"""
