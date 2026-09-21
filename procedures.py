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
        self.cooling = False
        # self.pause = False # TODO prompt
        self.procedures = []

        self.tcpip = tcpip.TcpIp()

        self.smc_device = self.parent.smc_device 
        self.keller_device = self.parent.keller_device
        self.tm_device = self.parent.tm_device
        self.peltier_device = self.parent.peltier_device

        self.reactors_worker = worker.Worker()
        self.reactors_worker.message.connect(self.parent.set_running)
        # self.reactors_worker.prompt.connect(self.parent.set_text)
        self.reactors_worker.start()

        self.separate_worker = worker.Worker()
        # self.separate_worker.message.connect(self.parent.set_running)
        # self.separate_worker.prompt.connect(self.parent.set_text)
        self.separate_worker.start()

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

    def get_procedures(self, stage=None):
        self.procedures = []
        if stage is None:
            for key in self.config.keys():
                self.procedures.append(key)
        elif stage in self.config.keys():
            self.procedures.append(stage)

    def get_active(self):
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

        idx = [r.id for r in self.reactors if r.id <= 5] + [21 - r.id for r in self.reactors if r.id > 5] # Could be better
        self.valve_reactors = [v for v in self.schematic.valves if v.id in idx]

    def start(self, stage=None):
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        self.get_active()
        self.get_procedures(stage)
        self.running = True

        for func in self.procedures:
            f = getattr(self, func.lower().replace(" ", "_"))
            if f is not None:
                self.reactors_worker.request(f)

    def stop(self):
        self.reactors_worker.clear()
        self.separate_worker.clear()

        self.running = False

    # ----- Helper Functions -----
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
                return -1
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

    # ----- Independent Procedures -----
    def process_runin(self):
        for _ in self.reactors:
            while self.tcpip.get_status() != "STS READY":
                if not self.running:
                    return
                time.sleep(1)

            index = self.tcpip.get_index()
            name = self.tcpip.get_name(index)

            if name.split()[0].lower() == "pre":
                self.tcpip.start()

    def cool_trap(self, temperature):
        while self.cooling:
            if not self.running:
                return
            if not self.valve_vortex.active and self.trap.value is not None and self.trap.value > temperature:
                self.smc_device.set([self.valve_vortex.id], 1)
            elif self.valve_vortex.active:
                self.smc_device.set([self.valve_vortex.id], 0)
            time.sleep(1)
        self.smc_device.set([self.valve_vortex.id], 0)

    def clean_trap(self, temperature, duration):
        self.start_heaters([self.trap], temperature)
        while self.trap.value is not None and self.trap.value < temperature:
            if not self.running:
                return
            time.sleep(1)
        self.stop_heaters([self.trap])

        self.smc_device.set([self.valve_sampling.id], 1)
        status = self.wait(duration)
        if status:
            return 
        self.smc_device.set([self.valve_sampling.id], 0)

    # ----- Conditioning Procedures ----- 
    def oxidize_iron(self, temperature, duration):
        self.smc_device.set([v.id for v in self.valve_lines], 1)
        self.start_heaters(self.ovens, temperature)
        while any(o.value is not None and o.value < temperature for o in self.ovens):
            if not self.running:
                return -1
            time.sleep(1.0)
        self.smc_device.set([self.valve_lift.id], 1)
        status = self.wait(duration)
        if status:
            return -1
        return 0

    def leak_test(self, duration, limit):
        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 1)
        status = self.wait(180)
        if status:
            return -1 
        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 0)
        start = self.get_average_pressure()
        if start == -1:
            return -1
        status = self.wait(duration)
        if status:
            return -1
        end = self.get_average_pressure()  
        if end == -1:
            return -1
        result = [
            abs(start[i] - end[i]) \
            if start[i] is not None and end[i] is not None \
            else None for i in range(len(self.reactors))
        ] 
        if any(p is not None and p > limit for p in result):
            self.parent.stop()
            return -1
        return 0

    def h2_cleaning(self, repetitions, duration):
        for _ in range(repetitions):
            self.smc_device.set([self.valve_h2.id], 1)
            while all(r.get_value() is not None and r.value < 0.8 for r in self.reactors):
                if not self.running:
                    return -1
                time.sleep(1.0)
            self.smc_device.set([self.valve_h2.id], 0)
            status = self.wait(duration)
            if status:
                return -1
            self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 1)
            status = self.wait(60)
            if status:
                return -1
            self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 0)
        return 0

    def correct_offset(self):
        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 1)
        status = self.wait(20)
        if status:
            return -1
        offsets = self.get_average_pressure()
        if offsets == -1:
            return -1
        for i, r in enumerate(self.reactors):
            if i < len(offsets):
                r.offset = offsets[i]
        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 0)
        return 0

    def conditioning(self):
        cfg = self.config["Conditioning"]
        cond_oven_temp = cfg["Conditioning Oven Temperature"]["Value"]
        preheat_iron_dur = cfg["Preheating Iron Duration"]["Value"]
        trap_heating_temp = cfg["Trap Heating Temperature"]["Value"]
        clean_trap_dur = cfg["Clean Trap Duration"]["Value"]
        leak_test_dur = cfg["Leak Test Duration"]["Value"]
        leak_press_limit = cfg["Leak Pressure Limit"]["Value"]
        h2_cycle_reps = cfg["H2 Cycle Repetitions"]["Value"]
        h2_cycle_dur = cfg["H2 Cycle Duration"]["Value"]

        if any(r.value is not None and r.get_value() < 0.8 for r in self.reactors):
            self.parent.stop()
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return
        if trap_heating_temp > 550:
            self.parent.stop()
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return
        if cond_oven_temp > 650:
            self.parent.stop()
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return

        self.reactors_worker.message.emit("Conditioning", "Started Oxidize Iron")
        status = self.oxidize_iron(cond_oven_temp, preheat_iron_dur)
        if status:
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return

        self.separate_worker.request(self.clean_trap, trap_heating_temp, clean_trap_dur)
        # self.separate_worker.request(self.process_runin)

        self.reactors_worker.message.emit("Conditioning", "Started Leak Test")
        status = self.leak_test(leak_test_dur, leak_press_limit)
        if status:
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return

        self.reactors_worker.message.emit("Conditioning", "Started H2 Cleaning")
        status = self.h2_cleaning(h2_cycle_reps, h2_cycle_dur)
        if status:
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return

        self.reactors_worker.message.emit("Conditioning", "Started Correct Offset")
        status = self.correct_offset()
        if status:
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return

        self.reactors_worker.message.emit("Conditioning", "Completed")
        return

    # ----- Stage Load Samples -----
    def load_reactor(self, reactor, vacuum_duration, release_duration, temperature, scaling): # TODO double check this
        self.smc_device.set([self.valve_vacuum.id, self.valve_trap.id], 1)
        status = self.wait(5)
        if status:
            return -1
        self.smc_device.set(self.valve_reactors[reactor.id - 1].id, 1)
        status = self.wait(vacuum_duration)
        if status:
            return -1
        self.smc_device.set([self.valve_vacuum.id], 0)
        self.start_heaters([self.trap], temperature) # TODO when stop heating trap?
        while self.trap.value is not None and self.trap.value < temperature:
            if not self.running:
                return -1
            time.sleep(1)
        status = self.wait(release_duration)
        if status:
            return -1      
        self.smc_device.set([self.valve_reactors[reactor.id - 1].id, self.valve_trap], 0)

        pressure_CO2 = self.get_average_pressure()
        while reactor.value is not None and reactor.get_value() > 570: # TODO: Repeat until (pressure_reactor_xx/pressure_calib) < trap_max_c: 
            if not self.running:
                return -1
            self.smc_device.set([self.valve_vacuum.id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_vacuum.id], 0)
            self.smc_device.set([self.valve_reactors[reactor.id - 1].id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_reactors[reactor.id - 1].id], 0)
        pressure_CO2_final = self.get_average_pressure()

        self.smc_device.set([self.valve_reactors[reactor.id - 1].id, self.valve_h2.id], 1)
        while reactor.value is not None and reactor.get_value() > pressure_CO2_final*(scaling + 1)-200:
            if not self.running:
                return -1
        self.smc_device.set([self.valve_reactors[reactor.id - 1].id, self.valve_h2.id], 0)

        while reactor.value is not None and reactor.get_value() > pressure_CO2_final*(scaling + 1):
            if not self.running:
                return -1
            self.smc_device.set([self.valve_h2.id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_h2.id], 0)
            self.smc_device.set([self.valve_reactors[reactor.id - 1].id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_reactors[reactor.id - 1].id], 0)       
        pressure_H2 = self.get_average_pressure()
        return 0

    def sampling(self, index):
        self.tcpip.start()
        while self.tcpip.get_status().split()[3] != "RUN":
            if not self.running:
                return -1
            time.sleep(1)       

        self.tcpip.start_processing()
        while self.tcpip.get_process_status().split()[2] != "10":
            if not self.running:
                self.tcpip.stop_processing()
                return -1
            time.sleep(1)

        self.smc_device.set([self.valve_sampling.id], 1)
        while self.tcpip.get_process_status().split()[2] != "15":
            if not self.running:
                self.tcpip.stop_processing()
                return -1
            time.sleep(1)
        self.smc_device.set([self.valve_sampling.id], 0)
        self.tcpip.stop_processing()
        c, n = self.tcpip.get_c(index), self.tcpip.get_n(index)
        return 0

    def load_samples(self):
        cfg = self.config["Load Samples"]
        trap_vac_dur = cfg["Trap Vacuum Duration"]["Value"]
        trap_release_dur = cfg["Trap Release Duration"]["Value"]
        trap_preheating_temp = cfg["Trap Preheating Temperature"]["Value"]
        trap_heating_temp = cfg["Trap Heating Temperature"]["Value"]
        clean_trap_dur = cfg["Clean Trap Duration"]["Value"]
        trap_cooling_temp = cfg["Trap Cooling Temperature"]["Value"]
        co2_press_scaling = cfg["CO2 Pressure Scaling"]["Value"]

        if trap_heating_temp > 550:
            self.reactors_worker.message.emit("Load Samples", "Stopped")
            self.parent.stop()
            return

        self.reactors_worker.message.emit("Load Samples", "Running Load Samples")
        for reactor in self.reactors:
            while self.tcpip.get_status() != "STS READY":
                if not self.running:
                    self.reactors_worker.message.emit("Load Samples", "Stopped")
                    return
                time.sleep(1)
            index = self.tcpip.get_index()
            name, weight = self.tcpip.get_name(index), self.tcpip.get_weight(index)

            if name.split()[0].lower() == "pre":
                continue
            self.cooling = True
            self.separate_worker.request(self.cool_trap, trap_cooling_temp)
            self.reactors_worker.message.emit("Load Samples", "Running Sampling")
            status = self.sampling(index)
            if status:
                self.reactors_worker.message.emit("Load Samples", "Stopped")
                self.cooling = False
                return 
            self.cooling = False

            if name.split()[0].lower() != "pre": #TODO Double check pre
                self.reactors_worker.message.emit("Load Samples", "Running Load Reactor")
                status = self.load_reactor(reactor, trap_vac_dur, trap_release_dur, trap_heating_temp, co2_press_scaling)
                if status:
                    self.reactors_worker.message.emit("Load Samples", "Stopped")
                    return 

            if name.split()[0].lower() != "first": 
                self.reactors_worker.message.emit("Load Samples", "Running Clean Trap")
                status = self.clean_trap(trap_heating_temp, clean_trap_dur)
                if status:
                    self.reactors_worker.message.emit("Load Samples", "Stopped")
                    return 

        # send EA to sleep?

        self.reactors_worker.message.emit("Load Samples", "Completed")
        return 

    def remove_water(self, duration): 
        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 1)
        status = self.wait(duration)
        if status:
            return -1
        self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors + self.valve_lines], 0)
        self.set_peltiers(0)
        return 0
        
    def reaction(self):
        cfg = self.config["Reaction"]
        reaction_temp = cfg["Reaction Temperature"]["Value"]
        reaction_dur = cfg["Reaction Duration"]["Value"]
        end_press_limit = cfg["End Pressure Limit"]["Value"]
        water_removal_dur = cfg["Water Removal Duration"]["Value"]

        self.reactors_worker.message.emit("Reaction", "Running Reaction")
        self.set_peltiers(1)
        self.start_heaters(self.ovens, reaction_temp)
        while any(o.value is not None and o.value < reaction_temp for o in self.ovens):
            if not self.running:
                self.reactors_worker.message.emit("Reaction", "Reaction Stopped")
                return 
            time.sleep(1)
        self.smc_device.set([self.valve_lift.id], 1)
        end_time = time.time() + reaction_dur
        while time.time() < end_time:
            if not self.running:
                self.reactors_worker.message.emit("Reaction", "Reaction Stopped")
                return
            self.reactors_worker.message.emit("Reaction", "Reaction Time Left: " + str(int(end_time - time.time())))
            time.sleep(1)
        self.smc_device.set([self.valve_lift.id], 0)
        self.stop_heaters(self.ovens)
        if any(r.get_value() is not None and r.get_value() > end_press_limit for r in self.reactors):
            self.parent.stop()
            self.reactors_worker.message.emit("Reaction", "Remove Water Stopped")
            return 

        status = self.remove_water(water_removal_dur)
        if status:
            self.reactors_worker.message.emit("Reaction", "Remove Water Stopped")
            return
        self.reactors_worker.message.emit("Reaction", "Completed")
        return 

    def closeEvent(self, event):
        self.running = False

        self.reactors_worker.clear()
        self.separate_worker.clear()

        self.reactors_worker.stop()
        self.separate_worker.stop()

        event.accept()
        

