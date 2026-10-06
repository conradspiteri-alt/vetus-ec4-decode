// EC4 sniffer enclosure rev B - houses the 88 x 74 mm L-shaped carrier PCB.
// Dr.FireFly.  Units mm.
// rev B changes: carrier widened to 88; lid screw bosses moved OUTSIDE the cavity
// (they fouled the carrier in rev A); DB9 fully enclosed, no external exposure;
// ONE USB opening only.
$fn = 48;

// ---------------- carrier + module data --------------------------------------
CAR_W   = 88.0;  CAR_D = 74.0;  CAR_T = 1.6;
NOTCH_X = 29.0;  NOTCH_Y = 63.5;
SEAT    = 2.5;                              // header seating height of every module

// Which DevKitC port gets the hole.  The module has two: "USB" (native, GPIO19/20)
// and "UART" (CH343 bridge).  UART auto-resets into the bootloader, so a sealed box
// never needs the BOOT button - but the firmware must then be built with
// "USB CDC On Boot: DISABLED" so Serial maps to UART0.
PORT = "UART";                              // "UART" or "USB"
PORT_X = (PORT == "UART") ? 21.0 : 10.0;    // centre, in carrier coords

// ---------------- enclosure parameters ----------------------------------------
CLR   = 0.4;
WALL  = 2.5; FLOOR = 2.5; LIDT = 2.5;
LEDGE = 2.0; LEDGE_Z = 5.0;
INT_W = CAR_W + CLR;  INT_D = CAR_D + CLR;  INT_H = 28.0;
SH_W  = INT_W + 2*WALL;  SH_D = INT_D + 2*WALL;          // shell 93.4 x 79.4
BOSS_D = 7.0; BOSS_OUT = 2.0;                            // boss centre, outside the shell face
SX = BOSS_D/2 + BOSS_OUT;  SY = SX;                      // shell origin within the part
EXT_W = SH_W + 2*SX;  EXT_D = SH_D + 2*SY;  EXT_H = FLOOR + INT_H + LIDT;
CX = SX + WALL + CLR/2;  CY = SY + WALL + CLR/2;         // carrier origin
CZ = FLOOR + LEDGE_Z;  BT = CZ + CAR_T;  MB = BT + SEAT;
BOSS = [[SX-BOSS_OUT, SY-BOSS_OUT], [EXT_W-SX+BOSS_OUT, SY-BOSS_OUT],
        [SX-BOSS_OUT, EXT_D-SY+BOSS_OUT], [EXT_W-SX+BOSS_OUT, EXT_D-SY+BOSS_OUT]];

function ex(x) = CX + x;
function ey(y) = CY + y;

// ---------------- carrier + modules, for fit check ----------------------------
module carrier() {
  color("#1d6b3a") linear_extrude(CAR_T) difference() {
    square([CAR_W, CAR_D]);
    translate([-1, NOTCH_Y]) square([NOTCH_X + 1, CAR_D - NOTCH_Y + 1]);
  }
}
module modules() {
  // ESP32-S3-DevKitC-1
  color("#2b4a7a") translate([2, 0, 0]) cube([26, 70, 1.6]);
  color("#3a3a3a") translate([4, 55, 1.6]) cube([22, 15, 3.4]);
  color("#b0b0b0") translate([6, -0.5, 1.6]) cube([8, 7, 3.2]);      // USB (native)
  color("#b0b0b0") translate([17, -0.5, 1.6]) cube([8, 7, 3.2]);     // UART
  // SK Pang ISO1050 - connectors now sit fully over the carrier
  color("#2b4a7a") translate([31, 0, 0]) cube([50, 47, 1.6]);
  color("#1b1b1b") translate([76, 20, 1.6]) cube([10, 16, 12.5]);    // DB9, enclosed
  color("#1b1b1b") translate([76, 4, 1.6]) cube([10, 13, 9.5]);      // CAN screw terminal
  color("#2a2a2a") translate([34, 26, 1.6]) cube([14, 12, 10.0]);    // isolated DC-DC
  // microSD
  color("#2b4a7a") translate([31, 49, 0]) cube([35, 25, 1.6]);
  color("#8a8a8a") translate([36, 56, 1.6]) cube([28, 12, 2.2]);
  color("#d07a2a") translate([64, 57.5, 2.0]) cube([4, 11, 1.0]);
  // through-hole 5 V block
  color("#1b4f9c") translate([69, 47.9, 0]) cube([9.5, 10.7, 9.0]);            // J2
  color("#3a3a3a") translate([69.54, 59.5, 0]) cylinder(d=8, h=4);             // F1 PTC
  color("#101010") translate([71.56, 69.1, 0]) cube([5.5, 2.8, 2.8]);          // D2
  color("#101010") translate([80.9, 59.33, 0]) cube([3.2, 6.5, 3.2]);          // D1
  color("#1b1b3a") translate([80.75, 66.75, 0]) cylinder(d=6.5, h=11);         // C1
  color("#7a5a20") translate([83.75, 51.29, 0]) cube([3.5, 5.5, 4]);           // C2
}
module assembly_modules() { translate([ex(0), ey(0), MB]) modules(); }

// ---------------- openings -----------------------------------------------------
module cut_port() translate([ex(PORT_X) - 6, SY - 1, MB - 1.0]) cube([12, WALL + 2, 9.0]);
module cut_can()  translate([ex(CAR_W) - 3, ey(2.5), MB + 0.5]) cube([WALL + 8, 16, 11.0]);
module cut_pwr()  translate([ex(CAR_W) - 3, ey(46.5), MB - 0.5]) cube([WALL + 8, 13, 10.0]);

// ---------------- base ----------------------------------------------------------
module base() {
  difference() {
    union() {
      difference() {
        translate([SX, SY, 0]) cube([SH_W, SH_D, FLOOR + INT_H]);
        translate([SX + WALL, SY + WALL, FLOOR]) cube([INT_W, INT_D, INT_H + 1]);
      }
      // carrier support ledge
      translate([SX + WALL, SY + WALL, FLOOR]) difference() {
        cube([INT_W, INT_D, LEDGE_Z]);
        translate([LEDGE, LEDGE, -1]) cube([INT_W - 2*LEDGE, INT_D - 2*LEDGE, LEDGE_Z + 2]);
      }
      // EXTERNAL corner bosses - clear of the cavity, so they cannot foul the carrier
      for (p = BOSS) translate([p[0], p[1], 0]) cylinder(d = BOSS_D + 3, h = FLOOR + INT_H);
      for (p = BOSS) hull() {
        translate([p[0], p[1], 0]) cylinder(d = BOSS_D + 3, h = 3);
        translate([SX + SH_W/2, SY + SH_D/2, 0]) cylinder(d = 1, h = 3);
      }
    }
    for (p = BOSS) translate([p[0], p[1], FLOOR + INT_H - 7]) cylinder(d = 4.0, h = 8);
    cut_port(); cut_can(); cut_pwr();
    // ledge relief under the SK Pang connectors and the tall 5 V parts
    translate([ex(74), ey(1), FLOOR]) cube([16, 46, LEDGE_Z + 0.1]);
    for (i = [0:5]) translate([SX + 20 + i*9, SY + SH_D/2 - 12, -1]) cube([3, 24, FLOOR + 2]);
  }
}

// ---------------- lid ------------------------------------------------------------
module lid() {
  RIB = (FLOOR + INT_H) - BT - 1.5;          // stop 1.5 mm above the carrier; EVA foam closes it
  difference() {
    union() {
      translate([SX, SY, 0]) cube([SH_W, SH_D, LIDT]);
      for (p = BOSS) translate([p[0], p[1], 0]) cylinder(d = BOSS_D + 3, h = LIDT);
      for (p = BOSS) hull() {
        translate([p[0], p[1], 0]) cylinder(d = BOSS_D + 3, h = LIDT);
        translate([SX + SH_W/2, SY + SH_D/2, 0]) cylinder(d = 1, h = LIDT);
      }
      // location lip into the cavity
      translate([SX + WALL + 0.25, SY + WALL + 0.25, -2.0]) difference() {
        cube([INT_W - 0.5, INT_D - 0.5, 2.0]);
        translate([1.6, 1.6, -1]) cube([INT_W - 3.7, INT_D - 3.7, 4]);
      }
      // hold-down rib on the carrier's free left edge, plus four pads
      translate([ex(0.1), ey(2), -RIB]) cube([2.2, 59, RIB]);
      for (p = [[29.1, 0.4], [29.1, 71.4], [85.9, 0.6], [85.9, 44.4]])
        translate([ex(p[0]), ey(p[1]), -RIB]) cube([2.2, 2.8, RIB]);
    }
    for (p = BOSS) translate([p[0], p[1], -3]) {
      cylinder(d = 3.4, h = LIDT + 6);
      translate([0, 0, 3 + LIDT - 1.4]) cylinder(d = 6.2, h = 3);
    }
    // RGB status LED window, thinned to 0.6 mm
    translate([ex(4), ey(6), 0.6]) cube([18, 12, LIDT]);
  }
}

// ---------------- scenes -----------------------------------------------------------
MODE = 0;   // 0 exploded, 1 closed, 2 base+carrier, 3 base only, 4 lid only
if (MODE == 0) {
  base(); translate([ex(0), ey(0), CZ]) carrier(); assembly_modules();
  translate([0, 0, FLOOR + INT_H + 24]) lid();
} else if (MODE == 1) {
  base(); translate([ex(0), ey(0), CZ]) carrier(); assembly_modules();
  translate([0, 0, FLOOR + INT_H]) lid();
} else if (MODE == 2) {
  base(); translate([ex(0), ey(0), CZ]) carrier(); assembly_modules();
} else if (MODE == 3) { base(); } else { lid(); }
