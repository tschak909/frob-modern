// FROB register semantics, shared by the firmware (apple_bus.c, vcs_bus.c)
// and the host tests (../test).  Pure C, no SDK dependencies.
//
// Reference: the reverse-engineered FROB card (retroabandon/apple2-re
// frob/hwdoc/theory.md, memory-map.md, kicad/a2board) and MAME's a2frob.cpp.
//
//   Apple $C0n0 write  D0-D3 page, D4 RAM to the 2600, D5 bidirectional port
//                      enable (U17 '174 latches D0-D5; D6/D7 ignored)
//   Apple $C0n0 read   D7 = Apple may write (2600 mailbox empty),
//                      D6 = Apple may read (Apple mailbox full)
//   Apple $C0n1 write  2600 mailbox <- data; '2600 full' set (U4 '374 + U1A, latched
//                      at the end of the cycle)
//   Apple $C0n1 read   <- Apple mailbox; 'Apple full' cleared by the access itself
//                      (U1B async clear), so 6502 dummy reads clear it too
//   (A0 is the only register address bit: $C0n0-$C0nF mirror the pair.)
//   Apple $Cn00-$CnFF  RAM[page * 256 + A7..A0] while the Apple owns the RAM;
//                      nothing drives the bus otherwise
//   2600 /CE low       RAM[A11..A0] while the 2600 owns the RAM; with the port
//                      enabled as well (U10A: both bits), $FFF0-$FFF2 are the port:
//                      $FFF0 write -> Apple mailbox, 'Apple full' set when the access ends
//                      $FFF1 read  D7 = 2600 may write (Apple mailbox empty),
//                                  D6 = 2600 may read (2600 mailbox full)
//                      $FFF2 read  <- 2600 mailbox, '2600 full' cleared
//                      ($FFF3 is RAM again.)  The 2600 cart port has no R/W line:
//                      any $FFF0 access is a write, as on the original.
#ifndef FROB_LOGIC_H
#define FROB_LOGIC_H

#include <stdbool.h>
#include <stdint.h>

#define FROB_CTRL_PAGE   0x0f
#define FROB_CTRL_VCS    0x10   // 1: RAM assigned to the 2600
#define FROB_CTRL_BIDIR  0x20   // 1: bidirectional port enabled (only counts with FROB_CTRL_VCS)
#define FROB_CTRL_MASK   0x3f

typedef struct {
    uint8_t mem[4096];
    volatile uint8_t ctrl;            // U17: page, owner, port enable
    volatile uint8_t byte_for_vcs;    // U4:  Apple -> 2600
    volatile uint8_t byte_for_apple;  // U14: 2600 -> Apple
    volatile uint8_t vcs_full;        // U1A: set by the Apple's write, cleared by the 2600's read
    volatile uint8_t apple_full;      // U1B: set by the 2600's write, cleared by the Apple's read
} frob_t;

// Cross-core ordering: data byte before the flag that publishes it.
#ifndef FROB_PUBLISH_BARRIER
#define FROB_PUBLISH_BARRIER() __asm__ volatile("" ::: "memory")
#endif

static inline void frob_reset(frob_t *f) {
    for (unsigned i = 0; i < sizeof f->mem; i++)
        f->mem[i] = 0;
    f->ctrl = 0;                    // Apple owns the RAM, page 0, port off
    f->byte_for_vcs = f->byte_for_apple = 0;
    f->vcs_full = f->apple_full = 0;
}

static inline bool frob_vcs_owns(uint8_t ctrl) { return ctrl & FROB_CTRL_VCS; }
static inline bool frob_port_on(uint8_t ctrl) {
    return (ctrl & (FROB_CTRL_VCS | FROB_CTRL_BIDIR)) == (FROB_CTRL_VCS | FROB_CTRL_BIDIR);
}

// ---- Apple side -----------------------------------------------------------
// iosel: true for $Cn00-$CnFF (/I/O SELECT), false for $C0n0-$C0nF (/DEVICE SELECT)

static inline uint8_t frob_apple_status(const frob_t *f) {
    return (f->vcs_full ? 0 : 0x80) | (f->apple_full ? 0x40 : 0);
}

// A 6502 read: returns true (and *out) if the card drives the bus.  No side effects.
static inline bool frob_apple_read(const frob_t *f, bool iosel, uint8_t a, uint8_t *out) {
    if (iosel) {
        uint8_t c = f->ctrl;
        if (frob_vcs_owns(c))
            return false;
        *out = f->mem[((c & FROB_CTRL_PAGE) << 8) | a];
        return true;
    }
    *out = (a & 1) ? f->byte_for_apple : frob_apple_status(f);
    return true;
}

// Side effects of a 6502 read, applied when the access ends.
static inline void frob_apple_read_done(frob_t *f, bool iosel, uint8_t a) {
    if (!iosel && (a & 1))
        f->apple_full = 0;
}

// A 6502 write, applied when the access ends (the original latches on the
// trailing edge of the decoded strobe).
static inline void frob_apple_write(frob_t *f, bool iosel, uint8_t a, uint8_t d) {
    if (iosel) {
        uint8_t c = f->ctrl;
        if (!frob_vcs_owns(c))
            f->mem[((c & FROB_CTRL_PAGE) << 8) | a] = d;
    } else if (a & 1) {
        f->byte_for_vcs = d;
        FROB_PUBLISH_BARRIER();
        f->vcs_full = 1;
    } else {
        f->ctrl = d & FROB_CTRL_MASK;
    }
}

// ---- 2600 side (A11..A0 while /CE is low) --------------------------------
typedef enum {
    VCS_FLOAT = 0,   // RAM belongs to the Apple: drive nothing
    VCS_ROM,         // drive RAM[a]
    VCS_PORT_WR,     // $FFF0: read the 2600's data, publish it when the access ends
    VCS_PORT_STAT,   // $FFF1: drive the status
    VCS_PORT_RD,     // $FFF2: drive the 2600 mailbox, clear '2600 full' when the access ends
} vcs_kind_t;

static inline vcs_kind_t frob_vcs_decode(uint8_t ctrl, uint16_t a) {
    if (!frob_vcs_owns(ctrl))
        return VCS_FLOAT;
    if (frob_port_on(ctrl) && a >= 0xff0 && a <= 0xff2)
        return (vcs_kind_t)(VCS_PORT_WR + (a - 0xff0));
    return VCS_ROM;
}

static inline uint8_t frob_vcs_status(const frob_t *f) {
    return (f->apple_full ? 0 : 0x80) | (f->vcs_full ? 0x40 : 0);
}

// The byte the card drives for kind/a (VCS_ROM, VCS_PORT_STAT, VCS_PORT_RD).
static inline uint8_t frob_vcs_value(const frob_t *f, vcs_kind_t k, uint16_t a) {
    switch (k) {
    case VCS_PORT_STAT: return frob_vcs_status(f);
    case VCS_PORT_RD:   return f->byte_for_vcs;
    default:            return f->mem[a & 0xfff];
    }
}

// Side effects when a port access ends (d: the 2600's data for VCS_PORT_WR).
static inline void frob_vcs_done(frob_t *f, vcs_kind_t k, uint8_t d) {
    if (k == VCS_PORT_WR) {
        f->byte_for_apple = d;
        FROB_PUBLISH_BARRIER();
        f->apple_full = 1;
    } else if (k == VCS_PORT_RD) {
        f->vcs_full = 0;
    }
}

#endif
