import time
import tm, smc, keller
import json
import numpy as np
import worker
import tcpip
import threading
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

# the expected units are the standard units: bar, s, celsius

# status: 0 = finished, 1 = stopped, 2 = failed, 3 = prompt

# TODO: Oven heating/ Valves reset after function?

class Procedures:
    def __init__(self, parent):
        self.parent = parent
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        self.running = False
        self.trap_cooling = False
        self.prompt_reply = None
        self.procedures = []

        self.tcpip = tcpip.TcpIp()

        self.smc_device = self.parent.smc_device 
        self.keller_device = self.parent.keller_device
        self.tm_device = self.parent.tm_device
        self.peltier_device = self.parent.peltier_device

        self.reactors_worker = worker.Worker()
        self.reactors_worker.message.connect(self.parent.set_running)
        self.reactors_worker.prompt.connect(self.parent.prompt)
        self.reactors_worker.start()

        self.separate_worker = worker.Worker()
        # self.separate_worker.prompt.connect(self.parent.set_text)
        self.separate_worker.start()

        self.schematic = self.parent.schematic
        self.table = self.parent.table

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

    def start(self, stages):
        if self.reactors_worker.requests.empty():
            with open("procedures_config.json", "r") as f:
                self.config = json.load(f)

            self.get_active()
            self.stages = stages
            self.running = True

            for func in self.stages:
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
        self.reactors_worker.message.emit("Separate", "Started Process Runin")
        for _ in self.reactors:
            while self.tcpip.get_status() != "STS READY":
                if not self.running:
                    self.reactors_worker.message.emit("Separate", "")
                    return
                time.sleep(1)

            index = int(self.tcpip.get_index().split()[1])
            name = self.tcpip.get_name(index)
            print(str(index) + " " + name)

            if name.split()[2].lower() == "runin":
                self.tcpip.start()

        self.reactors_worker.message.emit("Separate", "")

    def cool_trap(self, temperature):
        self.reactors_worker.message.emit("Separate", "Started Trap Cooling")
        while self.trap_cooling:
            if not self.running:
                self.reactors_worker.message.emit("Separate", "")
                return
            if not self.valve_vortex.active and self.trap.value is not None and self.trap.value > temperature + 5:
                self.smc_device.set([self.valve_vortex.id], 1) # TODO check if connected
            elif self.valve_vortex.active and self.trap.value is not None and self.trap.value > temperature - 5:
                self.smc_device.set([self.valve_vortex.id], 0)
            time.sleep(1)
        self.smc_device.set([self.valve_vortex.id], 0)
        self.reactors_worker.message.emit("Separate", "")

    def clean_trap(self, temperature, duration):
        self.reactors_worker.message.emit("Separate", "Started Clean Trap")
        self.start_heaters([self.trap], temperature)
        self.smc_device.set([self.valve_sampling.id], 1)
        while self.trap.value is not None and self.trap.value < temperature:
            if not self.running:
                self.reactors_worker.message.emit("Separate", "")
                return
            time.sleep(1)
        status = self.wait(duration)
        if status:
            self.reactors_worker.message.emit("Separate", "")
            return 
        self.stop_heaters([self.trap])
        # status = self.wait(20)
        # if status:
        #     self.reactors_worker.message.emit("Separate", "")
        #     return 
        self.smc_device.set([self.valve_sampling.id], 0)
        self.reactors_worker.message.emit("Separate", "")

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

    def leak_test(self, duration, limit, evac_duration):
        while True:
            self.smc_device.set([self.valve_vacuum.id] + [v.id for v in self.valve_reactors], 1)
            status = self.wait(evac_duration)
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
                wait = threading.Event()
                self.reactors_worker.prompt.emit("Leak limit exceeded. How to proceed?", wait)
                wait.wait()
                if self.prompt_reply == QMessageBox.StandardButton.Retry:
                    continue
                elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                    self.parent.stop()
                    return -1
            return 0

    def h2_cleaning(self, repetitions, duration, evac_duration):
        self.smc_device.set([v.id for v in self.valve_reactors], 1)
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
            self.smc_device.set([self.valve_vacuum.id], 1)
            status = self.wait(evac_duration)
            if status:
                return -1
            self.smc_device.set([self.valve_vacuum.id], 0)
        self.smc_device.set([v.id for v in self.valve_reactors], 0)
        return 0

    def correct_offset(self):
        for i, r in enumerate(self.reactors):
            r.reset()
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
        reactors_evac_dur = cfg["Reactors Evacuation Duration"]["Value"]
        leak_test_dur = cfg["Leak Test Duration"]["Value"]
        leak_press_limit = cfg["Leak Pressure Limit"]["Value"]
        h2_cycle_reps = cfg["H2 Cycle Repetitions"]["Value"]
        h2_cycle_dur = cfg["H2 Cycle Duration"]["Value"]
        cfg = self.config["Separate"]
        clean_trap_temp = cfg["Clean Trap Temperature"]["Value"]
        clean_trap_dur = cfg["Clean Trap Duration"]["Value"]

        if any(r.value is not None and r.get_value() < 0.8 for r in self.reactors):
            self.parent.stop()
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return
        if clean_trap_temp > 550:
            self.parent.stop()
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return
        if cond_oven_temp > 650:
            self.parent.stop()
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return
        # TODO check inputs are int and float not nonsense

        self.smc_device.close_all()

        self.reactors_worker.message.emit("Conditioning", "Started Oxidize Iron")
        status = self.oxidize_iron(cond_oven_temp, preheat_iron_dur)
        if status:
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return

        self.separate_worker.request(self.clean_trap, clean_trap_temp, clean_trap_dur)
        self.separate_worker.request(self.process_runin)

        self.reactors_worker.message.emit("Conditioning", "Started Leak Test")
        status = self.leak_test(leak_test_dur, leak_press_limit, reactors_evac_dur)
        if status:
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return

        self.reactors_worker.message.emit("Conditioning", "Started H2 Cleaning")
        status = self.h2_cleaning(h2_cycle_reps, h2_cycle_dur, reactors_evac_dur)
        if status:
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return

        self.reactors_worker.message.emit("Conditioning", "Started Correct Offset")
        status = self.correct_offset()
        if status:
            self.reactors_worker.message.emit("Conditioning", "Stopped")
            return

        self.smc_device.close_all()
        self.reactors_worker.message.emit("Conditioning", "Completed")
        return

    # ----- Stage Load Samples -----
    def load_reactor(self, reactor, vacuum_duration, release_duration, temperature, scaling):
        self.smc_device.set([self.valve_vacuum.id, self.valve_trap.id], 1)
        status = self.wait(5)
        if status:
            return -1
        self.smc_device.set(self.valve_reactors[reactor.id - 1].id, 1)
        status = self.wait(vacuum_duration)
        if status:
            return -1
        self.smc_device.set([self.valve_vacuum.id], 0)
        self.start_heaters([self.trap], temperature)
        while self.trap.value is not None and self.trap.value < temperature:
            if not self.running:
                return -1
            time.sleep(1)
        status = self.wait(release_duration)
        if status:
            return -1     

        self.smc_device.set([self.valve_reactors[reactor.id - 1].id, self.valve_trap], 0)

        self.stop_heaters([self.trap])
        # self.reactors_worker.message.emit("Load Samples", "Started Cleaning Trap")
        self.separate_worker.request(self.clean_trap)

        if 1 <= reactor.id <= 5:
            id = 0
        elif 6 <= reactor.id <= 10:
            id = 1
        
        pressure_CO2 = self.get_average_pressure()
        self.table.set_entry(pressure_CO2, reactor.id - 1, 2)
        print("pressure C02" + str(pressure_CO2))
        while reactor.value is not None and reactor.get_value() > 0.57:
            if not self.running:
                return -1
            self.smc_device.set([self.valve_vacuum.id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_vacuum.id], 0)
            # self.smc_device.set([self.valve_reactors[reactor.id - 1].id], 1)
            self.smc_device.set([self.valve_lines[id].id], 1)
            time.sleep(1)
            # self.smc_device.set([self.valve_reactors[reactor.id - 1].id], 0)
            self.smc_device.set([self.valve_lines[id].id], 0)
        pressure_CO2_final = self.get_average_pressure()
        self.table.set_entry(pressure_CO2_final, reactor.id - 1, 3)
        print("pressure CO2 final: " + str(pressure_CO2_final))

        self.smc_device.set([self.valve_reactors[reactor.id - 1].id, self.valve_h2.id], 1)
        while reactor.value is not None and reactor.get_value() > pressure_CO2_final*(scaling + 1)-0.2:
            if not self.running:
                return -1
        self.smc_device.set([self.valve_reactors[reactor.id - 1].id, self.valve_h2.id], 0)

        while reactor.value is not None and reactor.get_value() > pressure_CO2_final*(scaling + 1):
            if not self.running:
                return -1
            self.smc_device.set([self.valve_h2.id], 1)
            time.sleep(1)
            self.smc_device.set([self.valve_h2.id], 0)
            # self.smc_device.set([self.valve_reactors[reactor.id - 1].id], 1)
            self.smc_device.set([self.valve_lines[id].id], 1)
            time.sleep(1)
            # self.smc_device.set([self.valve_reactors[reactor.id - 1].id], 0)       
            self.smc_device.set([self.valve_lines[id].id], 0)
        self.smc_device.set([self.valve_lines[id].id], 1)
        pressure_H2 = self.get_average_pressure()
        self.table.set_entry(pressure_H2, reactor.id - 1, 4)
        print("pressure H2: " + str(pressure_H2))
        return 0

    def sampling(self, reactor, index):
        while self.trap.value is not None and self.trap.value > 50:
            if not self.running:
                return -1
            time.sleep(1)

        self.tcpip.start()
        while self.tcpip.get_status() != "STS RUN":
            print(self.tcpip.get_status())
            if not self.running:
                return -1
            time.sleep(1)       

        self.tcpip.start_processing()

        status = self.tcpip.get_process_status()
        while len(status.split()) < 3 or int(status.split()[2]) < 10:
            print(status)
            if not self.running:
                self.tcpip.stop_processing()
                return -1
            status = self.tcpip.get_process_status()
            time.sleep(1)
        self.smc_device.set([self.valve_sampling.id], 1)
        status = self.tcpip.get_process_status()
        while len(status.split()) < 3 or int(status.split()[2]) < 15:
            print(status)
            if not self.running:
                self.tcpip.stop_processing()
                return -1
            status = self.tcpip.get_process_status()
            time.sleep(1)
        self.smc_device.set([self.valve_sampling.id], 0)
        self.tcpip.stop_processing()
        c, n = self.tcpip.get_c(index), self.tcpip.get_n(index)
        pressure = self.get_average_pressure()
        self.table.set_entry(pressure, reactor.id - 1, 5)
        print("C%: " + str(c) + ", N%: " + str(n))
        return 0

    def load_samples(self):
        cfg = self.config["Load Samples"]
        trap_vac_dur = cfg["Trap Vacuum Duration"]["Value"]
        trap_release_dur = cfg["Trap Release Duration"]["Value"]
        trap_heating_temp = cfg["Trap Heating Temperature"]["Value"]
        co2_press_scaling = cfg["CO2 Pressure Scaling"]["Value"]
        cfg = self.config["Separate"]
        clean_trap_temp = cfg["Clean Trap Temperature"]["Value"]
        clean_trap_dur = cfg["Clean Trap Duration"]["Value"]
        trap_cooling_temp = cfg["Trap Cooling Temperature"]["Value"]

        if trap_heating_temp > 550:
            self.reactors_worker.message.emit("Load Samples", "Stopped")
            self.parent.stop()
            return
        if clean_trap_temp > 550:
            self.reactors_worker.message.emit("Load Samples", "Stopped")
            self.parent.stop()
            return

        self.smc_device.set([v.id for v in self.valve_lines], 1)

        self.reactors_worker.message.emit("Load Samples", "Started Load Samples")
        i = 0
        while i < len(self.reactors):
            while self.tcpip.get_status() != "STS READY":
                print(self.tcpip.get_status())
                if not self.running:
                    self.reactors_worker.message.emit("Load Samples", "Stopped")
                    return
                time.sleep(1)
            index = int(self.tcpip.get_index().split()[1])
            name, weight = self.tcpip.get_name(index), self.tcpip.get_weight(index)
            self.table.set_entry(name.split()[2], self.reactors[i].id - 1, 0)
            self.table.set_entry(weight.split()[2], self.reactors[i].id - 1, 1)
            print("Index: " + str(index) + ", Name: " + name + ", Weight: " + str(weight))

            self.trap_cooling = True
            self.separate_worker.request(self.cool_trap, trap_cooling_temp)
            self.reactors_worker.message.emit("Load Samples", "Started Sampling")
            status = self.sampling(self.reactors[i], index)
            if status:
                self.reactors_worker.message.emit("Load Samples", "Stopped")
                self.trap_cooling = False
                return 
            self.trap_cooling = False

            if name.split()[0].lower() == "pre": 
                # self.reactors_worker.message.emit("Load Samples", "Started Cleaning Trap")
                self.separate_worker.request(self.clean_trap, clean_trap_temp, clean_trap_dur)
                continue

            if name.split()[0].lower() == "first":
                continue

            self.reactors_worker.message.emit("Load Samples", "Started Load Reactor")
            status = self.load_reactor(self.reactors[i], trap_vac_dur, trap_release_dur, trap_heating_temp, co2_press_scaling)
            if status:
                self.reactors_worker.message.emit("Load Samples", "Stopped")
                return 
            i += 1

        # send EA to sleep?

        self.smc_device.close_all()
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

        if reaction_temp > 650:
            self.reactors_worker.message.emit("Reaction", "Stopped")
            self.parent.stop()
            return

        self.smc_device.set([self.valve_lift.id], 1)

        self.reactors_worker.message.emit("Reaction", "Started Reaction")
        self.set_peltiers(1)
        self.start_heaters(self.ovens, reaction_temp)
        while any(o.value is not None and o.value < reaction_temp for o in self.ovens):
            if not self.running:
                self.reactors_worker.message.emit("Reaction", "Stopped")
                return 
            time.sleep(1)
        end_time = time.time() + reaction_dur
        while time.time() < end_time:
            if not self.running:
                self.reactors_worker.message.emit("Reaction", "Stopped")
                return
            self.reactors_worker.message.emit("Reaction", "Reaction Time Left: " + str(int(end_time - time.time())) + "s")
            time.sleep(1)
        self.smc_device.set([self.valve_lift.id], 0)
        self.stop_heaters(self.ovens)
        if any(r.get_value() is not None and r.get_value() > end_press_limit for r in self.reactors): # TODO how to handle
            self.parent.stop()
            self.reactors_worker.message.emit("Reaction", "Stopped")
            return 

        self.reactors_worker.message.emit("Reaction", "Started Remove Water")
        status = self.remove_water(water_removal_dur)
        if status:
            self.reactors_worker.message.emit("Reaction", "Stopped")
            return

        self.smc_device.close_all()
        self.reactors_worker.message.emit("Reaction", "Completed")
        return 

    def closeEvent(self, event):
        self.running = False

        self.reactors_worker.clear()
        self.separate_worker.clear()

        self.reactors_worker.stop()
        self.separate_worker.stop()

        event.accept()
        

