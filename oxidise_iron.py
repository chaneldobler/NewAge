import time
import tm, smc, keller
import json
import numpy as np

# the expected units are the standard units: bar, s, celsius

# make qthread and start to pull from worker

class Conditioning:
    def __init__(self, keller, tm, smc):
        self.keller = keller
        self.tm = tm
        self.smc = smc

        #with open("conditioning_config.json", "r") as f:
        #    self.smc_config = json.load(f)

    def oxidise_iron(self, threshold_pressure=0.800, conditioning_oven_temperature=500, preheat_iron_time=300):
        # check pressures
        if not all(p > threshold_pressure for p in self.keller.get_pressure_all()):
            print("Error: Pressure is below threshold. Oxidation process stopped.")
            return False

        # set and run ovens
        self.tm.set_temperature_ovens(conditioning_oven_temperature)
        self.tm.run_ovens()

        # set valves
        self.smc.close_multiple(
            self.smc.vacuum 
            + self.smc.h2 
            + self.smc.trap 
            + self.smc.reactors
        )
        self.smc.open_multiple(
            self.smc.lines
        )
        time.sleep(1.0)

        # wait for ovens to reach temperature
        while not all(t > conditioning_oven_temperature for t in self.tm.get_temperature_multiple(self.tm.ovens)):
            time.sleep(1.0)

        # oven up how?

        time.sleep(preheat_iron_time)

    def get_average_pressure(self):
        pressures = []
        start_time = time.time()
        while time.time() - start_time < 10:
            pressures.append(self.keller.get_pressure_all())
            time.sleep(0.1)
        return np.mean(pressures, axis=0)

    def leak_test(self, leak_test_time=300, leak_test_limit=0.006):
        # open valves
        self.smc.open_multiple(
            self.smc.reactors
            + self.smc.lines
            + self.smc.vacuum
        )

        time.sleep(180)

        # close valves
        self.smc.close_multiple(
            self.smc.reactors
        )

        # get pressure difference
        pressure_before = self.get_average_pressure()
        time.sleep(leak_test_time)
        pressure_after = self.get_average_pressure()  
        pressure_diff = np.subtract(pressure_after, pressure_before).tolist()

        if not all(p < leak_test_limit for p in pressure_diff):
            print("Leak test failed.") # prompt user for retry

if __name__ == "__main__":
    smcdevnet = smc.SmcDevNet()
    smcdevnet.start()
    keller_sensor = keller.Keller()
    tm_sensor = tm.TMHardware()
    c = Conditioning(keller_sensor, tm_sensor, smcdevnet)
    c.oxidise_iron()
    smcdevnet.stop()

        




    