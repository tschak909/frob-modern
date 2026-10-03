// Frob2354: the FROB Apple II card (Frobco, 1982) on one RP2354B.
//
// Core 0 serves the Apple II slot (apple_bus.c), core 1 the Atari 2600 cable
// (vcs_bus.c); both run from SRAM with interrupts off.  The 4 KB FROB RAM, the
// control register and the two mailbox registers live in `frob` (frob_logic.h).
// USB is not used at run time: firmware updates go through BOOTSEL (hold
// BOOTSEL, press RESET, copy the UF2) or SWD.
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/vreg.h"

#include "frob.h"

#ifndef FROB_SYS_KHZ
#define FROB_SYS_KHZ 150000     // RP2350 nominal; see firmware/README.md for timing margins
#endif

frob_t frob;

void frob_ctrl_changed(void) {
    // LED on while the 2600 owns the RAM
    if (frob_vcs_owns(frob.ctrl))
        sio_hw->gpio_set = 1u << LED_PIN;
    else
        sio_hw->gpio_clr = 1u << LED_PIN;
}

static void pin_in(unsigned pin) {
    gpio_init(pin);
    gpio_disable_pulls(pin);    // RP2350-E9: no internal pull-downs on bus inputs
    gpio_set_input_hysteresis_enabled(pin, true);
}

static void pin_out(unsigned pin, bool level) {
    gpio_init(pin);
    gpio_disable_pulls(pin);
    gpio_put(pin, level);
    gpio_set_dir(pin, GPIO_OUT);
    gpio_set_slew_rate(pin, GPIO_SLEW_RATE_FAST);
}

static void pins_init(void) {
    // buffer enables first, inactive (the boards' 10k pull-ups hold them so through reset)
    pin_out(A2_DOE_PIN, 1);
    pin_out(VCS_DOE_PIN, 1);
    pin_out(VCS_DIR_PIN, 1);
    for (unsigned i = 0; i < 8; i++) {
        pin_out(A2_DATA_PIN + i, 0);        // '245 A sides: driven while the buffers are closed
        pin_out(VCS_DATA_PIN + i, 0);
        pin_in(A2_ADDR_PIN + i);
    }
    for (unsigned i = 0; i < 12; i++)
        pin_in(VCS_ADDR_PIN + i);
    pin_in(A2_RW_PIN);
    pin_in(A2_IOSEL_PIN);
    pin_in(A2_DEVSEL_PIN);
    pin_in(A2_PHI0_PIN);
    pin_in(A2_RES_PIN);
    pin_in(VCS_CE_PIN);
    pin_in(VCS_PRESENT_PIN);
    pin_out(LED_PIN, 0);
    pin_out(SPARE_PIN, 0);
}

int main(void) {
#if FROB_SYS_KHZ > 150000
    vreg_set_voltage(VREG_VOLTAGE_1_15);
    sleep_ms(2);
#endif
    set_sys_clock_khz(FROB_SYS_KHZ, true);
    frob_reset(&frob);
    pins_init();
    multicore_launch_core1(vcs_bus_loop);
    apple_bus_loop();
}
