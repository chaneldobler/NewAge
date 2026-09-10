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
        self.peltiers_request = self.schematic.peltiers_worker.request

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
        self.valve_he = self.schematic.valve_he

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

    def evacuate_reactors(self):
        self.smc_request("set", [self.valve_trap.id, self.valve_h2.id], 0)
        self.smc_request("set", [self.valve_vacuum.id] + [v.id for v in self.valve_lines + self.valve_reactors], 1)
        



    def oxidise_iron(self):
        print("oxidize iron")

        cfg = self.config["conditioning"]["iron oxidation"]
        temperature = cfg["oven conditioning temperature"]
        duration = cfg["iron preheating duration"]

        # Pressure Check
        if any(r.value is not None and r.value < 0.8 for r in self.reactors):
            return 1, "Pressure below threshold. Iron oxidation stopped."

        # Set and Run Ovens
        if temperature > 650:
            return 1, "Conditioning temperature unsafe. Iron oxidation stopped."
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

        # Heat Ovens
        while any(o.value is not None and o.value < temperature for o in self.ovens):
            if not self.parent.running:
                return 2, "Iron oxidation stopped."
            time.sleep(1.0)

        # Lift Samples
        self.smc_request(
            "set",
            [self.valve_lift.id],
            1
        )

        end_time = time.time() + duration
        while time.time() < end_time:
            if not self.parent.running:
                return 2, "Iron oxidation stopped."
            time.sleep(1)

        return 0, "Iron oxidation finished."

    def get_average_pressure(self):
        pressures = [0.0] * len(self.reactors)
        end_time = time.time() + 10
        while time.time() < end_time:
            if not self.parent.running:
                raise RuntimeError("Procedure aborted by user")
            for i, p in enumerate(self.reactors):
                if p.value is not None:
                    pressures[i] += p.value / 10
                else:
                    pressures[i] = None
            time.sleep(1)
        return pressures

    def leak_test(self):
        print("leak test")

        cfg = self.config["conditioning"]["leak test"]
        duration = cfg["leak test duration"]
        limit = cfg["leak test limit"]

        # Open Valves
        self.smc_request(
            "set",
            [v.id for v in self.valve_reactors]
            + [v.id for v in self.valve_lines]
            + [self.valve_vacuum.id],
            1
        )

        end_time = time.time() + 180
        while time.time() < end_time:
            if not self.parent.running:
                return 2, "Leak test stopped."
            time.sleep(1)

        # Close Valves
        self.smc_request(
            "set",
            [v.id for v in self.valve_reactors],
            0
        )

        # Pressure Difference
        pressure_before = self.get_average_pressure()

        end_time = time.time() + duration
        while time.time() < end_time:
            if not self.parent.running:
                return 2, "Leak test stopped."
            time.sleep(1)

        pressure_after = self.get_average_pressure()  

        pressure_difference = [
            abs(pressure_after[i] - pressure_before[i]) \
            if pressure_after[i] is not None and pressure_before[i] is not None \
            else None for i in range(len(pressure_before))
        ] 

        if any(p is not None and p > limit for p in pressure_difference):
            return 3, "Leak test failed."

        return 0, "Leak test successful."

    def correct_offset(self):
        print("correct offset")

        # Open Valves
        self.smc_request(
            "set",
            [v.id for v in self.valve_reactors] 
            + [v.id for v in self.valve_lines]
            + [self.valve_vacuum.id],
            1
        )

        end_time = time.time() + 20
        while time.time() < end_time:
            if not self.parent.running:
                return 2, "Offset correction stopped."
            time.sleep(1)

        # Set Offset
        avg = self.get_average_pressure()
        for i, r in enumerate(self.reactors):
            if i < len(avg):
                r.offset = avg[i]

        return 0, "Offset correction finished."

    def h2_clean(self):
        print("h2 clean")

        cfg = self.config["conditioning"]["h2 clean"]
        repetitions = cfg["h2 cycle repetitions"]  
        duration = cfg["h2 cycle duration"]
        
        for _ in range(repetitions):
            # Set Valves
            self.smc_request("set", [self.valve_vacuum.id], 0)
            self.smc_request("set", [self.valve_h2.id], 1)

            # Vacuum
            while all(r.value is not None and r.value < 0.8 for r in self.reactors):
                if not self.parent.running:
                    return 2, "H2 cleaning stopped."
                time.sleep(1.0)

            # Set Valves
            self.smc_request("set", [self.valve_h2.id], 0)

            end_time = time.time() + duration
            while time.time() < end_time:
                if not self.parent.running:
                    return 2, "H2 cleaning stopped."
                time.sleep(1)

            self.smc_request("set", [self.valve_vacuum.id], 1)

            end_time = time.time() + 60
            while time.time() < end_time:
                if not self.parent.running:
                    return 2, "H2 cleaning stopped."
                time.sleep(1)

            return 0, "H2 cleaning finished."

    def clean_trap(self):
        print("clean trap")

        self.smc_request("set", [self.valve_vacuum.id], 0)
        
        # open switch

        # wait trap clean time 60s

        # close switch

        return True

    def conditioning(self):
        functions = [
            self.update,
            self.oxidise_iron,
            self.leak_test,
            self.correct_offset,
            self.h2_clean,
            self.clean_trap
        ]

        for func in functions:
            status, message = func()
            if status:
                return status, message

        # read if continue and add sampling and reaction

        return 0,"Conditioning finished."

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

    # ----- Reacting -----
    def react(self):
        cfg = self.config["reacting"]["reaction"]
        duration = cfg["reaction duration"]
        limit = cfg["end pressure limit"]

        # Start Ovens
        for o in self.ovens:
            self.tm_request("set_temperature", o.id, 580)
            self.tm_request("run", o.id)
            o.set_running(True)

        # Start Coolers
        self.peltiers_request("set", [p.id for p in self.peltiers], 1)
        for p in self.peltiers:
            p.set_running(True)

        # Heat Ovens
        while any(o.value is not None and o.value < 560 for o in self.ovens):
            if not self.parent.running:
                return 2, "Reaction stopped."
            time.sleep(1)

        # Lift 
        self.smc_request("set", [self.valve_lift.id], 1)

        time_end = time.time() + duration
        while time.time() < time_end:
            if not self.parent.running:
                return 2, "Reaction stopped."
            time.sleep(1)

        # Lift 
        self.smc_request("set", [self.valve_lift.id], 0)

        # Stop ovens
        for o in self.ovens:
            self.tm_request("halt", o.id)
            o.set_running(False)

        # Pressure Check
        if any(r.value is not None and r.value > limit for r in self.reactors):
            return 3, "Pressure above threshold."

        return 0, "Reaction finished."

    def remove_water(self):
        cfg = self.config["reacting"]["remove water"]
        duration = cfg["water removal duration"]

        # Open Valves
        self.smc_request(
            "set",
            [v.id for v in self.valve_lines]
            + [v.id for v in self.valve_reactors]
            + [self.valve_vacuum.id],
            1
        )

        # Stop Coolers
        self.peltiers_request("set", [p.id for p in self.peltiers], 0)

        time_end = time.time() + duration
        while time.time() < time_end:
            if not self.parent.running:
                return 2, "Water removal stopped."
            time.sleep(1)

        # Close Valves
        self.smc_request(
            "set",
            [v.id for v in self.valve_lines]
            + [v.id for v in self.valve_reactors]
            + [self.valve_vacuum.id],
            0
        )

        return 0, "Water removal finished."

    def reacting(self):
        functions = [self.react, self.remove_water]

        for func in functions:
            status, message = func()
            if status:
                return status, message

        return 0, "Reaction finished."


        

