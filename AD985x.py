
""" Version 0.1 - working prototype, must be refactored including the documentation.
    Utility for the AD9850/1 VCO (Voltage Controlled Oscillator) - module, connected to GPIO of Rpi.
    Supports all functions of the VCO - in serial mode. For hardware config see specs
    Program may configured to run on RPI or on master, connected to local network """

from math import pow, log10 as lg
import os, sys

# To install gpiozero for acces gpio-pins see:
# https://gpiozero.readthedocs.io/en/stable/remote_gpio.html#preparing-the-control-computer
from gpiozero import LED

# *** CONFIGURATION ***

# RPI: for remote access enable or install Remote GPIO to allow communication via daemon
# sudo systemctl start pigpiod      => run daemon once
# sudo systemctl enable pigpiod     => run daemon at (re)boot

# used VCO's.
# WARNING configuring a D9850 as AD9851 may unintentionally set Factory Reserved Codes
VCO_A = "AD9851" # or "AD9850"
VCO_B = "AD9850" # or "AD9851" or None

# Max VCO-clock at 5V supply voltage, but be aware of RPi 3,3V limit for GPIO-pins.
# No problem encountered with 5V supply when only connecting the input pins of VCO to RPi.
AD9851_clock = 30000000     # default (and max for 5 volt supply) crystal frequency AD9851
AD9850_clock = 125000000    # default (and max for 5 volt supply) crystal frequency AD9850

# Pin factories see: https://gpiozero.readthedocs.io/en/stable/api_pins.html
# uncomment JUST ONE pin factory:
# 
# pin_factory = "rpigpio" # When program runs on RPi, is DFAULT pin factory (uses RPI.GPIO lib)
# pin_factory = "mock"    # emulates gpio pins for test purposes
pin_factory = "pigpio"  # for remote connection see:
                          # https://gpiozero.readthedocs.io/en/stable/remote_gpio.html      

# Remote acces: fill in ip address of RPi for pigpio of wifi / utp cable connection
ip_addr="192.168.1.46"

# gpio interface wth VCO module (use gpio numbers, not physical pin numbers)
gif_A = dict(RESET=22, W_CLK=23, FQ_UD=24, DATA=25)

# gpio interface second VCO if connected
gif_B = dict(RESET=26, W_CLK=17, FQ_UD=27, DATA=6)

start_freq = 1000 # Initial frequentie VCO

#*** END CONFIGURATION ***

class PrgrsBar:
    def __init__(self, bar_len = 50, bar_char='-', limit_char = '|'):
        self.bar_len = bar_len
        self.bar_char = bar_char
        self.limit_char = limit_char
        self.cur_len = 0
        self.ref_bar = False

    def _ref_bar_init(self):
            print(f"{self.limit_char}{self.bar_len*self.bar_char}{self.limit_char}")
            print('>', end = '')
            self.cur_len = 0
            self.ref_bar = True

    def prgrs(self, fraction):
        if fraction < 0 or fraction > 1:
                return False
        if self.ref_bar:
            self.bar_val = int(fraction * self.bar_len)
            if self.bar_val > self.cur_len:
                print(f"{(self.bar_val - self.cur_len) * self.bar_char}", end = '')
                self.cur_len = self.bar_val
                if self.cur_len >= self.bar_len:
                    print('<')
                    self.cur_len = 0
                    self.ref_bar = False
        else:
            self._ref_bar_init()
            self.ref_bar = True
        return True

class parse():  # parse and execute user commands
    # multiply factors for values
    mulfactors = {'k':1000, 'K':1000, 'm':1000000, 'M':1000000, 'c':0.01, 'C':0.01}
    
    def __init__(self, system_interface1, system_interface2):
        self.cmds = dict(c=self.config, f=self.freq, h=self.help, r=self.reset, i=self.idle_mode, \
                         s=self.sweep, l=self.lsweep, q=self.quit,w=self.restore_reg, \
                         p=self.phase_shift, m=self.multiplier, a=self.a_VCO, b=self.b_VCO)

        self.pb = PrgrsBar() # Progress bar for frequency sweep
        
        self.sif_A = system_interface1
        self.sif_B = system_interface2
        self.sif = self.sif_A
    
        if self.sif_B != None:
            self.prompt = 'A'
            self.cmds.update(e=self.exchange)
        else: self.prompt = ""
        
    def isreal(self, s): # value is real number - test
        try:
            x = float(s)
            return x
        except: return None

    def param_val(self, s): # convert number string to real number
        for i in self.mulfactors.keys():
            if i in s:
                s = s.replace(i ,"", -1)
                value = self.isreal(s.strip())
                if value != None:
                    return  value * self.mulfactors[i]
                else: return None
                
        return self.isreal(s.strip())
    
    def xqt_cmd(self, cmd):
        # treat single number as frequency command (add 'f' to number string)
        if cmd[0].isdigit() or cmd[0] == '.':
            cmd = 'f'+ cmd

        if cmd[0].lower() in self.cmds.keys(): # ==> execute command
            if not self.cmds[cmd[0].lower()](cmd):
                print(f"Error in cmd: {cmd}")
        else:
            print(f"Invalid cmd: {cmd}")


    def get_cmd(self): # get and execute user command
        print("enter command (h for help):")
        while True:
            user_input = input(f"{self.prompt}?").strip()
            if user_input == "":
                continue
            
            self.xqt_cmd(user_input.strip())

    # General user functions to execute
    def a_VCO(self, cmd):
        saved = self.sif
        self.sif = self.sif_A
        if len(cmd) > 1:
            self.xqt_cmd(cmd[1:].strip())
        self.sif = saved
        return True

    def b_VCO(self, cmd):
        saved = self.sif
        self.sif = self.sif_B
        if len(cmd) > 1:
            self.xqt_cmd(cmd[1:].strip())
        self.sif = saved
        return True
    
    def exchange(self, cmd):
        if self.prompt == 'A':
            self.prompt = 'B'
            self.sif = self.sif_B
        else:
            self.prompt = 'A'
            self.sif = self.sif_A
        return True
        
    def sweep(self, cmd): # frequency sweep
        params  = cmd[1:].strip().split()
        if len(params) == 3:
            values = []
            try:
                values = [self.param_val(i) for i in params]
            except:
                return False
            f_start = values[0]; f_end = values[1]; f_incr = values[2]
            if f_start < f_end:
                print(f'Sweep {f_start} {f_end} {f_incr}')
                f = f_start
                f_range = f_end - f_start
                while True:
                    f = f if f <= f_end else f_end
                    self.sif.set_freq(f)
                    self.pb.prgrs((f-f_start)/f_range)
                    if f >= f_end:
                        break
                    f += f_incr
                return True
        return False

    def lsweep(self, cmd): # logarithmic (exponential) frequency sweep
        params  = cmd[1:].strip().split()
        if len(params) == 3:
            values = []
            try:
                values = [self.param_val(i) for i in params]
            except:
                return False
            
            f_start = values[0]; f_end = values[1]; f_steps = int(values[2])
            exp_start = lg(f_start)
            exp_end = lg(f_end)
            exp_range = exp_end - exp_start
            exp_incr = exp_range / f_steps
            print(f'Sweep {f_start} {f_end} {f_steps}')
            f=pow(10,exp_start)
            exp = exp_start

            for step in range(f_steps+1):
                self.sif.set_freq(f)
                self.pb.prgrs((step)/f_steps)
                exp += exp_incr
                f = pow(10, exp)
            return True
        else:
            return False
    
    def quit(self, cmd): # end program
        if len(cmd) == 1:
            sys.exit()
        return False

    def config(self, cmd):
        self.sif.show_config()
        return True
        
    def help(self, cmd):
        print("""
   Command letters may be upper or lower case
   -----------------------------------------
   - a: VCO A prefix, xqt command once for VCO A - example B?af 1000
   - b: VCO B prefix, xqt command once for VCO B - example A?bf 1000
   - e: change default VCO (VCO A <=> VCO B)
   - f: frequency: f freq# or freq#[k-kHz, m-mHz, c-1/100Hz] - examples: f100k ; 1m
   - s: sweep freq: s start freq, end freq, delta freq - example: s 1000 1m 100k
   - l: log (exp) sweep: l start freq, end freq, number of steps - l 20 20k 20
   - m: set/reset frequency multiplier: (AD9851 only, may harm AD9850!): m+ / m-
   - p: set phase shift (0..31 X 11.25 degrees): p number[0..31] - example: p 23
   - i: set/reset idle (power) mode: i+ / i-
   - r: reset frequency generator AND clears VCO-register
   - w: write register (restore VCO register value)
   - c: show current configuration settings
   - q: quit program
   - h: This help function: h\n""")
        return True

    # logical AD98x chip-functions to execute      
    def freq(self, cmd): # set frequency
        self.freq = self.param_val(cmd[1:].strip())
        if self.freq != None:
            return self.sif.set_freq(self.freq)
        else:
            return False

    def idle_mode(self, cmd):
        if '+' in cmd:
            return self.sif.set_pwr_sleep(1)

        elif '-' in cmd:
            return self.sif.set_pwr_sleep(0)

        return False
            
    def phase_shift(self, cmd):
        phase = self.param_val(cmd[1:].strip())
        print("phase: ", phase)
        if phase != None and phase in range(32):
            return self.sif.set_phase_shift(int(phase))
        return False

    def multiplier(self, cmd):
        print("multiplier set/reset")
        if '+' in cmd:
            return self.sif.set_multiplier(1)
        elif '-' in cmd:
            return self.sif.set_multiplier(0)
        else: return False

    def reset(self, cmd):
        return self.sif.reset()

    def restore_reg(self,cmd):
        return self.sif.set_reg_vals()
        
#=========================== low level IO functions

class CntrlFunctions(): # low level io interface functions
    def __init__(self):
        self.reset()
        self.resetpin.off()
        self.w_clk.off()
        self.data.off()
        self.fq_ud.off()

    def pulse(self, pin): # simple pulse 
        pin.on()
#        pin.on() # repeat when pulse width is too short
        pin.off()

    def reset(self):
        self.pulse(self.resetpin)
        self.write_reg(0,0) # define register value, undefined control bits may harm chip
        return True

    def write_reg(self, word, byte): # write control byte and frequency word bit for bit to chip

        for i in range (32):
            if word & 0x01: self.data.on()
            else: self.data.off()
            word = word >> 1
            self.pulse(self.w_clk)
        
        for i in range (8):
            if byte & 0x1: self.data.on()
            else: self.data.off()
            byte = byte >> 1
            self.pulse(self.w_clk)
            
        self.pulse(self.fq_ud)
        return True

class GpioADxIf(CntrlFunctions): # set IO paramters
    def __init__(self, params):
        self.resetpin = LED(params["RESET"])
        self.w_clk = LED(params["W_CLK"])
        self.fq_ud = LED(params["FQ_UD"])
        self.data = LED(params["DATA"])
        super().__init__()

#================= logical functions for AD98x chip

class AD98x():
    def __init__(self, iface):
        self.clock_freq = self.sys_clock
        self.freq_word = 0x0
        self.phase_shift = 0
        self.iface = iface
#        self.reset  # for test

    def show_config(self): # current status of AD98x
        print(self.ic_name)
        print(f"Register: {self.ctl_byte:02X} - {self.freq_word:08X}")
        print(f"Frequency input / real: {self.frequency:.2f} / {round(self.freq_word*self.clock_freq/4294967296, 2):.2f}")
        print(f"Phase shift: {self.ctl_byte >> 3} = {(self.ctl_byte >> 3)*11.25} degrees")
        print("Multiplier bit: ", end = "")
        if self.ic_name == "AD9851":print(self.ctl_byte & 0x1)
        else: print("-")
        print(f"Clock frequency: {self.clock_freq}")
        print(f"Power mode: {self.ctl_byte & 0x4:1X}")

    def reset(self):
        self.iface.reset()
        return True

    def set_freq(self, freq):
        self.frequency = freq
        self.freq_word = int((freq/self.clock_freq)*4294967296) & 0xFFFFFFFF
        self.iface.write_reg(self.freq_word, self.ctl_byte)
        return True

    def set_pwr_sleep(self, sleep_bit):
        print("Set to sleep set to ", sleep_bit)
        if sleep_bit:
            self.ctl_byte |= 0x04
        else:
            self.ctl_byte &= 0xFB
            self.iface.reset()
            
        self.iface.write_reg(self.freq_word, self.ctl_byte & self.ctl_mask)
        return True

    def set_multiplier(self, mp_bit):
        if mp_bit:
            self.ctl_byte |= 0x01
            self.clock_freq = 6 * self.sys_clock
        else:
            self.ctl_byte &= 0xFE
            self.clock_freq = self.sys_clock

        self.set_freq(self.frequency)
        return True
        
    def set_phase_shift(self, n):
        self.phase_shift = n
        self.ctl_byte = (self.ctl_byte & 0x07 | n << 3) & self.ctl_mask
        self.iface.write_reg(self.freq_word, self.ctl_byte)
        return True

    def set_reg_vals(self):
        print(f"{self.ctl_byte:02X} {self.freq_word:08X}")
        self.iface.write_reg(self.freq_word, self.ctl_byte)
        return True

class AD9851(AD98x): # parameters for AD9851
    ic_name = 'AD9851'
    sys_clock = AD9851_clock
    
    def __init__(self, iface):
        super().__init__(iface)
        self.ctl_byte = 0x01 # set multiplier bit
        self.clock_freq = 6 * self.sys_clock
        self.ctl_mask = 0xFD # to ensure ctrl bit 1 == 0
        self.set_freq(start_freq)
        
class AD9850(AD98x): # parameters for AD9850
    ic_name = 'AD9850'
    sys_clock = AD9850_clock
    
    def __init__(self, iface):
        super().__init__(iface)
        self.ctl_byte = 0x0
        self.ctl_mask = 0xFC # to ensure ctrl bit 0 and 1 == 0
        self.set_freq(start_freq)

    def set_multiplier(self, n):
        print("Error: multiplier bit not allowed for ", AD9850.ic_name)
        return True
        
#=======================

def main():
    if pin_factory != "rpigpio":
        os.environ["GPIOZERO_PIN_FACTORY"] = pin_factory
        os.environ["PIGPIO_ADDR"] = ip_addr
    else:
        pass # do nothing - rpigpio is default pin factory
    
    # system interface A or B: logical functions AD98x and low level IO

    if VCO_A == "AD9851":
        sif_A = AD9851(GpioADxIf(gif_A))
    else:
        sif_A = AD9850(GpioADxIf(gif_A)) 

    if VCO_B != None:
        if VCO_B == "AD9851":
            sif_B = AD9851(GpioADxIf(gif_B))  # sif system interface RPi - VCO
        else:
            sif_B = AD9850(GpioADxIf(gif_B))
    
    ## user interface
    uif = parse(sif_A, sif_B)
    # start program
    uif.get_cmd()
    
if __name__ =='__main__':
    main()
