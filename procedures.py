import time
import json
import threading
from PySide6.QtWidgets import QMessageBox
from datetime import datetime

class Procedures:
    def __init__(self, parent, tcpip, smc, keller, tm, peltier, worker, helper, table, schematic, panel):
        self.parent = parent
        self.filename = "procedures_config.json"
        self.timestamp = None

        self.running = False
        self.trap_cooling = False
        self.prompt_reply = None

        self.tcpip = tcpip
        self.smc = smc
        self.keller = keller
        self.tm = tm
        self.peltier = peltier

        self.worker = worker
        self.helper = helper

        self.schematic = schematic
        self.table = table
        self.panel = panel

        self.valve_reactors_all = self.schematic.valve_reactors
        self.valve_reactors = self.schematic.valve_reactors
        self.valve_lines = self.schematic.valve_lines
        self.valve_vacuum = [self.schematic.valve_vacuum]
        self.valve_trap = [self.schematic.valve_trap]
        self.valve_h2 = [self.schematic.valve_h2]
        self.valve_vortex = [self.schematic.valve_vortex]
        self.valve_lift = [self.schematic.valve_lift]
        self.valve_sampling = [self.schematic.valve_sampling]

        self.reactors_all = self.schematic.reactors
        self.reactors = self.schematic.reactors

        self.ovens = self.schematic.ovens
        self.trap = self.schematic.trap

        self.peltiers = self.schematic.peltiers

    def set_active(self):
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
        self.smc.set(self.get_idx(self.valve_reactors), active)       

    def start(self):
        if self.worker.requests.empty():
            funcs = [self.conditioning, self.load_samples, self.reaction]
            self.running = True 
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for f in funcs:
                self.worker.request(f)
            return

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
                    pressures[i] += dt * r.get_value() / duration
            time.sleep(dt)
        return pressures

    # ----- Parallel Procedures -----
    def process_runin(self):
        self.schematic.helper.set_running(True)
        self.helper.message.emit("Processing runins")
        for _ in self.reactors:
            status = self.tcpip.get_status()
            while status != "STS READY":
                status = self.tcpip.get_status() 
                if not self.running:
                    return
                if len(status.split()) > 1 and status.split()[1] == "ERR":
                    wait = threading.Event()
                    self.helper.prompt.emit(status, QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel, wait)
                    wait.wait()
                    if self.prompt_reply == QMessageBox.StandardButton.Retry:
                        continue
                    elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                        self.parent.stop()
                        return
                time.sleep(1)

            index = int(self.tcpip.get_index().split()[1])
            name = self.tcpip.get_name(index).split()[2]
            if name.lower() == "runin":
                self.tcpip.start()

        self.helper.message.emit("")
        self.schematic.helper.set_running(False)
        return

    def cool_trap(self):
        with open(self.filename, "r") as f:
            self.config = json.load(f)
        cfg = self.config["Separate"]
        trap_cooling_temp = cfg["Trap Cooling Temperature"]["Value"]

        self.schematic.helper.set_running(True)
        self.helper.message.emit("Cooling trap")
        while self.trap_cooling:
            if not self.running:
                return
            if self.trap.get_value() > trap_cooling_temp + 3:
                self.smc.set(self.get_idx(self.valve_vortex), 1) 
            elif self.trap.get_value() < trap_cooling_temp - 3:
                self.smc.set(self.get_idx(self.valve_vortex), 0)
            time.sleep(1)
        self.smc.set(self.get_idx(self.valve_vortex), 0)

        self.helper.message.emit("")
        self.schematic.helper.set_running(False)
        return

    def clean_trap(self):
        while True:
            with open(self.filename, "r") as f:
                self.config = json.load(f)
            cfg = self.config["Separate"]
            clean_trap_temp = cfg["Clean Trap Temperature"]["Value"]
            clean_trap_dur = cfg["Clean Trap Duration"]["Value"]
            if clean_trap_temp > 550:
                wait = threading.Event()
                self.helper.prompt.emit("Trap cleaning temperature exceeds limit.", QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel, wait)
                wait.wait()
                if self.prompt_reply == QMessageBox.StandardButton.Retry:
                    continue
                elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                    self.parent.stop()
                    return

            self.schematic.helper.set_running(True)
            self.helper.message.emit("Cleaning trap")

            self.start_heaters([self.trap], clean_trap_temp)
            self.smc.set(self.get_idx(self.valve_sampling), 1)

            while self.trap.get_value() < clean_trap_temp:
                if not self.running:
                    return
                time.sleep(1)

            status = self.wait(clean_trap_dur)
            if status:
                return 
            
            self.stop_heaters([self.trap])
            self.smc.set(self.get_idx(self.valve_sampling), 0)

            self.helper.message.emit("")
            self.schematic.helper.set_running(False)
            return

    def ea_sleep(self):
        self.schematic.helper.set_running(True)
        self.helper.message.emit("Sending EA to sleep")

        self.tcpip.sleep()
        status = self.tcpip.get_status() 
        while status != "STS ERR":
            self.tcpip.sleep()
            status = self.tcpip.get_status() 
            if not self.running:
                return
            time.sleep(1)

        self.helper.message.emit("")
        self.schematic.helper.set_running(False)
        return

    # ----- Conditioning Procedures ----- 
    def oxidize_iron(self):
        while True:
            with open(self.filename, "r") as f:
                self.config = json.load(f)
            cfg = self.config["Conditioning"]
            cond_oven_temp = cfg["Conditioning Oven Temperature"]["Value"]
            preheat_iron_dur = cfg["Preheating Iron Duration"]["Value"]
            if any(r.get_value() < 0.8 for r in self.reactors):
                wait = threading.Event()
                self.worker.prompt.emit("Pressure too low.", QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Ignore | QMessageBox.StandardButton.Cancel, wait)
                wait.wait()
                if self.prompt_reply == QMessageBox.StandardButton.Retry:
                    continue
                elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                    self.parent.stop()
                    return -1
            if cond_oven_temp > 650:
                wait = threading.Event()
                self.worker.prompt.emit("Oven conditioning temperature exceeds limit.", QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel, wait)
                wait.wait()
                if self.prompt_reply == QMessageBox.StandardButton.Retry:
                    continue
                elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                    self.parent.stop()
                    return -1 
            self.set_active()

            self.worker.message.emit("Heating ovens")
            self.start_heaters(self.ovens, cond_oven_temp)
            while any(o.get_value() < cond_oven_temp for o in self.ovens):
                if not self.running:
                    return -1
                time.sleep(1.0)

            self.worker.message.emit("Oxidizing iron")
            self.smc.set(self.get_idx(self.valve_lift), 1)
            status = self.wait(preheat_iron_dur)
            if status:
                return -1
            return 0

    def leak_test(self):
        while True:
            with open(self.filename, "r") as f:
                self.config = json.load(f)
            cfg = self.config["Conditioning"]
            reactors_evac_dur = cfg["Reactors Evacuation Duration"]["Value"]
            leak_test_dur = cfg["Leak Test Duration"]["Value"]
            leak_press_limit = cfg["Leak Pressure Limit"]["Value"]
            self.set_active()

            self.worker.message.emit("Evacuating reactors")
            self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 1)
            status = self.wait(reactors_evac_dur)
            if status:
                return -1 

            self.worker.message.emit("Testing for leaks")
            self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 0)
            start = self.get_average_pressure()
            if start == -1:
                return -1
            status = self.wait(leak_test_dur)
            if status:
                return -1
            end = self.get_average_pressure()  
            if end == -1:
                return -1
            exceeding = []
            for i in range(len(self.reactors)):
                if abs(start[i] - end[i]) > leak_press_limit:
                    exceeding.append(self.reactors[i].id) 

            if len(exceeding) > 0:
                text = "Leak limit exceeded by"
                for i in exceeding:
                    text += " Reactor " + i
                wait = threading.Event()
                self.worker.prompt.emit(text, QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Ignore | QMessageBox.StandardButton.Cancel, wait)
                wait.wait()
                if self.prompt_reply == QMessageBox.StandardButton.Retry:
                    continue
                elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                    self.parent.stop()
                    return -1
            return 0

    def h2_cleaning(self):
        for _ in range(h2_cycle_reps):
            while not self.panel.auto.running:
                self.worker.message.emit("")
                if not self.running:
                    return 
                time.sleep(1)
            with open(self.filename, "r") as f:
                self.config = json.load(f)
            cfg = self.config["Conditioning"]
            reactors_evac_dur = cfg["Reactors Evacuation Duration"]["Value"]
            h2_press_limit = cfg["H2 Pressure Limit"]["Value"]
            h2_cycle_reps = cfg["H2 Cycle Repetitions"]["Value"]
            h2_cycle_dur = cfg["H2 Cycle Duration"]["Value"]
            self.set_active()

            self.worker.message.emit("Cleaning reactors")
            self.smc.set(self.get_idx(self.valve_reactors), 1)
            time.sleep(0.4)

            self.smc.set(self.get_idx(self.valve_h2), 1)
            while all(r.get_value() < h2_press_limit for r in self.reactors):
                if not self.running:
                    return -1
                time.sleep(0.4)
                
            self.smc.set(self.get_idx(self.valve_h2), 0)
            status = self.wait(h2_cycle_dur)
            if status:
                return -1
            self.smc.set(self.get_idx(self.valve_vacuum), 1)
            status = self.wait(reactors_evac_dur)
            if status:
                return -1
            
            self.smc.set(self.get_idx(self.valve_vacuum), 0)
        self.smc.set(self.get_idx(self.valve_reactors), 0)
        return 0

    def correct_offset(self):
        with open(self.filename, "r") as f:
            self.config = json.load(f)
        cfg = self.config["Conditioning"]
        offset_vac_dur = cfg["Offset Vacuum Duration"]["Value"]
        self.set_active()

        self.worker.message.emit("Correcting offset")
        self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 1)
        status = self.wait(offset_vac_dur)
        if status:
            return -1

        with open("settings.json", "r") as f:
            settings = json.load(f)

        for i, r in enumerate(self.reactors):
            offset = r.value
            r.offset = offset
            settings["Reactors"][f"Reactor {r.id}"]["Offset"] = offset
            r.slope = settings["Reactors"][f"Reactor {r.id}"]["Slope"]

        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

        self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 0)
        return 0

    def conditioning(self):
        if not self.panel.conditioning.active:
            self.schematic.worker.set_running(False)                
            if self.worker.requests.empty():
                self.parent.stop()
            return
        self.schematic.worker.set_running(True)
        self.panel.conditioning.set_running(True)
        self.set_active()

        self.smc.close_all()
        time.sleep(0.4)
        self.smc.set([v.id for v in self.valve_lines], 1)

        while not self.panel.auto.running:
            self.worker.message.emit("")
            if not self.running:
                return 
            time.sleep(1)
        status = self.oxidize_iron()
        if status:
            return
        self.worker.message.emit("Saving")    
        self.parent.save(self.timestamp)

        self.helper.request(self.clean_trap)
        self.helper.request(self.process_runin)

        while not self.panel.auto.running:
            self.worker.message.emit("")
            if not self.running:
                return 
            time.sleep(1)
        status = self.leak_test()
        if status:
            return
        self.worker.message.emit("Saving")    
        self.parent.save(self.timestamp)

        while not self.panel.auto.running:
            self.worker.message.emit("")
            if not self.running:
                return 
            time.sleep(1)
        status = self.h2_cleaning()
        if status:
            return
        self.worker.message.emit("Saving")    
        self.parent.save(self.timestamp)

        while not self.panel.auto.running:
            self.worker.message.emit("")
            if not self.running:
                return 
            time.sleep(1)
        status = self.correct_offset()
        if status:
            return
        self.worker.message.emit("Saving")    
        self.parent.save(self.timestamp)

        while not self.panel.auto.running:
            self.worker.message.emit("")
            if not self.running:
                return 
            time.sleep(1)
        self.panel.conditioning.set_running(False)
        self.worker.message.emit("")
        self.smc.close_all()
        return

    # ----- Stage Load Samples -----
    def load_reactor(self, reactor, valve_reactor): 
        while True:   
            with open(self.filename, "r") as f:
                self.config = json.load(f)        
            cfg = self.config["Load Samples"]
            trap_vac_dur = cfg["Trap Vacuum Duration"]["Value"]
            trap_release_dur = cfg["Trap Release Duration"]["Value"]
            trap_heating_temp = cfg["Trap Heating Temperature"]["Value"]
            vac_step = cfg["Vacuum Step Duration"]["Value"]
            line_step = cfg["Line Step Duration"]["Value"]
            co2_press_scaling = cfg["CO2 Pressure Scaling"]["Value"]
            h2_step = cfg["H2 Step Duration"]["Value"]
            load_press_limit = cfg["Load Pressure Limit"]["Value"]
            if trap_heating_temp > 550:
                wait = threading.Event()
                self.worker.prompt.emit("Trap heating temperature exceeds limit.", QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel, wait)
                wait.wait()
                if self.prompt_reply == QMessageBox.StandardButton.Retry:
                    continue
                elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                    self.parent.stop()
                    return -1 
            self.set_active()

            if len(self.valve_lines) < 2:
                valve_line = self.valve_lines
            else:
                if 1 <= reactor.id <= 5: 
                    valve_line = [self.valve_lines[0]]
                elif 6 <= reactor.id <= 10:
                    valve_line = [self.valve_lines[1]]

            self.worker.message.emit("Evacuating trap")
            self.smc.set(self.get_idx(self.valve_vacuum), 1)
            time.sleep(0.4)
            self.smc.set(self.get_idx(self.valve_trap), 1)
            status = self.wait(3)
            if status:
                return -1

            self.smc.set(self.get_idx(valve_line), 1)
            time.sleep(0.4)
            
            self.worker.message.emit(f"Evacuating reactor {reactor.id}")
            self.smc.set([valve_reactor.id], 1)
            status = self.wait(trap_vac_dur)
            if status:
                return -1
            
            self.smc.set(self.get_idx(self.valve_vacuum), 0)
            time.sleep(0.4)

            self.worker.message.emit(f"Loading reactor {reactor.id}")
            self.start_heaters([self.trap], trap_heating_temp)
            while self.trap.get_value() < trap_heating_temp:
                if not self.running:
                    return -1
                time.sleep(1)

            status = self.wait(trap_release_dur)
            if status:
                return -1     

            self.smc.set(self.get_idx(self.valve_trap + valve_line), 0)
            time.sleep(0.4)

            self.stop_heaters([self.trap])
            self.helper.request(self.clean_trap)
            time.sleep(0.4)

            pressure_CO2 = reactor.get_value()
            self.table.set_entry(int(pressure_CO2 * 1000 / 0.57), reactor.id - 1, 2)

            self.worker.message.emit("Evacuating excess load")
            while reactor.get_value() > load_press_limit:
                if not self.running:
                    return -1
                self.smc.set(self.get_idx(self.valve_vacuum), 1)
                time.sleep(vac_step)
                self.smc.set(self.get_idx(self.valve_vacuum), 0)
                time.sleep(0.4)
                self.smc.set(self.get_idx(valve_line), 1)
                time.sleep(line_step)
                self.smc.set(self.get_idx(valve_line), 0)
                time.sleep(0.4)
            
            pressure_CO2_final = reactor.get_value()
            self.table.set_entry(int(pressure_CO2_final * 1000 / 0.57), reactor.id - 1, 3)

            self.worker.message.emit("Loading hydrogen")
            self.smc.set(self.get_idx(self.valve_h2 + valve_line), 1)
            while reactor.get_value() < pressure_CO2_final*(co2_press_scaling + 1)-0.1:
                if not self.running:
                    return -1
                time.sleep(0.4)
            self.smc.set(self.get_idx(self.valve_h2 + valve_line), 0)
            time.sleep(0.4)
            while reactor.get_value() < pressure_CO2_final*(co2_press_scaling + 1):
                if not self.running:
                    return -1
                self.smc.set(self.get_idx(self.valve_h2), 1)
                time.sleep(h2_step)
                self.smc.set(self.get_idx(self.valve_h2), 0)
                time.sleep(0.4)
                self.smc.set(self.get_idx(valve_line), 1)
                time.sleep(line_step)
                self.smc.set(self.get_idx(valve_line), 0)
                time.sleep(0.4)

            self.smc.set([valve_reactor.id], 0)
            time.sleep(0.4)

            pressure_H2 = reactor.get_value()
            self.table.set_entry(int(pressure_H2 * 1000), reactor.id - 1, 4)
            return 0

    def sampling(self):
        with open(self.filename, "r") as f:
            self.config = json.load(f)        
        cfg = self.config["Load Samples"]
        trap_sampling_temp = cfg["Trap Sampling Temperature"]["Value"]
        self.set_active()

        self.worker.message.emit("Waiting for trap")
        while self.trap.get_value() > trap_sampling_temp:
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
        return 0

    def load_samples(self):
        if not self.panel.load_samples.active:
            self.schematic.worker.set_running(False)
            if self.worker.requests.empty():
                self.parent.stop()
            return
        self.schematic.worker.set_running(True)
        self.panel.load_samples.set_running(True)
        self.set_active()
        self.smc.close_all()

        i = 0
        i_complete = []
        while i < len(self.reactors_all):
            if not self.reactors_all[i].active or i in i_complete:
                i += 1
            else:
                self.parent.panel.next.combo.setCurrentIndex(i)
                break

        while i < len(self.reactors_all):
            while not self.panel.auto.running:
                self.worker.message.emit("")
                if not self.running:
                    return 
                time.sleep(1)
            self.worker.message.emit("Waiting for EA")
            status = self.tcpip.get_status() 
            while status != "STS READY":
                time.sleep(1)
                status = self.tcpip.get_status() 
                if not self.running:
                    return
                if len(status.split()) > 1 and status.split()[1] == "ERR":
                    wait = threading.Event()
                    self.worker.prompt.emit(status, QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel, wait)
                    wait.wait()
                    if self.prompt_reply == QMessageBox.StandardButton.Retry:
                        continue
                    elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                        self.parent.stop()
                        return -1

            idx = self.tcpip.get_index().split()
            while idx[0] != "SINX":
                time.sleep(1)
                idx = self.tcpip.get_index().split()
            index = int(idx[1])

            name = self.tcpip.get_name(index).split()
            while name[0] != "NAM":
                time.sleep(1)
                name = self.tcpip.get_name(index).split()
            name = name[2]

            wgh = self.tcpip.get_weight(index).split()
            while wgh[0] != "WGH":
                time.sleep(1)
                wgh = self.tcpip.get_weight(index).split()
            weight = float(wgh[2])

            while not self.panel.auto.running:
                self.worker.message.emit("")
                if not self.running:
                    return 
                time.sleep(1)
            self.trap_cooling = True
            self.helper.request(self.cool_trap)
            status = self.sampling()
            if status:
                self.trap_cooling = False
                return 
            self.trap_cooling = False
                
            pct_n = self.tcpip.get_n(index).split()
            while pct_n[0] != "PCT" and pct_n[2] != "N":
                time.sleep(1)
                pct_n = self.tcpip.get_n(index).split()
            n = float(pct_n[3])

            pct_c = self.tcpip.get_c(index).split()
            while pct_c[0] != "PCT" and pct_c[2] != "C":
                time.sleep(1)
                pct_c = self.tcpip.get_c(index).split()
            c = float(pct_c[3])

            self.worker.message.emit("Saving")    
            self.parent.save(self.timestamp)

            if name.lower() == "pre": 
                self.helper.request(self.clean_trap)
                continue

            if name.lower() == "first":
                continue
            
            while not self.panel.auto.running:
                self.worker.message.emit("")
                if not self.running:
                    return 
                time.sleep(1)   
            i = self.parent.panel.next.combo.currentIndex()
            if i >= len(self.reactors_all):
                break
            i_next = i + 1
            while i_next < len(self.reactors_all):
                if not self.reactors_all[i_next].active or i_next in i_complete:
                    i_next += 1
                continue
            self.parent.panel.next.combo.setCurrentIndex(i_next)
            self.table.set_entry(name.split("-")[0].split("_")[0], i, 0)
            self.table.set_entry(f"{weight:.2f}", i, 1)
            self.table.set_entry(f"{n:.1f}", i, 6)
            self.table.set_entry(f"{c:.1f}", i, 7)
            self.table.set_entry(f"{(c/n):.2f}", i, 8)
            status = self.load_reactor(self.reactors_all[i], self.valve_reactors_all[i])
            if status:
                return 
            self.worker.message.emit("Saving")    
            self.parent.save(self.timestamp)
            i_complete.append(i)
            i = i_next

        self.helper.request(self.ea_sleep)
        while not self.panel.auto.running:
            self.worker.message.emit("")
            if not self.running:
                return 
            time.sleep(1)
        self.worker.message.emit("")
        self.smc.close_all()
        self.panel.load_samples.set_running(False)
        return 

    def remove_water(self): 
        with open(self.filename, "r") as f:
            self.config = json.load(f)
        cfg = self.config["Reaction"]
        water_removal_dur = cfg["Water Removal Duration"]["Value"]
        self.set_active()
        self.set_peltiers(0)
        self.smc.set(self.get_idx(self.valve_vacuum), 1)
        time.sleep(0.4)
        self.smc.set(self.get_idx(self.valve_reactors), 1)
        status = self.wait(water_removal_dur)
        if status:
            return -1
        self.smc.set(self.get_idx(self.valve_vacuum + self.valve_reactors), 0)
        return 0
        
    def reaction(self):
        while True:
            if not self.panel.reaction.active:
                self.schematic.worker.set_running(False)
                if self.worker.requests.empty():
                    self.parent.stop()
                return
            with open(self.filename, "r") as f:
                self.config = json.load(f)
            cfg = self.config["Reaction"]
            reaction_temp = cfg["Reaction Temperature"]["Value"]
            reaction_dur = cfg["Reaction Duration"]["Value"]
            end_press_tol = cfg["End Pressure Tolerance"]["Value"]
            cooling_dur = cfg["Cooling Duration"]["Value"]
            if reaction_temp > 650:
                wait = threading.Event()
                self.worker.prompt.emit("Reaction temperature exceeds limit.", QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel, wait)
                wait.wait()
                if self.prompt_reply == QMessageBox.StandardButton.Retry:
                    continue
                elif self.prompt_reply == QMessageBox.StandardButton.Cancel:
                    self.parent.stop()
                    return -1 
            self.schematic.worker.set_running(True)
            self.panel.reaction.set_running(True)
            self.smc.close_all()
            self.set_active()
            self.smc.set(self.get_idx(self.valve_lift + self.valve_lines), 1)
            self.set_peltiers(1)

            while not self.panel.auto.running:
                self.worker.message.emit("")
                if not self.running:
                    return 
                time.sleep(1)
            self.worker.message.emit("Heating ovens")
            self.start_heaters(self.ovens, reaction_temp)
            while any(o.get_value() < reaction_temp for o in self.ovens):
                if not self.running:
                    return 
                time.sleep(1)

            while not self.panel.auto.running:
                self.worker.message.emit("")
                if not self.running:
                    return 
                time.sleep(1)
            self.worker.message.emit("Starting reaction")    
            end_time = time.time() + reaction_dur
            while time.time() < end_time:
                if not self.running:
                    return
                self.worker.message.emit(f"Reaction ({int(end_time - time.time())//60 + 1} min)")
                time.sleep(1)
            self.smc.set(self.get_idx(self.valve_lift), 0)
            self.stop_heaters(self.ovens)
            self.worker.message.emit("Saving")    
            self.parent.save(self.timestamp)

            self.worker.message.emit("Resting reactors")    
            status = self.wait(cooling_dur)
            if status:
                return

            for r in self.reactors:
                pressure_end = r.get_value()
                self.table.set_entry(int(pressure_end * 1000), r.id - 1, 5)
                self.table.set_entry(int(reaction_dur / 60), r.id - 1, 9)
                self.table.set_entry(self.timestamp, r.id - 1, 10)
            self.worker.message.emit("Saving")    
            self.parent.save(self.timestamp)
            self.table.store()

            if any(1000*r.get_value() > int(self.table.get_entry(r.id-1, 4)) - 3*int(self.table.get_entry(r.id-1, 2)) + 3*1000*end_press_tol for r in self.reactors):
                if not self.running:
                    return
                wait = threading.Event()
                self.worker.prompt.emit("Remaining pressure exceeds expectation.", QMessageBox.StandardButton.Ignore | QMessageBox.StandardButton.Cancel, wait)
                wait.wait()
                if self.prompt_reply == QMessageBox.StandardButton.Cancel:
                    return -1
                time.sleep(1)

            self.worker.message.emit("Removing water")
            status = self.remove_water()
            if status:
                return
            self.worker.message.emit("Saving")    
            self.parent.save(self.timestamp)

            self.smc.close_all()
            self.panel.reaction.set_running(False)
            self.parent.stop()
            return 

            

