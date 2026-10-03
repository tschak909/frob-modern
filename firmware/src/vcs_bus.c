// Core 1: the Atari 2600 cartridge port, through the FROB cable.
//
// The cart port has no clock and no R/W: the card sees A0-A11 and /CE (A12
// inverted on the cable adapter) and must put RAM[A11..A0] on D0-D7 while /CE
// is low.  So, as every RP2040/STM32 2600 cart does (PlusCart, UnoCart):
// wait for a stable address, drive the byte, repeat.  The data '245's /OE is
// /CE | V_DOE in hardware, so while the 2600 owns the RAM the RP keeps V_DOE
// low and just keeps GP24-31 up to date; the buffer opens and closes with /CE.
//
// The port registers have side effects (mailbox flags), so for them an
// address only counts once it has been stable for STABLE_LOOPS samples:
// the 6507 holds an address for ~800 ns, while a transition can show a
// passing value for a few tens of ns.  The original's decoder had no such
// filter (only an RC on /CE) -- one likely source of its reported flakiness.
#include "frob.h"

#include "hardware/structs/sio.h"
#include "hardware/sync.h"

#define HI_CE    (1u << VCS_HI_CE_BIT)
#define DOE_BIT  (1u << (VCS_DOE_PIN - 32))   // gpio_hi_* registers: bit n = GPIO 32+n
#define DIR_BIT  (1u << (VCS_DIR_PIN - 32))

#ifndef STABLE_LOOPS
#define STABLE_LOOPS 4          // x ~25-30 ns per sample at 150 MHz: >= ~100 ns
#endif

static inline uint32_t vcs_in(void) { return sio_hw->gpio_hi_in & (VCS_HI_ADDR_MASK | HI_CE); }

static inline void drive(uint8_t v) {
    sio_hw->gpio_togl = (sio_hw->gpio_out ^ ((uint32_t)v << VCS_DATA_PIN)) & VCS_DATA_MASK;
}

void __not_in_flash_func(vcs_bus_loop)(void) {
    (void)save_and_disable_interrupts();
    // idle state: buffer closed, direction card -> 2600, GP24-31 driving the '245 A side
    sio_hw->gpio_hi_set = DOE_BIT | DIR_BIT;
    sio_hw->gpio_oe_set = VCS_DATA_MASK;
    uint8_t owned = 0;
    uint32_t addr = 0xffffffffu, prev;
    for (;;) {
        do {                                    // a stable address: two equal samples
            prev = addr;
            addr = vcs_in();
        } while (addr != prev);

        const uint8_t ctrl = frob.ctrl;
        const uint8_t own = frob_vcs_owns(ctrl);
        if (own != owned) {                     // ownership follows the Apple's control register
            owned = own;
            if (own)
                sio_hw->gpio_hi_clr = DOE_BIT;
            else
                sio_hw->gpio_hi_set = DOE_BIT;
        }
        if (addr & HI_CE)                       // not a cartridge access (buffer closed by /CE)
            continue;
        const uint16_t a = (uint16_t)addr;
        const vcs_kind_t k = frob_vcs_decode(ctrl, a);
        if (k == VCS_FLOAT)
            continue;
        drive(frob_vcs_value(&frob, k, a));     // ROM / status / mailbox: on the bus at once
        if (k == VCS_ROM)
            continue;

        if (k == VCS_PORT_WR) {
            // $FFF0: the 6507 drives the bus.  Stop driving, turn the buffer round,
            // and sample until the address moves; keep the next-to-last sample
            // (the last one may already be the next cycle's), as PlusCart does.
            sio_hw->gpio_hi_set = DOE_BIT;
            sio_hw->gpio_oe_clr = VCS_DATA_MASK;
            sio_hw->gpio_hi_clr = DIR_BIT;
            sio_hw->gpio_hi_clr = DOE_BIT;
            uint32_t n = 0, d = 0, dprev = 0;
            while (vcs_in() == addr) {
                dprev = d;
                d = sio_hw->gpio_in;
                n++;
            }
            sio_hw->gpio_hi_set = DOE_BIT;
            sio_hw->gpio_hi_set = DIR_BIT;
            sio_hw->gpio_oe_set = VCS_DATA_MASK;
            if (owned)
                sio_hw->gpio_hi_clr = DOE_BIT;
            if (n >= STABLE_LOOPS)
                frob_vcs_done(&frob, k, (uint8_t)(dprev >> VCS_DATA_PIN));
        } else {
            uint32_t n = 0;
            while (vcs_in() == addr) {
                if (k == VCS_PORT_STAT)         // a flag may change mid-access: keep it current
                    drive(frob_vcs_status(&frob));
                n++;
            }
            if (n >= STABLE_LOOPS)
                frob_vcs_done(&frob, k, 0);
        }
        addr = 0xffffffffu;
    }
}
