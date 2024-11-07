import logging
from artiq.experiment import *

# SubComponent1: Demonstrates the use of scan and enumeration parameters
class SubComponent1(HasEnvironment):
    def build(self):
        # Set up scan parameter with two scan modes:
        # 1. NoScan with fixed value 3250
        # 2. Range scan from 10-20 with 6 points, randomized
        # 3. unit is kHz
        # 4. “Flux capacitor” is the name of the device that contains this parameter
        self.setattr_argument("sc1_scan",
            Scannable(default=[NoScan(3250), RangeScan(10, 20, 6, randomize=True)],
                      unit="kHz"),
            "Flux capacitor")
        # Set up enumeration parameter with options 1,2,3 and default value "1"
        self.setattr_argument("sc1_enum", EnumerationValue(["1", "2", "3"], "1"),
                              "Flux capacitor")

    def do(self):
        # Print scan and enumeration parameter values
        print("SC1:")
        for i in self.sc1_scan:
            print(i)
        print(self.sc1_enum)

# SubComponent2: Demonstrates boolean, scan and enumeration parameters
class SubComponent2(HasEnvironment):
    def build(self):
        # Set up boolean parameter with default False
        self.setattr_argument("sc2_boolean", BooleanValue(False),
                              "Transporter")
        # Set up scan parameter with 49 points between 200-300
        self.setattr_argument("sc2_scan", Scannable(
                                          default=RangeScan(200, 300, 49)),
                              "Transporter")
        # Set up enumeration parameter with options 3,4,5 and default value "3"
        self.setattr_argument("sc2_enum", EnumerationValue(["3", "4", "5"], "3"),
                              "Transporter")

    def do(self):
        # Print all parameter values
        print("SC2:")
        print(self.sc2_boolean)
        for i in self.sc2_scan:
            print(i)
        print(self.sc2_enum)

# Main experiment class: Demonstrates various ARTIQ parameter types
class ArgumentsDemo(EnvExperiment):
    def build(self):
        # PYON value parameter, fetched from dataset "foo" with default 42
        self.setattr_argument("pyon_value",
            PYONValue(self.get_dataset("foo", default=42)))
        
        # Number parameter with unit and precision settings
        self.setattr_argument("number", NumberValue(42e-6,
                                                    unit="us",
                                                    precision=4))
        # Integer parameter with step size 1
        self.setattr_argument("integer", NumberValue(42,
                                                     step=1, precision=0))
        # String parameter
        self.setattr_argument("string", StringValue("Hello World"))
        
        # Scan parameter with global maximum 400
        self.setattr_argument("scan", Scannable(global_max=400,
                                                default=NoScan(325),
                                                precision=6))
        # Boolean parameter in "Group"
        self.setattr_argument("boolean", BooleanValue(True), "Group")
        # Enumeration parameter in "Group"
        self.setattr_argument("enum", EnumerationValue(
            ["foo", "bar", "quux"], "foo"), "Group")

        # Create subcomponent instances
        self.sc1 = SubComponent1(self)
        self.sc2 = SubComponent2(self)

    def run(self):
        # Demonstrate different logging levels
        logging.error("logging test: error")
        logging.warning("logging test: warning")
        logging.warning("logging test:" + " this is a very long message."*15)
        logging.info("logging test: info")
        logging.debug("logging test: debug")

        # Print all parameter values
        print(self.pyon_value)
        print(self.boolean)
        print(self.enum)
        print(self.number, type(self.number))
        print(self.integer, type(self.integer))
        print(self.string)
        for i in self.scan:
            print(i)
            
        # Execute subcomponent operations
        self.sc1.do()
        self.sc2.do()