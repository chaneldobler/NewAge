import time
import tm, smc, keller
import json
import numpy as np

# the expected units are the standard units: bar, s, celsius

# conditioning thread

class Procedures:
    def __init__(self, keller_worker, tm_worker, smc_worker):
        # workers handle communication to hardware
        self.keller_worker = keller_worker
        self.tm_worker = tm_worker
        self.smc_worker = smc_worker
    
        # extract devices for indexing
        self.keller = self.keller_worker.device
        self.tm = self.tm_worker.device
        self.smc = self.smc_worker.device

        # store active idx
        self.active = None
        self.config = None

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
        if any(p is not None and p < threshold_pressure for p in pressures):
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
        start_time = time.time()
        while not all(t > conditioning_oven_temperature for t in temperatures):
            time.sleep(1.0)
            temperatures = self.tm_worker.cache
            # timeout
            if time.time() - start_time > 10:
                return

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
        # read config
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
        pressure_diff = np.subtract(pressure_after, pressure_before).tolist() # fix for nones
        if not all(p < difference_limit for p in pressure_diff):
            print("Leak test failed.") # prompt user for retry ...

    def h2_clean(self):
        # read config
        with open("conditioning_config.json", "r") as f:
            config = json.load(f)
        cfg = config["h2_clean"]
        num_cycles = cfg["number_of_cycles"]
        threshold_pressure = cfg["threshold_pressure"]
        clean_duration = cfg["clean_duration"]
        
        for _ in range(num_cycles):
            # set valves
            self.smc_worker.send_request("close_multiple", self.smc.vacuum)
            self.smc_worker.send_request("open_multiple", self.smc.h2)

            # wait for reactors to reach pressure
            pressures = self.smc_worker.cache
            while not any(p > threshold_pressure for p in pressures):
                time.sleep(1.0)
                pressures = self.smc_worker.cache

            # set valves
            self.smc_worker.send_request("close_multiple", self.smc.h2)
            time.sleep(clean_duration)
            self.smc_worker.send_request("close_multiple", self.smc.vacuum)
            time.sleep(60)

    def offset_correction(self):
        self.smc_worker.send_request(
            "open_multiple",
            self.smc.reactors 
            + self.smc.lines
            + self.smc.vac
            )

        time.sleep(20)

        return self.get_average_pressure() # what do i do with this? 

    def clean_trap(self):
        pass

    def clean_alf(self):
        pass

    def conditioning(self, idx):
        self.active = idx

        with open("conditioning_config.json", "r") as f:
            self.config = json.load(f)

        self.oxidise_iron()
        # evacuate reactors ? 
        self.leak_test()
        self.h2_clean()

    def load_trap(self):
        pass

    def load_reactors(self):
        # for reactor in active reactors

        # set valves
        self.smc_worker.send_request(
            "open_multiple",
            + self.smc.vacuum
            + self.smc.trap
        )
        self.smc_worker.send_request(
            "close_multiple",
            self.smc.lines
        )

        time.sleep(5)

        # open reactor and line

        time.sleep(10)

        self.smc_worker.send_request("close_multiple", self.smc.vacuum)
        self.tm_worker.send_request("set_temperature_multiple", self.tm.trap, 420)
        self.tm_worker.send_request("run_multiple", self.tm.trap)

        time.sleep(10)

        # close reactor and log pressure

        time.sleep(0.2)

        self.smc_worker.send_request("open_multiple", self.smc.vacuum)

        start_time = time.time()
        while True: # something
            if start_time - time.time() > 10:
                break
            
            self.smc_worker.send_request("close_multiple", self.smc.vacuum)
            time.sleep(0.2)
            # open reactor
            time.sleep(1)
            # close reactor
            time.sleep(0.2)
            self.smc_worker.send_request("open_multiple", self.smc.vacuum)
            time.sleep(1)

        # log pressure

        self.smc_worker.send_request("close_multiple", self.smc.vacuum)

        time.sleep(0.2)

        self.smc_worker.send_request(
            "open_multiple",
            self.smc.h2 # + reactor
        )

        # wait for pressure in reactor

        # close reactor

        while True: # something
            if start_time - time.time() > 10:
                break

            self.smc_worker.send_request("close_multiple", self.smc.h2)
            time.sleep(0.2)
            # open reactor
            time.sleep(1)
            # close valve
            time.sleep(0.2)
            self.smc_worker.send_request("open_multiple", self.smc.h2)
            time.sleep(1)

        # log pressure

        self.smc_worker.send_request("close_multiple", self.smc.h2)
        self.smc_worker.send_request(
            "open_multiple", 
            self.smc.lines
            + self.smc.vacuum
        )
        time.sleep(5)

    def reaction(self):
        self.tm_worker.send_request("set_temperature_multiple", self.tm.ovens, 580)

        # peltier coolers

        # wait for ovens to reach temperature
        temperatures = self.tm_worker.cache
        start_time = time.time()
        while not all(t > 560 for t in temperatures):
            time.sleep(1.0)
            temperatures = self.tm_worker.cache
            # timeout
            if time.time() - start_time > 10:
                self.tm_worker.send_request("stop_multiple", self.tm.ovens)
                self.smc_worker.send_request("close_all")
                return

        # oven up

        time.sleep(2)

        pressures = self.keller_worker.cache
        if any(p is not None and p > 0.18 for p in pressures):
            # user input if continue or not
            pass

    def remove_water(self):
        self.smc_worker.send_request(
            "open_multiple",
            self.smc.lines
            + self.smc.reactors
            + self.smc.vacuum
        )

        # off peltiers

        time.sleep(420)

        self.smc_worker.send_request(
            "close_multiple",
            self.smc.lines
            + self.smc.reactors
            + self.smc.vacuum
        )


        

