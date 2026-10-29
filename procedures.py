import time
import tm, smc, keller
import json
import numpy as np
import worker
import tcpip
import threading
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

class Procedures:
    def __init__(self, parent, tcpip, smc, keller, tm, peltier, worker, helper, table, schematic):
        self.parent = parent
        self.filename = "procedures_config.json"

        self.running = False
        self.trap_cooling = False
        self.prompt_reply = None
        self.procedures = []

        self.tcpip = tcpip
        self.smc = smc
        self.keller = keller
        self.tm = tm
        self.peltier = peltier

        self.worker = worker
        self.helper = helper

        self.schematic = schematic
        self.table = table # make function

        self.valve_reactors = self.schematic.valve_reactors
        self.valve_lines = self.schematic.valve_lines
        self.valve_vacuum = [self.schematic.valve_vacuum]
        self.valve_trap = [self.schematic.valve_trap]
        self.valve_h2 = [self.schematic.valve_h2]
        self.valve_vortex = [self.schematic.valve_vortex]
        self.valve_lift = [self.schematic.valve_lift]
        self.valve_sampling = [self.schematic.valve_sampling]

        self.reactors = self.schematic.reactors

        self.ovens = self.schematic.ovens
        self.trap = [self.schematic.trap]

        self.peltiers = self.schematic.peltiers

    def set_active(self): # Make getters and setters, combine?
        self.reactors = [r for r in self.schematic.reactors if r.active]

        # Close Both Lines
        if not self.reactors:
            self.ovens = []
            self.peltiers = []
            self.valve_lines = []

        elif all(6 <= r.id <= 10 for r in self.reactors):
            self.ovens = [self.schematic.ovens[1]]
            self.peltiers = [self.schematic.peltiers[1]]
            self.valve_lines = [self.schematic.valve_lines[1]]
            self.schematic.ovens[0].set_active(False)
            self.schematic.peltiers[0].set_active(False)

        elif all(1 <= r.id <= 5 for r in self.reactors):
            self.ovens = [self.schematic.ovens[0]]
            self.peltiers = [self.schematic.peltiers[0]]
            self.valve_lines = [self.schematic.valve_lines[0]]
            self.schematic.ovens[1].set_active(False)
            self.schematic.peltiers[1].set_active(False)

        idx = [r.id for r in self.reactors if r.id <= 5] + [21 - r.id for r in self.reactors if r.id > 5] # Could be better
        self.valve_reactors = [v for v in self.schematic.valves if v.id in idx]

    def set_reactor_valves(self, active):
        if self.worker.requests.empty():
            with open(self.filename, "r") as f:
                self.config = json.load(f)

            self.set_active()
            self.worker.request(self.smc.set, self.get_idx(self.valve_reactors), active)       

    def start(self, names):
        if self.worker.requests.empty():
            with open(self.filename, "r") as f:
                self.config = json.load(f)

            self.set_active()
            funcs = []

            for name in names:
                if name == "Conditioning":
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
                        self.worker.prompt.emit("Reactor pressure below limit.", None)
                        return
                    if clean_trap_temp > 550:
                        self.worker.prompt.emit("Trap cleaning temperature exceeds limit.", None)
                        return
                    if cond_oven_temp > 650:
                        self.worker.prompt.emit("Oven conditioning temperature exceeds limit.", None)
                        return

                    args = (
                        cond_oven_temp, preheat_iron_dur, reactors_evac_dur, 
                        leak_test_dur, leak_press_limit, h2_cycle_reps, 
                        h2_cycle_dur, clean_trap_temp, clean_trap_dur
                    )
                    funcs.append((self.conditioning, args))

                elif name == "Load Samples":
                    cfg = self.config["Load Samples"]
                    trap_vac_dur = cfg["Trap Vacuum Duration"]["Value"]
                    trap_release_dur = cfg["Trap Release Duration"]["Value"]
                    trap_heating_temp = cfg["Trap Heating Temperature"]["Value"]
                    co2_press_scaling = cfg["CO2 Pressure Scaling"]["Value"]
                    load_press_limit = cfg["Load Pressure Limit"]["Value"]
                    cfg = self.config["Separate"]
                    clean_trap_temp = cfg["Clean Trap Temperature"]["Value"]
                    clean_trap_dur = cfg["Clean Trap Duration"]["Value"]
                    trap_cooling_temp = cfg["Trap Cooling Temperature"]["Value"]

                    if trap_heating_temp > 550:
                        self.worker.message.emit("Trap heating temperature exceeds limit.", None)
                        return
                    if clean_trap_temp > 550:
                        self.worker.message.emit("Trap cleaning temperature exceeds limit.", None)
                        return

                    args = (
                        trap_vac_dur, trap_release_dur, trap_heating_temp, 
                        co2_press_scaling, clean_trap_temp, clean_trap_dur,
                        trap_cooling_temp, load_press_limit
                    )
                    funcs.append((self.load_samples, args))

                elif name == "Reaction":
                    cfg = self.config["Reaction"]
                    reaction_temp = cfg["Reaction Temperature"]["Value"]
                    reaction_dur = cfg["Reaction Duration"]["Value"]
                    end_press_limit = cfg["End Pressure Limit"]["Value"]
                    water_removal_dur = cfg["Water Removal Duration"]["Value"]

                    if reaction_temp > 650:
                        self.worker.prompt.emit("Reaction temperature exceeds limit.", None)
                        return

                    args = (reaction_temp, reaction_dur, end_press_limit, water_removal_dur)
                    funcs.append((self.reaction, args))

            self.running = True 
            for f, args in funcs:
                self.worker.request(f, *args)
            return

    def stop(self):
        self.running = False

    # ----- Helper Functions -----
    def get_idx(self, container):
        return [element.id for element in container]

    def start_heaters(self, heaters, temperature):
        self.tm.set(self.get_idx(heaters), temperature)
        self.tm.start(self.get_idx(heaters))
        for o in heaters:
            o.set_running(True)    

    def stop_heaters(self, heaters):
        self.tm.stop(self.get_idx(heaters))
        for o in heaters:
            o.set_running(False)

    def set_peltiers(self, running):
        self.peltier.set(self.get_idx(self.peltiers), running)
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
        dt = 0.5
        end_time = time.time() + duration
        while time.time() < end_time:
            if not self.running:
                return -1
            
            for i, r in enumerate(self.reactors):
                if r.value is not None:
                    pressures[i] += dt * r.get_value() / duration
                else:
                    pressures[i] = None
            time.sleep(dt)
        return pressures

    # ----- Parallel Procedures -----
    def process_runin(self):
        self.helper.message.emit("Processing runins")
        for _ in self.reactors:
            status = self.tcpip.get_status()
            while status != "STS READY":
                if not self.running:
                    self.helper.message.emit("")
                    return
                if len(status.split()) > 1 and status.split()[1] == "ERR":
                    self.helper.message.emit(status)
                    return
                time.sleep(1)
                status = self.tcpip.get_status()

            index = int(self.tcpip.get_index().split()[1])
            name = self.tcpip.get_name(index).split()[2]
            if name.lower() == "runin":
                self.tcpip.start()

        self.helper.message.emit("")
        return

    def cool_trap(self, temperature):
        self.helper.message.emit("Cooling trap")
        while self.trap_cooling:
            if not self.running:
                self.helper.message.emit("")
                return # make better
            if not self.valve_vortex[0].active and self.trap[0].value is not None and self.trap[0].get_value() > temperature + 3:
                self.smc.set(self.get_idx(self.valve_vortex), 1) 
            elif self.valve_vortex[0].active and self.trap[0].value is not None and self.trap[0].get_value() < temperature - 3:
                self.smc.set(self.get_idx(self.valve_vortex), 0)
            time.sleep(1)
        self.smc.set(self.get_idx(self.valve_vortex), 0)

        self.helper.message.emit("")
        return

    def clean_trap(self, temperature, duration):
        self.helper.message.emit("Cleaning trap")

        self.start_heaters(self.trap, temperature)
        self.smc.set(self.get_idx(self.valve_sampling), 1)

        while self.trap[0].value is not None and self.trap[0].get_value() < temperature:
            if not self.running:
                self.helper.message.emit("")
                return
            time.sleep(1)

        status = self.wait(duration)
        if status:
            self.helper.message.emit("")
            return 
        
        self.stop_heaters(self.trap)
        self.smc.set(self.get_idx(self.valve_sampling), 0)

        self.helper.message.emit("")
        return

    # ----- Conditioning Procedures ----- 
    def oxidize_iron(self, temperature, duration):
        self.worker.message.emit("Heating ovens")
        self.start_heaters(self.ovens, temperature)
        while any(o.value is not None and o.get_value() < temperature for o in self.ovens):
            if not self.running:
                return -1
            time.sleep(1.0)

        self.worker.message.emit("Oxidizing iron")
        self.smc.set(self.get_idx(self.valve_lift), 1)
        status = self.wait(duration)
        if status:
            return -1
        return 0

    def leak_test(self, duration, limit, evac_duration):
        while True:
            self.worker.message.emit("Evacuating reactors")
            self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 1)
            status = self.wait(evac_duration)
            if status:
                return -1 

            self.worker.message.emit("Testing for leaks")
            self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 0)
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
            if any(res is not None and res > limit for res in result):
                wait = threading.Event()
                self.worker.prompt.emit("Leak limit exceeded.", wait)
                wait.wait()
                if self.prompt_reply == QMessageBox.StandardButton.Retry:
                    continue
                elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                    self.parent.stop() # hand down?
                    return -1
            return 0

    def h2_cleaning(self, repetitions, duration, evac_duration):
        self.smc.set(self.get_idx(self.valve_reactors), 1)
        for i in range(repetitions):
            self.worker.message.emit(f"Cleaning reactors (Cycle {i+1}/{repetitions})")
            self.smc.set(self.get_idx(self.valve_h2), 1)
            while all(r.get_value() is not None and r.value < 0.8 for r in self.reactors):
                if not self.running:
                    return -1
                time.sleep(0.2)
                
            self.smc.set(self.get_idx(self.valve_h2), 0)
            status = self.wait(duration)
            if status:
                return -1
            self.smc.set(self.get_idx(self.valve_vacuum), 1)
            status = self.wait(evac_duration)
            if status:
                return -1
            
            self.smc.set(self.get_idx(self.valve_vacuum), 0)
        self.smc.set(self.get_idx(self.valve_reactors), 0)
        return 0

    def correct_offset(self):
        for r in self.reactors:
            r.reset()

        self.worker.message.emit("Evacuating reactors")
        self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 1)
        status = self.wait(20)
        if status:
            return -1
        
        self.worker.message.emit("Measuring offsets")
        offsets = self.get_average_pressure()
        if offsets == -1:
            return -1
        
        for i, r in enumerate(self.reactors):
            if i < len(offsets):
                r.offset = offsets[i]
        self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 0)
        return 0

    def conditioning(self, cond_oven_temp, preheat_iron_dur, reactors_evac_dur, 
                            leak_test_dur, leak_press_limit, h2_cycle_reps, 
                            h2_cycle_dur, clean_trap_temp, clean_trap_dur):
        self.smc.close_all()
        self.smc.set([v.id for v in self.valve_lines], 1)

        status = self.oxidize_iron(cond_oven_temp, preheat_iron_dur)
        if status:
            self.worker.message.emit("")
            return

        self.helper.request(self.clean_trap, clean_trap_temp, clean_trap_dur)
        self.helper.request(self.process_runin)

        status = self.leak_test(leak_test_dur, leak_press_limit, reactors_evac_dur)
        if status:
            self.worker.message.emit("")
            return

        status = self.h2_cleaning(h2_cycle_reps, h2_cycle_dur, reactors_evac_dur)
        if status:
            self.worker.message.emit("")
            return

        status = self.correct_offset()
        if status:
            self.worker.message.emit("")
            return

        self.smc.close_all()
        self.worker.message.emit("")
        return

    # ----- Stage Load Samples -----
    def load_reactor(self, reactor, valve_reactor, vacuum_duration, release_duration, clean_trap_temp, clean_trap_dur, temperature, scaling, limit):
        if len(self.valve_lines) < 2: # check timining of valve closing
            valve_line = self.valve_lines
        else:
            if 1 <= reactor.id <= 5: 
                valve_line = [self.valve_lines[0]]
            elif 6 <= reactor.id <= 10:
                valve_line = [self.valve_lines[1]]

        self.worker.message.emit("Evacuating trap")
        self.smc.set(self.get_idx(self.valve_vacuum), 1)
        time.sleep(0.2)
        self.smc.set(self.get_idx(self.valve_trap), 1)
        status = self.wait(3)
        if status:
            return -1
        
        self.worker.message.emit(f"Evacuating reactor {reactor.id}")
        self.smc.set([valve_reactor.id], 1)
        status = self.wait(vacuum_duration)
        if status:
            return -1
        
        self.smc.set(self.get_idx(self.valve_vacuum), 0)

        self.worker.message.emit("Heating trap")
        self.start_heaters(self.trap, temperature)
        while self.trap[0].value is not None and self.trap[0].get_value() < temperature:
            if not self.running:
                return -1
            time.sleep(1)

        self.worker.message.emit(f"Loading reactor {reactor.id}")
        status = self.wait(release_duration)
        if status:
            return -1     

        self.smc.set(self.get_idx(self.valve_trap + valve_line), 0)

        self.stop_heaters(self.trap)
        self.helper.request(self.clean_trap, clean_trap_temp, clean_trap_dur)

        pressure_CO2 = reactor.get_value()
        self.table.set_entry(int(pressure_CO2 * 1000), reactor.id - 1, 2)

        self.worker.message.emit("Evacuating excess load")
        while reactor.value is not None and reactor.get_value() > limit:
            if not self.running:
                return -1
            self.smc.set(self.get_idx(self.valve_vacuum), 1)
            time.sleep(0.4)
            self.smc.set(self.get_idx(self.valve_vacuum), 0)
            time.sleep(0.2)
            self.smc.set(self.get_idx(valve_line), 1)
            time.sleep(0.4)
            self.smc.set(self.get_idx(valve_line), 0)
            time.sleep(0.2)
        
        pressure_CO2_final = reactor.get_value()
        self.table.set_entry(int(pressure_CO2_final * 1000), reactor.id - 1, 3)

        self.worker.message.emit("Loading hydrogen")
        self.smc.set(self.get_idx(self.valve_h2 + valve_line), 1)
        while reactor.value is not None and reactor.get_value() < pressure_CO2_final*(scaling + 1)-0.2:
            if not self.running:
                return -1
            time.sleep(0.2)
        self.smc.set(self.get_idx(self.valve_h2 + valve_line), 0)
        while reactor.value is not None and reactor.get_value() < pressure_CO2_final*(scaling + 1):
            if not self.running:
                return -1
            self.smc.set(self.get_idx(self.valve_h2), 1)
            time.sleep(0.4)
            self.smc.set(self.get_idx(self.valve_h2), 0)
            time.sleep(0.2)
            self.smc.set(self.get_idx(valve_line), 1)
            time.sleep(0.4)
            self.smc.set(self.get_idx(valve_line), 0)
            time.sleep(0.2)

        self.smc.set([valve_reactor.id], 0)
        time.sleep(0.2)
        self.smc.set(self.get_idx(valve_line), 1)

        pressure_H2 = reactor.get_value()
        self.table.set_entry(int(pressure_H2 * 1000), reactor.id - 1, 4)

        return 0

    def sampling(self, reactor, index):
        self.worker.message.emit("Waiting for trap to cool")
        while self.trap[0].value is not None and self.trap[0].get_value() > 50:
            if not self.running:
                return -1
            time.sleep(1)

        self.worker.message.emit("Starting EA")
        self.tcpip.start()
        status = self.tcpip.get_status()
        while status != "STS RUN":
            if not self.running:
                return -1
            time.sleep(1) 
            status = self.tcpip.get_status()          

        self.tcpip.start_processing()

        self.worker.message.emit("Processing sample")
        status = self.tcpip.get_process_status().split()
        while len(status) < 3 or int(status[2]) < 10:
            if not self.running:
                self.tcpip.stop_processing()
                return -1
            time.sleep(1)
            status = self.tcpip.get_process_status().split()

        self.worker.message.emit("Loading trap")
        self.smc.set(self.get_idx(self.valve_sampling), 1)
        status = self.tcpip.get_process_status().split()
        while len(status) < 3 or int(status[2]) < 15:
            if not self.running:
                self.tcpip.stop_processing()
                return -1
            time.sleep(1)
            status = self.tcpip.get_process_status().split()

        self.tcpip.stop_processing()

        self.smc.set(self.get_idx(self.valve_sampling), 0)

        n = float(self.tcpip.get_n(index).split()[3])
        c = float(self.tcpip.get_c(index).split()[3])
        self.table.set_entry(f"{n:.3f}", reactor.id - 1, 6)
        self.table.set_entry(f"{c:.3f}", reactor.id - 1, 7)

        pressure_end = reactor.get_value()
        self.table.set_entry(int(pressure_end * 1000), reactor.id - 1, 5)

        return 0

    def load_samples(self, trap_vac_dur, trap_release_dur, trap_heating_temp, 
                        co2_press_scaling, clean_trap_temp, clean_trap_dur, trap_cooling_temp, load_press_limit):
        self.smc.close_all()
        self.smc.set(self.get_idx(self.valve_lines), 1)

        i = 0
        while i < len(self.reactors):         
            self.worker.message.emit("Waiting for EA")
            status = self.tcpip.get_status() 
            while status != "STS READY":
                if not self.running:
                    self.worker.message.emit("")
                    return
                if len(status.split()) > 1 and status.split()[1] == "ERR":
                    self.worker.message.emit(status)
                    return
                time.sleep(1)
                status = self.tcpip.get_status()

            index = int(self.tcpip.get_index().split()[1])
            name = self.tcpip.get_name(index).split()[2]
            weight = self.tcpip.get_weight(index).split()[2]
            self.table.set_entry(name, self.reactors[i].id - 1, 0)
            self.table.set_entry(weight, self.reactors[i].id - 1, 1)

            self.trap_cooling = True
            self.helper.request(self.cool_trap, trap_cooling_temp)
            status = self.sampling(self.reactors[i], index)
            if status:
                self.worker.message.emit("")
                self.trap_cooling = False
                return 
            self.trap_cooling = False

            if name.lower() == "pre": 
                self.helper.request(self.clean_trap, clean_trap_temp, clean_trap_dur)
                continue

            if name.lower() == "first":
                continue

            status = self.load_reactor(
                self.reactors[i], self.valve_reactors[i],
                trap_vac_dur, trap_release_dur, clean_trap_temp,
                clean_trap_dur, trap_heating_temp, co2_press_scaling, load_press_limit
            )
            if status:
                self.worker.message.emit("")
                return 

            i += 1

        self.smc.close_all()
        self.worker.message.emit("")
        return 

    def remove_water(self, duration): 
        self.smc.set(self.get_idx(self.valve_vacuum), 1)
        time.sleep(0.2)
        self.smc.set(self.get_idx(self.valve_reactors), 1)
        status = self.wait(duration)
        if status:
            return -1
        self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 0)
        return 0
        
    def reaction(self, reaction_temp, reaction_dur, end_press_limit, water_removal_dur):
        self.smc.close_all()
        self.smc.set(self.get_idx(self.valve_lift + self.valve_lines), 1)

        self.set_peltiers(1)
        
        self.worker.message.emit("Heating ovens")
        self.start_heaters(self.ovens, reaction_temp)
        while any(o.value is not None and o.get_value() < reaction_temp for o in self.ovens):
            if not self.running:
                self.worker.message.emit("")
                return 
            time.sleep(1)

        self.worker.message.emit("Starting reaction")    
        end_time = time.time() + reaction_dur
        while time.time() < end_time:
            if not self.running:
                self.worker.message.emit("")
                return
            self.worker.message.emit(f"Reaction ({int(end_time - time.time())//60 + 1} min left)")
            time.sleep(1)

        self.smc.set(self.get_idx(self.valve_lift), 0)
        self.stop_heaters(self.ovens)

        # self.worker.message.emit("Waiting for reactor pressure to fall below limit")
        # while any(r.value is not None and r.get_value() > end_press_limit for r in self.reactors):
        #     if not self.running:
        #         self.worker.message.emit("")
        #         return
        #     time.sleep(1)

        self.worker.message.emit("Removing water")
        status = self.remove_water(water_removal_dur)
        if status:
            self.worker.message.emit("")
            return

        self.set_peltiers(0)

        self.smc.close_all()

        self.worker.message.emit("")
        return 

        

