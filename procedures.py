import time
import tm, smc, keller
import json
import numpy as np

# the expected units are the standard units: bar, s, celsius

# send requesst to just request

class Procedures:
    def __init__(self, schematic):
        self.schematic = schematic

        # Device Communication
        self.keller_request = self.schematic.keller_worker.request
        self.tm_request = self.schematic.tm_worker.request
        self.smc_request = self.schematic.smc_worker.request

        self.reset()

    def reset(self):
        with open("conditioning_config.json", "r") as f:
            self.config = json.load(f)

        # Valves
        self.valve_reactors = self.schematic.valve_reactors
        self.valve_lines = self.schematic.valve_lines
        self.valve_vacuum = self.schematic.valve_vacuum
        self.valve_trap = self.schematic.valve_trap
        self.valve_h2 = self.schematic.valve_h2
        self.valve_lift = self.schematic.valve_lift

        # Reactors
        self.reactors = self.schematic.reactors

        # Heaters
        self.ovens = self.schematic.ovens
        self.trap = self.schematic.trap

        # Coolers
        self.peltiers = self.schematic.peltiers

    def update(self):
        with open("conditioning_config.json", "r") as f:
            self.config = json.load(f)

        self.reactors = [r for r in self.schematic.reactors if r.active]

        # Close Line 1
        if all(id not in range(5) for id in self.reactors):
            self.ovens = self.schematic.ovens[1]
            self.peltiers = self.schematic.peltiers[1]
            self.lines = self.schematic.valve_lines[1]

        # Close Line 2
        if all(id not in range(5, 10) for id in self.reactors):
            self.ovens = self.schematic.ovens[0]
            self.peltiers = self.schematic.peltiers[0]
            self.lines = self.schematic.valve_lines[0]
        idx = [r.id for r in self.reactors if r.id <= 5] + [21 - r.id for r in self.reactors if r.id > 5]

        self.valve_reactors = [v for v in self.schematic.valves if v.id in idx]

    def oxidise_iron(self):
        self.update()
        cfg = self.config["iron_oxidation"]

        # Pressure Check
        if any(r.value is not None and r.value < cfg["threshold_pressure"] for r in self.reactors):
            print("Error: Pressure below threshold. Oxidation process stopped.")
            return False

        # Set and Run Ovens
        if cfg["conditioning_oven_temperature"] > 650:
            print("Error: Conditioning temperature unsafe. Oxidation process stopped.")
        for o in self.ovens:
            self.tm_request("set_temperature", o.id, cfg["conditioning_oven_temperature"])
            self.tm_request("run", o.id)
            o.set_running(True)

        # Set Valves
        self.smc_request(
            "set",
            [self.valve_vacuum.id] 
            + [self.valve_h2.id] 
            + [self.valve_trap.id]
            + [v.id for v in self.valve_reactors],
            0
        )
        self.smc_request(
            "set",
            [v.id for v in self.valve_lines],
            1
        )
        time.sleep(1.0)

        # Heat Ovens
        start_time = time.time()
        while not all(o.value is not None and o.value > cfg["conditioning_oven_temperature"] for o in self.ovens):
            time.sleep(1.0)
            if time.time() - start_time > 100:
                return

        # Lift
        self.smc_request(
            "set",
            [self.valve_lift.id]
        )
        time.sleep(cfg["preheat_iron_duration"])

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


        

