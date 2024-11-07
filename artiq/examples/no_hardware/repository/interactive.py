from artiq.experiment import *


class InteractiveDemo(EnvExperiment):
    def build(self):
        pass

    def run(self):
        print("Waiting for user input...")
        with self.interactive(title="Interactive Demo") as interactive:
            # Interactive input fields explanation:

            # 1. pyon_value: Python Object Notation value
            interactive.setattr_argument("pyon_value",
                PYONValue(self.get_dataset("foo", default=42)))
            # - Accepts any Python value
            # - Default is 42 (from dataset "foo" or fallback)

            # 2. number: Floating point with microsecond unit
            interactive.setattr_argument("number", NumberValue(42e-6,
                unit="us",      # Unit is microseconds
                precision=4))   # 4 decimal places
            # - You can input like: 42.5, 100.0, etc.
            # - Will be displayed with 'us' (microsecond) unit

            # 3. integer: Whole number value
            interactive.setattr_argument("integer", NumberValue(42,
                step=1,         # Increment by 1
                precision=0))   # No decimal places
            # - Input whole numbers: 42, 100, -5, etc.

            # 4. string: Text input
            interactive.setattr_argument("string", StringValue("Hello World"))
            # - Input any text string

            # 5. scan: Scanning parameter
            interactive.setattr_argument("scan", Scannable(
                global_max=400,           # Maximum allowed value
                default=NoScan(325),      # Default single value
                precision=6))             # 6 decimal places
            # - Can select scan type (No Scan, Range Scan, etc.)
            # - Set scan parameters if applicable

            # 6. boolean: True/False checkbox (in "Group")
            interactive.setattr_argument("boolean", BooleanValue(True), "Group")
            # - Simple checkbox: True or False

            # 7. enum: Drop-down selection (in "Group")
            interactive.setattr_argument("enum",
                EnumerationValue(["foo", "bar", "quux"], "foo"), "Group")
            # - Select one from: "foo", "bar", or "quux"
        print("Done! Values:")
        print(interactive.pyon_value)
        print(interactive.boolean)
        print(interactive.enum)
        print(interactive.number, type(interactive.number))
        print(interactive.integer, type(interactive.integer))
        print(interactive.string)
        for i in interactive.scan:
            print(i)
