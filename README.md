# AD985x-Utility for Raspberry Pi

![](D:\GitHub\AD985x-Utility\RPi-driving-AD9850&51.jpg)\
Test set up\
\
An interactve utility for the AD9850 and AD9851 VCO-modules written in Python.\
This utility covers all AD9850 & AD9851 chip options.\
Program can be configured to run on the RPI, or on remote host via gpiozero.
For configuration see comments in the header of the program.

User functions:

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
- h: help
