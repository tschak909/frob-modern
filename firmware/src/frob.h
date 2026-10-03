// Frob2354 firmware: shared declarations.
#ifndef FROB_H
#define FROB_H

#include "hardware/sync.h"
// RP2350: both cores see SRAM coherently; order the data byte before its flag
#define FROB_PUBLISH_BARRIER() __dmb()

#include "frob_logic.h"
#include "frob_pins.h"

extern frob_t frob;

void apple_bus_loop(void);      // core 0, never returns
void vcs_bus_loop(void);        // core 1, never returns
void frob_ctrl_changed(void);   // core 0, after the Apple wrote a new control value

#endif
