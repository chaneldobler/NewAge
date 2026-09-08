import time
import tm, smc, keller
import json
import numpy as np

# the expected units are the standard units: bar, s, celsius

# send requesst to just request

class Procedures:
    def __init__(self, parent):
        self.parent = parent
        self.schematic = self.parent.schematic

        # Device Communication
        self.keller_request = self.schematic.keller_worker.request
        self.tm_request = self.schematic.tm_worker.request
        self.smc_request = self.schematic.smc_worker.request

        self.reset()

    def reset(self):
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        # Valves
        self.valve_reactors = self.schematic.valve_reactors
        self.valve_lines = self.schematic.valve_lines
        self.valve_vacuum = self.schematic.valve_vacuum
        self.valve_trap = self.schematic.valve_trap
        self.valve_h2 = self.schematic.valve_h2
        self.valve_vortex = self.schematic.valve_vortex
        self.valve_lift = self.schematic.valve_lift

        # Reactors
        self.reactors = self.schematic.reactors

        # Heaters
        self.ovens = self.schematic.ovens
        self.trap = self.schematic.trap

        # Coolers
        self.peltiers = self.schematic.peltiers

    def update(self):
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        self.reactors = [r for r in self.schematic.reactors if r.active]

        # Close Both
        if not self.reactors:
            self.ovens = []
            self.peltiers = []
            self.valve_lines = []

        # Close Line 1
        elif all(6 <= r.id <= 10 for r in self.reactors):
            self.ovens = [self.schematic.ovens[1]]
            self.peltiers = [self.schematic.peltiers[1]]
            self.valve_lines = [self.schematic.valve_lines[1]]
            self.schematic.ovens[0].set_active(False)
            self.schematic.peltiers[0].set_active(False)
            
        # Close Line 2
        elif all(1 <= r.id <= 5 for r in self.reactors):
            self.ovens = [self.schematic.ovens[0]]
            self.peltiers = [self.schematic.peltiers[0]]
            self.valve_lines = [self.schematic.valve_lines[0]]
            self.schematic.ovens[1].set_active(False)
            self.schematic.peltiers[1].set_active(False)

        idx = [r.id for r in self.reactors if r.id <= 5] + [21 - r.id for r in self.reactors if r.id > 5]
        self.valve_reactors = [v for v in self.schematic.valves if v.id in idx]

    # ----- Conditioning -----
    def oxidise_iron(self):
        cfg = self.config["conditioning"]["iron oxidation"]
        temperature = cfg["oven conditioning temperature"]
        duration = cfg["iron preheating duration"]

        # Pressure Check
        if any(r.value is not None and r.value < 0.8 for r in self.reactors):
            print("Error: Pressure below threshold. Iron oxidation process stopped.")
            return False

        # Set and Run Ovens
        if temperature > 650:
            print("Error: Conditioning temperature unsafe. Iron oxidation process stopped.")
            return False
        for o in self.ovens:
            self.tm_request("set_temperature", o.id, temperature)
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
        while any(o.value is not None and o.value < temperature for o in self.ovens):
            time.sleep(1.0)
            if not self.parent.running:
                return False

        # Lift Samples
        self.smc_request(
            "set",
            [self.valve_lift.id],
            1
        )

        end_time = time.time() + duration
        while time.time() < end_time:
            time.sleep(1)
            # interrupt

    def get_average_pressure(self):
        pressures = [] * len(self.reactors)
        start_time = time.time()
        while time.time() - start_time < 10:
            for i, p in enumerate(self.reactors):
                if p.value is not None:
                    pressures[i] += p.value / 10
                else:
                    pressures[i] = None
            time.sleep(1)
        return pressures

    def leak_test(self):
        cfg = self.config["conditioning"]["leak test"]
        duration = cfg["leak test duration"]
        limit = cfg["leak test limit"]

        # Open Valves
        self.smc_request(
            "set",
            self.valve_reactors
            + self.valve_lines
            + self.valve_vacuum,
            1
        )

        time.sleep(180)

        # Close Valves
        self.smc_request(
            "set",
            self.valve_reactors,
            0
        )

        # Pressure Difference
        pressure_before = self.get_average_pressure()
        time.sleep(duration)
        pressure_after = self.get_average_pressure()  
        pressure_difference = [
            abs(pressure_after[i] - pressure_before[i]) \
            if pressure_after[i] is not None and pressure_before[i] is not None \
            else None for i in range(len(pressure_before))
        ] 
        if any(p is not None and p > limit for p in pressure_difference):
            print("Leak test failed.") # prompt user for retry ...

    def correct_offset(self):
        # Open Valves
        self.smc_request(
            "set",
            self.valve_reactors 
            + self.valve_lines
            + self.valve_vacuum,
            1
        )

        time.sleep(20)

        # Set Offset
        avg = self.get_average_pressure()
        for i, r in self.reactors:
            if i < len(avg):
                r.offset = avg[i]

    def h2_clean(self):
        cfg = self.config["conditioning"]["h2 test"]
        repetitions = cfg["h2 cycle repetitions"]  
        duration = cfg["h2 cycle duration"]
        
        for _ in range(repetitions):
            # Set Valves
            self.smc_request("set", self.valve_vacuum, 0)
            self.smc_request("set", self.valve_h2, 1)

            # Vacuum
            while all(r.value is not None and r.value < 0.8 for r in self.reactors):
                time.sleep(1.0)
                if not self.parent.running:
                    return False

            # Set Valves
            self.smc_request("set", self.valve_h2, 0)
            time.sleep(duration)
            self.smc_request("set", self.valve_vacuum, 1)
            time.sleep(60)

    def clean_trap(self):
        self.smc_request("set", self.valve_vacuum, 0)
        
        # open switch

        # wait trap clean time 60s

        # close switch

        pass

    def conditioning(self):
        self.update()
        self.oxidise_iron()
        self.leak_test()
        self.correct_offset()
        self.h2_clean()
        self.clean_trap()

    # ----- Sample -----
    def load_trap(self):
        # Vortex Cooler
        self.smc_request("set", self.valve_vortex, 1)

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


        

