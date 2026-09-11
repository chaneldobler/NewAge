import time
import tm, smc, keller
import json
import numpy as np
import worker

# the expected units are the standard units: bar, s, celsius

# status: 0 = finished, 1 = stopped, 2 = failed, 3 = prompt

# TODO: Oven heating/ Valves reset after function?

class Procedures:
    def __init__(self, parent):
        self.parent = parent
        self.running = False
        self.schematic = self.parent.schematic

        self.smc_device = self.parent.smc_device 
        self.keller_device = self.parent.keller_device
        self.tm_device = self.parent.tm_device
        self.peltier_device = self.parent.peltier_device

        self.procedures_worker = worker.Worker()
        self.procedures_worker.start()

        self.reset()

    def start(self):
        self.running = True
        self.procedures_worker.request(self.run)

    def run(self):
        self.update()

        funcs = [self.oxidize_iron, self.clean_trap, self.leak_test, self.h2_clean, self.correct_offset]

        for f in funcs:
            status, message = f()
            if status:
                return status, message

    def stop(self):
        self.running = False

    # ----- Setup -----
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

    # ----- Helpers -----
    def wait(self, duration):
        end_time = time.time() + duration
        while time.time() < end_time:
            if not self.running:
                return 1
            time.sleep(1)
        return 0

    def get_average_pressure(self):
        pressures = [0.0] * len(self.reactors)

        duration = 10
        end_time = time.time() + duration
        while time.time() < end_time:
            if not self.running:
                return -1
            
            for i, r in enumerate(self.reactors):
                if r.value is not None:
                    pressures[i] += r.get_value() / duration
                else:
                    pressures[i] = None
            time.sleep(1)
        return pressures

    def evacuate_reactors(self):

        self.smc_device.set([self.valve_trap.id, self.valve_h2.id], 0)
        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_lines + self.valve_reactors], 1)

        return self.wait(120)

    # ----- Procedures -----
    def oxidize_iron(self):
        message = "oxidize iron"

        if any(r.value is not None and r.get_value() < 0.8 for r in self.reactors):
            return 2, message + " pressure too high"

        cfg = self.config["oxidize iron"]
        temperature = cfg["oven conditioning temperature"]
        duration = cfg["iron preheating duration"]

        if temperature > 650:
            return 2, message + " temperature too high"

        self.tm_device.set([o.id for o in self.ovens], temperature)
        self.tm_device.start([o.id for o in self.ovens])
        for o in self.ovens:
            o.set_running(True)

        self.smc_device.set([self.valve_vacuum.id, self.valve_h2.id, self.valve_trap.id] \
            + [v.id for v in self.valve_reactors], 0)
        self.smc_device.set([v.id for v in self.valve_lines], 1)

        while any(o.value is not None and o.value < temperature for o in self.ovens):
            if not self.running:
                return 1, message
            time.sleep(1.0)

        self.smc_device.set([self.valve_lift.id], 1)

        status = self.wait(duration)
        if status:
            return status, message    

        self.smc_device.set([self.valve_lift.id], 0)

        return 0, message

    def clean_trap(self):
        message = "clean trap"

        duration = self.config["clean trap"]["clean trap duration"]

        self.smc_device.set([self.valve_vacuum.id], 0)
        self.smc_device.set([self.valve_he.id], 1)
        
        status = self.wait(duration)
        if status:
            return status, message

        self.smc_device.set([self.valve_vacuum.id], 1)
        self.smc_device.set([self.valve_he.id], 0)

        return 0, message

    def leak_test(self):
        message = "leak test"

        status = self.evacuate_reactors()
        if status:
            return status, message

        cfg = self.config["leak test"]
        duration = cfg["leak test duration"]
        limit = cfg["leak test limit"]

        self.smc_device.set([v.id for v in self.valve_reactors], 0)

        start = self.get_average_pressure()
        if start == -1:
            return 1, message
        
        status = self.wait(duration)
        if status:
            return status, message
        
        end = self.get_average_pressure()  
        if end == -1:
            return 1, message

        result = [
            abs(start[i] - end[i]) \
            if start[i] is not None and end[i] is not None \
            else None for i in range(len(self.reactors))
        ] 

        if any(p is not None and p > limit for p in result):
            return 3, message

        return 0, message

    def h2_clean(self):
        message = "h2 clean"

        cfg = self.config["h2 clean"]
        repetitions = cfg["h2 cycle repetitions"]  
        duration = cfg["h2 cycle duration"]

        self.smc_device.set([self.valve_lift.id], 1)
        self.smc_device.set([self.valve_vacuum.id], 0)  
        
        for _ in range(repetitions):
            self.smc_device.set([self.valve_h2.id], 1)

            while all(r.get_value() is not None and r.value < 0.8 for r in self.reactors):
                if not self.running:
                    return 1, message
                time.sleep(1.0)

            self.smc_device.set([self.valve_h2.id], 0)

            status = self.wait(duration)
            if status:
                return status, message

        status = self.wait(duration)
        if status:
            return status, message

        self.smc_device.set([self.valve_vacuum.id], 1)
        self.smc_device.set([self.valve_lift, self.valve_trap], 0)

        return 0, message

    def correct_offset(self):
        message = "correct offset"

        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors + self.valve_lines], 1)

        status = self.wait(20)
        if status:
            return status, message

        offsets = self.get_average_pressure()
        if offsets == -1:
            return 1, message
        
        for i, r in enumerate(self.reactors):
            if i < len(offsets):
                r.offset = offsets[i]

        return 0, message

    def load_reactor(self, reactor):
        message = "load_reactor"

        self.peltier_device.stop()

        self.smc_device.set([self.valve_h2.id] + [v.id for v in self.valve_reactors], 0)
        self.smc_device.set([self.valve_vacuum.id, self.valve_trap.id] + [v.id for v in self.valve_lines], 1)
        
        status = self.wait(5)
        if status:
            return status, message

        self.smc_device.set([reactor.id], 1)

        status = self.wait(10)
        if status:
            return status, message      

        self.smc_device.set([self.valve_vacuum.id, self.valve_trap.id], 0)
        self.tm_device.set([self.trap.id], 420)
        self.tm_device.start([self.trap.id])

        status = self.wait(10)
        if status:
            return status, message           

        self.smc_device.set([self.reactor.id], 0)

        while reactor.get_value() > 100:
            if not self.running:
                return 1, message
            self.smc_device.set([self.valve_vacuum.id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_vacuum.id], 0)
            self.smc_device.set([self.reactor.id], 1)
            time.sleep(1)
            self.smc_device.set([self.reactor.id], 0)

        self.smc_device.set([reactor.id, self.valve_h2.id], 1)

        while reactor.get_value() < 100:
            if not self.running:
                return 1, message

        self.smc_device.set([reactor.id, self.valve_h2.id], 1)

    def burn_sample(self, reactor):
        # Wait for STS ready

        # get index, name, weight

        # if name doesnt contain runin

            # self.load()

            # start EA

            # trap EA, c%, n%

        # else
            
            # ...
        
        pass

    # ----- Sample -----
    def load_trap(self):
        # Vortex Cooler
        self.smc_request("set", self.valve_vortex, 1)



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

    def closeEvent(self, event):
        self.running = False
        self.procedures_worker.stop()

        event.accept()
        

