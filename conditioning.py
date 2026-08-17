import time
import tm, smc, keller
import json
import numpy as np

# the expected units are the standard units: bar, s, celsius

# conditioning thread

class Conditioning:
    def __init__(self, keller_worker, tm_worker, smc_worker):
        # workers handle communication to hardware
        self.keller_worker = keller_worker
        self.tm_worker = tm_worker
        self.smc_worker = smc_worker
    
        # extract devices for indexing
        self.keller = self.keller_worker.device
        self.tm = self.tm_worker.device
        self.smc = self.smc_worker.device

    def oxidise_iron(self):
        # read config
        with open("conditioning_config.json", "r") as f:
            config = json.load(f)
        cfg = config["iron_oxidation"]
        threshold_pressure = cfg["threshold_pressure"]
        conditioning_oven_temperature = cfg["conditioning_oven_temperature"]
        preheat_iron_duration = cfg["preheat_iron_duration"]

        # check pressures
        pressures = self.keller_worker.cache
        if not all(p > threshold_pressure for p in pressures):
            print("Error: Pressure is below threshold. Oxidation process stopped.")
            return False

        # set and run ovens
        self.tm_worker.send_request("set_temperature_multiple", self.tm.ovens, conditioning_oven_temperature)
        self.tm_worker.send_request("run_multiple", self.tm.ovens)

        # set valves
        self.smc_worker.send_request(
            "close_multiple",
            self.smc.vacuum 
            + self.smc.h2 
            + self.smc.trap 
            + self.smc.reactors
        )
        self.smc_worker.send_request(
            "open_multiple",
            self.smc.lines
        )
        time.sleep(1.0)

        # wait for ovens to reach temperature
        temperatures = self.tm_worker.cache
        while not all(t > conditioning_oven_temperature for t in temperatures):
            time.sleep(1.0)
            temperatures = self.tm_worker.cache

        # make device go up

        time.sleep(preheat_iron_duration)

    def get_average_pressure(self):
        pressures = []
        start_time = time.time()
        while time.time() - start_time < 10:
            pressures.append(self.keller_worker.cache)
            time.sleep(0.1)
        return np.mean(pressures, axis=0)

    def leak_test(self):
        with open("conditioning_config.json", "r") as f:
            config = json.load(f)
        cfg = config["leak_test"]
        test_duration = cfg["test_duration"]
        difference_limit = cfg["difference_limit"]

        # open valves
        self.smc_worker.send_request(
            "open_multiple",
            self.smc.reactors
            + self.smc.lines
            + self.smc.vacuum
        )

        time.sleep(180)

        # close valves
        self.smc_worker.send_request(
            "close_multiple",
            self.smc.reactors
        )

        # get pressure difference
        pressure_before = self.get_average_pressure()
        time.sleep(test_duration)
        pressure_after = self.get_average_pressure()  
        pressure_diff = np.subtract(pressure_after, pressure_before).tolist()
        if not all(p < difference_limit for p in pressure_diff):
            print("Leak test failed.") # prompt user for retry ...


        




    