// Core 0: the Apple II slot.
//
// /DEVSEL and /IOSEL are already PHI0-qualified by the Apple (low only in
// PHI0-high of a cycle that addresses this slot), and A0-A7 and R/W are
// stable by then.  A 6502 read must have data on the bus before PHI0 falls
// (~490 ns after it rose; ~100 ns setup), so the loop below has a few hundred
// ns to answer -- it needs well under 100 ns at 150 MHz.
//
// The data '245 is DIR = R/W in hardware and its /OE = (/IOSEL & /DEVSEL) |
// A2_DOE: it can only be enabled while one of our selects is low, whatever
// this code does.  Order of operations keeps the RP pins and the buffer from
// ever driving each other: GP0-7 change direction only while A2_DOE is high.
#include "frob.h"

#include "hardware/structs/sio.h"
#include "hardware/sync.h"

#define SEL_MASK ((1u << A2_IOSEL_PIN) | (1u << A2_DEVSEL_PIN))
#define DOE_BIT  (1u << A2_DOE_PIN)

void __not_in_flash_func(apple_bus_loop)(void) {
    (void)save_and_disable_interrupts();
    sio_hw->gpio_set = DOE_BIT;
    for (;;) {
        uint32_t in;
        while (((in = sio_hw->gpio_in) & SEL_MASK) == SEL_MASK)
            ;
        in = sio_hw->gpio_in;                   // one more look: past any edge skew
        const bool iosel = !(in & (1u << A2_IOSEL_PIN));
        const uint32_t sel_bit = iosel ? (1u << A2_IOSEL_PIN) : (1u << A2_DEVSEL_PIN);
        const uint8_t a = (uint8_t)(in >> A2_ADDR_PIN);

        if (in & (1u << A2_RW_PIN)) {           // 6502 read
            uint8_t v;
            if (frob_apple_read(&frob, iosel, a, &v)) {
                sio_hw->gpio_togl = (sio_hw->gpio_out ^ ((uint32_t)v << A2_DATA_PIN)) & A2_DATA_MASK;
                sio_hw->gpio_oe_set = A2_DATA_MASK;
                sio_hw->gpio_clr = DOE_BIT;
            }
            while (!(sio_hw->gpio_in & sel_bit))
                ;
            sio_hw->gpio_set = DOE_BIT;
            frob_apple_read_done(&frob, iosel, a);
        } else {                                // 6502 write: the '245 drives Apple -> RP
            sio_hw->gpio_oe_clr = A2_DATA_MASK;
            sio_hw->gpio_clr = DOE_BIT;
            uint32_t s, last = 0;
            // keep the last sample taken while the select was still low: the
            // original latches on the strobe's trailing edge
            while (!((s = sio_hw->gpio_in) & sel_bit))
                last = s;
            sio_hw->gpio_set = DOE_BIT;
            const uint8_t before = frob.ctrl;
            frob_apple_write(&frob, iosel, a, (uint8_t)(last >> A2_DATA_PIN));
            if (!iosel && !(a & 1) && frob.ctrl != before)
                frob_ctrl_changed();
        }
    }
}
