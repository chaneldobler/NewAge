import time
import tm, smc, keller
import json
import numpy as np
import worker
import tcpip

# the expected units are the standard units: bar, s, celsius

# status: 0 = finished, 1 = stopped, 2 = failed, 3 = prompt

# TODO: Oven heating/ Valves reset after function?

class Procedures:
    def __init__(self, parent):
        self.parent = parent
        self.running = False

        self.tcpip = tcpip.TcpIp()
        self.schematic = self.parent.schematic

        self.smc_device = self.parent.smc_device 
        self.keller_device = self.parent.keller_device
        self.tm_device = self.parent.tm_device
        self.peltier_device = self.parent.peltier_device

        self.procedures_worker = worker.Worker()
        self.procedures_worker.start()

        self.reset()

    def start(self):
        self.update()
        self.running = True

    def stop(self):
        self.procedures_worker.clear()
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

        # Close Both Lines
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

    def evacuate_reactors(self, duration):

        self.smc_device.set([self.valve_trap.id, self.valve_h2.id], 0)
        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_lines + self.valve_reactors], 1)

        status = self.wait(duration)
        if status:
            return status

        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_lines + self.valve_reactors], 0)

        return 0

    def start_heaters(self, heaters, temperature):
        self.tm_device.set([h.id for h in heaters], temperature)
        self.tm_device.start([h.id for h in heaters])
        for o in heaters:
            o.set_running(True)    

    def stop_heaters(self, heaters):
        self.tm_device.stop([h.id for h in heaters])
        for o in heaters:
            o.set_running(False)

    def set_peltiers(self, running):
        self.peltier_device.set([p.id for p in self.peltiers], running)
        for p in self.peltiers:
            p.set_running(running)        

    # ----- Procedures -----
    def oxidize_iron(self):
        message = "Oxidize Iron"

        if any(r.value is not None and r.get_value() < 0.8 for r in self.reactors):
            return 2, message

        cfg = self.config["Oxidize Iron"]["Configurations"]
        temperature = cfg["Conditioning Temperature"]["Value"]
        duration = cfg["Iron Preheating Duration"]["Value"]

        if temperature > 650:
            return 2, message

        self.start_heaters(self.ovens, temperature)

        self.smc_device.set([self.valve_vacuum.id, self.valve_h2.id, self.valve_trap.id] \
            + [v.id for v in self.valve_reactors], 0)
        # self.smc_device.set([v.id for v in self.valve_lines], 1)

        while any(o.value is not None and o.value < temperature for o in self.ovens):
            if not self.running:
                return 1, message
            time.sleep(1.0)

        self.smc_device.set([self.valve_lift.id], 1)

        status = self.wait(duration)
        if status:
            return 1, message    

        self.smc_device.set([self.valve_lift.id], 0)

        # self.smc_device.set([self.valve_lift.id] + [v.id for v in self.valve_lines], 0)

        return 0, message

    def clean_trap(self):
        message = "Clean Trap"

        cfg = self.config["Clean Trap"]["Configurations"]
        duration = cfg["Clean Trap Duration"]["Value"]
        temperature = cfg["Clean Trap Temperature"]["Value"]
        temperature_low = cfg["Trap Cooling Temperature"]["Value"]

        if temperature > 550:
            return 2, message

        self.smc_device.set([self.valve_trap.id], 0)
        self.smc_device.set([self.valve_he.id], 1)
        
        status = self.wait(duration)
        if status:
            return status, message

        self.smc_device.set([self.valve_he.id], 0)
        
        self.start_heaters([self.trap], temperature)

        while self.trap.value is not None and self.trap.value < temperature:
            if not self.running:
                return 1, message
            time.sleep(1)

        status = self.wait(duration)
        if status:
            return status, message

        self.stop_heaters([self.trap])

        self.smc_device.set([self.valve_vortex.id], 1)

        while self.trap.value is not None and self.trap.value > temperature_low:
            if not self.running:
                return 1, message
            time.sleep(1)

        self.smc_device.set([self.valve_vortex.id], 0)

        return 0, message

    def leak_test(self):
        message = "Leak Test"

        cfg = self.config["Leak Test"]["Configurations"]
        duration = cfg["Leak Test Duration"]["Value"]
        limit = cfg["Pressure Leak Limit"]["Value"]

        status = self.evacuate_reactors(30)
        if status:
            return status, message

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
            return 2, message

        return 0, message

    def h2_cleaning(self):
        message = "H2 Cleaning"

        cfg = self.config["H2 Cleaning"]["Configurations"]
        repetitions = cfg["H2 Cycle Repetitions"]["Value"]
        duration = cfg["H2 Cycle Duration"]["Value"]

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

        self.smc_device.set([self.valve_vacuum.id], 1)
        self.smc_device.set([self.valve_lift.id, self.valve_trap.id], 0)

        return 0, message

    def correct_offset(self):
        message = "Correct Offset"

        self.smc_device.set([self.valve_vacuum.id] \
            + [v.id for v in self.valve_reactors + self.valve_lines], 1)

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
        cfg = self.config["Iterate Reactors"]["Configurations"]

        vacuum_duration = cfg["Trap Vacuum Duration"]["Value"]
        release_duration = cfg["Trap Release Duration"]["Value"]
        temperature = cfg["Trap Heating Temperature"]["Value"]
        pressure = cfg["CO2 Pressure"]["Value"]

        if temperature > 550:
            return 2

        self.set_peltiers(0)

        self.smc_device.set([self.valve_h2.id, self.valve_he.id] \
            + [v.id for v in self.valve_reactors], 0)
        self.smc_device.set([v.id for v in self.valve_lines] \
            + [reactor.id, self.valve_vacuum.id, self.valve_trap.id], 1)

        status = self.wait(vacuum_duration)
        if status:
            return status   

        self.smc_device.set([self.valve_vacuum.id], 0)

        self.start_heaters([self.trap], temperature)

        while self.trap.value is not None and self.trap.value < temperature:
            if not self.running:
                return 1
            time.sleep(1)

        status = self.wait(release_duration)
        if status:
            return status         

        self.smc_device.set([self.valve_trap.id, reactor.id], 0)
        self.smc_device.set([self.valve_he.id], 1)
        
        status = self.wait(60)
        if status:
            return status

        self.smc_device.set([self.valve_he.id], 0)

        while reactor.value is not None and reactor.get_value() > 100: # TODO: Repeat until (pressure_reactor_xx/pressure_calib) < trap_max_c: 
            if not self.running:
                return 1
            self.smc_device.set([self.valve_vacuum.id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_vacuum.id], 0)
            self.smc_device.set([reactor.id], 1)
            time.sleep(1)
            self.smc_device.set([reactor.id], 0)

        self.smc_device.set([reactor.id, self.valve_h2.id], 1)

        while reactor.value is not None and reactor.get_value() > pressure-200:
            if not self.running:
                return 1

        while reactor.value is not None and reactor.get_value() > pressure:
            if not self.running:
                return 1
            self.smc_device.set([self.valve_h2.id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_h2.id], 0)
            self.smc_device.set([reactor.id], 1)
            time.sleep(1)
            self.smc_device.set([reactor.id], 0)       

        self.smc_device.set([self.valve_vacuum.id], 1) 

        return 0

    def burn_sample(self, name):
        tcpip.start()

        while tcpip.get_status().split()[3] != "RUN":
            if not self.running:
                tcpip.sleep()
                return 1
            time.sleep(1)       

        if name.split()[0].lower() != "runin":

            tcpip.trap_on()

            while tcpip.trap_status().split()[2] != "10":
                if not self.running:
                    tcpip.trap_off()
                    tcpip.sleep()
                    return 1
                time.sleep(1)

            self.smc_device.set([self.valve_he.id], 1)

            while tcpip.trap_status().split()[2] != "15":
                if not self.running:
                    tcpip.trap_off()
                    tcpip.sleep()
                    return 1
                time.sleep(1)

            self.smc_device.set([self.valve_he.id], 0)

            tcpip.trap_off()

            c, n = tcpip.get_c(), tcpip.get_n()

        return 0

    def iterate_reactors(self):
        message = "Iterate Reactors"

        cfg = self.config["Iterate Reactors"]["Configurations"]
        temperature_low = cfg["Trap Cooling Temperature"]["Value"]

        for reactor in self.reactors:

            while tcpip.get_status() != "STS READY":
                if not self.running:
                    return 1
                time.sleep(1)

            index, name, weight = tcpip.get_index(), tcpip.get_name(), tcpip.get_weight()

            self.smc_device.set([self.valve_vortex.id], 1)

            while self.trap.value is not None and self.trap.value > temperature_low:
                if not self.running:
                    return 1, message

            self.smc_device.set([self.valve_vortex.id], 0)

            if name.split()[0].lower() != "first":

                if name.split()[0].lower() != "pre":

                        status = self.load_reactor(reactor)
                        if status:
                            return status, message

                        status = self.burn_sample(name)
                        if status:
                            return status, message

                status, _ = self.clean_trap()
                if status:
                    return status, message
                

    def reaction(self):
        message = "Reaction"

        cfg = self.config["Reaction"]["Configurations"]
        duration = cfg["Reaction Duration"]["Value"]
        limit = cfg["Pressure End Limit"]["Value"]

        self.start_heaters(self.ovens, 580)

        self.set_peltiers(1)

        while any(o.value is not None and o.value < 580 for o in self.ovens):
            if not self.running:
                return 1, message
            time.sleep(1)

        self.smc_device.set([self.valve_lift.id], 1)

        status = self.wait(duration)
        if status:
            return status, message

        self.smc_device.set([self.valve_lift.id], 0)

        self.stop_heaters(self.ovens)

        if any(r.get_value() is not None and r.get_value() > limit for r in self.reactors):
            return 2, message

        return 0, message

    def remove_water(self): 
        message = "Remove Water"

        cfg = self.config["Remove Water"]["Configurations"]
        duration = cfg["Remove Water Duration"]["Value"]

        self.set_peltiers(0)

        status = self.evacuate_reactors(duration)
        if status:
            return status, message

        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_lines + self.valve_reactors], 0)

        return 0, message

    def closeEvent(self, event):
        self.running = False
        self.procedures_worker.clear()
        self.procedures_worker.stop()

        event.accept()
        

