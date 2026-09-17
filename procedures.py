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
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        self.running = False
        self.pause = False # TODO prompt
        self.funcs = []

        self.tcpip = tcpip.TcpIp()

        self.smc_device = self.parent.smc_device 
        self.keller_device = self.parent.keller_device
        self.tm_device = self.parent.tm_device
        self.peltier_device = self.parent.peltier_device

        self.procedures_worker = worker.Worker()
        self.procedures_worker.begin.connect(self.parent.set_running)
        # self.procedures_worker.prompt.connect(self.parent.set_text)
        self.procedures_worker.end.connect(self.parent.set_stopped)
        self.procedures_worker.start()

        self.schematic = self.parent.schematic

        # Valves
        self.valve_reactors = self.schematic.valve_reactors
        self.valve_lines = self.schematic.valve_lines
        self.valve_vacuum = self.schematic.valve_vacuum
        self.valve_trap = self.schematic.valve_trap
        self.valve_h2 = self.schematic.valve_h2
        self.valve_vortex = self.schematic.valve_vortex
        self.valve_lift = self.schematic.valve_lift
        self.valve_sampling = self.schematic.valve_sampling

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

    def get_procedures(self, name=None):
        procedures = []
        if name is None:
            for funcs in self.config.values():
                for f in funcs:
                    procedures.append(f)
        elif name in self.config.keys():
            for f in self.config[name]:
                procedures.append(f)
        return procedures

    def start(self, name=None):
        self.update()
        self.running = True
        self.funcs = self.get_procedures(name)
        for func in self.funcs:
            f = getattr(self, func.lower().replace(" ", "_"))
            if f is not None:
                self.procedures_worker.request(f)

    def stop(self):
        self.procedures_worker.clear()
        self.running = False

    # ----- Helpers -----
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

    # ----- Procedures -----
    def oxidize_iron(self):
        message = "Oxidize Iron"

        cfg = self.config["Conditioning"]["Oxidize Iron"]
        temperature = cfg["Conditioning Temperature"]["Value"]
        duration = cfg["Iron Preheating Duration"]["Value"]

        if any(r.value is not None and r.get_value() < 0.8 for r in self.reactors):
            self.procedures_worker.end.emit(message, "Pressure too low.")
            return

        if temperature > 650:
            self.procedures_worker.end.emit(message, "Oven temperature set too high.") # TODO prompts

        self.procedures_worker.begin.emit(message) # TODO start when conditions met

        self.smc_device.set([v.id for v in self.valve_lines], 1)

        self.start_heaters(self.ovens, temperature)

        while any(o.value is not None and o.value < temperature for o in self.ovens):
            if not self.running:
                self.procedures_worker.end.emit(message, "Stopped.")
                return 
            time.sleep(1.0)

        self.smc_device.set([self.valve_lift.id], 1)

        status = self.wait(duration)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 

        self.procedures_worker.end.emit(message, "")
        return

    def clean_trap(self):
        message = "Clean Trap"

        cfg = self.config["Conditioning"]["Clean Trap"]
        duration = cfg["Clean Trap Duration"]["Value"]
        temperature = cfg["Clean Trap Temperature"]["Value"]
        temperature_low = cfg["Trap Cooling Temperature"]["Value"]

        if temperature > 550:
            self.procedures_worker.end.emit(message, "Trap temperature set too high.")
            return

        self.procedures_worker.begin.emit(message)

        self.smc_device.set([self.valve_sampling.id], 1)
        
        status = self.wait(duration)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 

        self.smc_device.set([self.valve_sampling.id], 0)
        
        # self.start_heaters([self.trap], temperature)

        # while self.trap.value is not None and self.trap.value < temperature:
        #     if not self.running:
        #         self.procedures_worker.end.emit(message, "Stopped.")
        #         return 
        #     time.sleep(1)

        # status = self.wait(duration)
        # if status:
        #     self.procedures_worker.end.emit(message, "Stopped.")
        #     return 

        # self.stop_heaters([self.trap])

        # self.smc_device.set([self.valve_vortex.id], 1)

        # while self.trap.value is not None and self.trap.value > temperature_low:
        #     if not self.running:
        #         self.procedures_worker.end.emit(message, "Stopped.")
        #         return 
        #     time.sleep(1)

        # self.smc_device.set([self.valve_vortex.id], 0)

        self.procedures_worker.end.emit(message, "")
        return 

    def leak_test(self):
        message = "Leak Test"

        cfg = self.config["Conditioning"]["Leak Test"]
        duration = cfg["Leak Test Duration"]["Value"]
        limit = cfg["Pressure Leak Limit"]["Value"]

        self.procedures_worker.begin.emit(message)

        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 1)

        status = self.wait(180)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 

        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 0)

        start = self.get_average_pressure()
        if start == -1:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 
        
        status = self.wait(duration)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 
        
        end = self.get_average_pressure()  
        if end == -1:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 

        result = [
            abs(start[i] - end[i]) \
            if start[i] is not None and end[i] is not None \
            else None for i in range(len(self.reactors))
        ] 

        if any(p is not None and p > limit for p in result):
            self.procedures_worker.end.emit(message, "Pressure above limit.")
            return 

        self.procedures_worker.end.emit(message, "")
        return 

    def h2_cleaning(self):
        message = "H2 Cleaning"

        cfg = self.config["Conditioning"]["H2 Cleaning"]
        repetitions = cfg["H2 Cycle Repetitions"]["Value"]
        duration = cfg["H2 Cycle Duration"]["Value"]

        self.procedures_worker.begin.emit(message)
        
        for _ in range(repetitions):
            self.smc_device.set([self.valve_h2.id], 1)

            while all(r.get_value() is not None and r.value < 0.8 for r in self.reactors):
                if not self.running:
                    self.procedures_worker.end.emit(message, "Stopped.")
                    return 
                time.sleep(1.0)

            self.smc_device.set([self.valve_h2.id], 0)

            status = self.wait(duration)
            if status:
                self.procedures_worker.end.emit(message, "Stopped.")
                return 

        return 0, message

    def correct_offset(self):
        message = "Correct Offset"

        self.procedures_worker.begin.emit(message)

        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 1)

        status = self.wait(20)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 

        offsets = self.get_average_pressure()
        if offsets == -1:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 
        
        for i, r in enumerate(self.reactors):
            if i < len(offsets):
                r.offset = offsets[i]

        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 0)

        self.procedures_worker.end.emit(message, "")
        return 

    def load_reactor(self, reactor): # TODO double check this
        message = "Load Reactor"

        cfg = self.config["Load Samples"]["Load Samples"]
        vacuum_duration = cfg["Trap Vacuum Duration"]["Value"]
        release_duration = cfg["Trap Release Duration"]["Value"]
        temperature = cfg["Trap Heating Temperature"]["Value"]
        pressure = cfg["CO2 Pressure"]["Value"]

        if temperature > 550:
            self.procedures_worker.end.emit(message, "Trap temperature set too high.")
            return

        self.procedures_worker.begin.emit(message)

        self.smc_device.set([self.valve_vacuum.id, self.valve_trap.id], 1)

        status = self.wait(5)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return

        self.smc_device.set([reactor.id], 1)

        status = self.wait(vacuum_duration)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return

        self.smc_device.set([self.valve_vacuum.id], 0)

        self.start_heaters([self.trap], temperature)

        while self.trap.value is not None and self.trap.value < temperature:
            if not self.running:
                self.procedures_worker.end.emit(message, "Stopped.")
                return
            time.sleep(1)

        status = self.wait(release_duration)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return      

        self.smc_device.set([reactor.id, self.valve_trap], 0)

        pressure_CO2 = self.get_average_pressure()

        while reactor.value is not None and reactor.get_value() > 100: # TODO: Repeat until (pressure_reactor_xx/pressure_calib) < trap_max_c: 
            if not self.running:
                self.procedures_worker.end.emit(message, "Stopped.")
                return
            self.smc_device.set([self.valve_vacuum.id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_vacuum.id], 0)
            self.smc_device.set([reactor.id], 1)
            time.sleep(1)
            self.smc_device.set([reactor.id], 0)

        pressure_CO2_final = self.get_average_pressure()

        self.smc_device.set([reactor.id, self.valve_h2.id], 1)

        while reactor.value is not None and reactor.get_value() > pressure-200:
            if not self.running:
                self.procedures_worker.end.emit(message, "Stopped.")
                return

        self.smc_device.set([reactor.id, self.valve_h2.id], 0)

        while reactor.value is not None and reactor.get_value() > pressure:
            if not self.running:
                return 1
            self.smc_device.set([self.valve_h2.id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_h2.id], 0)
            self.smc_device.set([reactor.id], 1)
            time.sleep(1)
            self.smc_device.set([reactor.id], 0)       

        pressure_H2 = self.get_average_pressure()

        self.procedures_worker.end.emit(message, "")
        return

    def sampling(self, name, index): # TODO double check runin
        message = "Sampling"

        self.procedures_worker.begin.emit(message)

        self.tcpip.start()

        while self.tcpip.get_status().split()[3] != "RUN":
            if not self.running:
                self.procedures_worker.end.emit(message, "Stopped.")
                return
            time.sleep(1)       

        if name.split()[0].lower() != "runin":

            self.tcpip.trap_on()

            while self.tcpip.get_process_status().split()[2] != "10":
                if not self.running:
                    self.tcpip.stop_processing()
                    self.procedures_worker.end.emit(message, "Stopped.")
                    return
                time.sleep(1)

            self.smc_device.set([self.valve_sampling.id], 1)

            while self.tcpip.get_process_status().split()[2] != "15":
                if not self.running:
                    self.tcpip.stop_processing()
                    self.procedures_worker.end.emit(message, "Stopped.")
                    return
                time.sleep(1)

            self.smc_device.set([self.valve_sampling.id], 0)

            self.tcpip.stop_processing()

            c, n = self.tcpip.get_c(index), self.tcpip.get_n(index)

        self.procedures_worker.end.emit(message, "")
        return

    def load_samples(self):
        message = "Load Samples"

        cfg = self.config["Load Samples"]["Load Samples"]
        temperature_low = cfg["Trap Cooling Temperature"]["Value"]

        self.procedures_worker.begin.emit(message)

        for reactor in self.reactors:

            while self.tcpip.get_status() != "STS READY":
                if not self.running:
                    self.procedures_worker.end.emit(message, "Stopped.")
                    return
                time.sleep(1)

            index = self.tcpip.get_index()
            name, weight = self.tcpip.get_name(index), self.tcpip.get_weight(index)

            self.smc_device.set([self.valve_vortex.id], 1)

            while self.trap.value is not None and self.trap.value > temperature_low:
                if not self.running:
                    self.procedures_worker.end.emit(message, "Stopped.")
                    return 
                time.sleep(1)

            self.smc_device.set([self.valve_vortex.id], 0)

            if name.split()[0].lower() != "first": # TODO what does first do

                if name.split()[0].lower() != "pre":

                        status = self.sampling(name, index)
                        if status:
                            self.procedures_worker.end.emit(message, "Stopped.")
                            return 

                        status = self.load_reactor(reactor)
                        if status:
                            self.procedures_worker.end.emit(message, "Stopped.")
                            return 

                status, _ = self.clean_trap()
                if status:
                    self.procedures_worker.end.emit(message, "Stopped.")
                    return 

        # TODO send EA to sleep?

        self.procedures_worker.end.emit(message, "")
        return 
        
    def reaction(self):
        message = "Reaction"

        cfg = self.config["Reaction"]["Reaction"]
        duration = cfg["Reaction Duration"]["Value"]
        limit = cfg["Pressure End Limit"]["Value"]

        self.procedures_worker.begin.emit(message)

        self.set_peltiers(1)

        self.start_heaters(self.ovens, 580)

        while any(o.value is not None and o.value < 580 for o in self.ovens):
            if not self.running:
                self.procedures_worker.end.emit(message, "Stopped.")
                return 
            time.sleep(1)

        self.smc_device.set([self.valve_lift.id], 1)

        status = self.wait(duration)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 

        self.smc_device.set([self.valve_lift.id], 0)

        self.stop_heaters(self.ovens)

        self.set_peltiers(0)

        if any(r.get_value() is not None and r.get_value() > limit for r in self.reactors):
            self.procedures_worker.end.emit(message, "Pressure above limit.")
            return 

        self.procedures_worker.end.emit(message, "")
        return 

    def remove_water(self): 
        message = "Remove Water"

        cfg = self.config["Reaction"]["Remove Water"]
        duration = cfg["Remove Water Duration"]["Value"]

        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 1)

        status = self.wait(duration)
        if status:
            self.procedures_worker.end.emit(message, "Stopped.")
            return 

        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors + self.valve_lines], 0)

        self.procedures_worker.end.emit(message, "")
        return 

    def closeEvent(self, event):
        self.running = False
        self.procedures_worker.clear()
        self.procedures_worker.stop()

        event.accept()
        

