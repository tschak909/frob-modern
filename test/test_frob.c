// Host tests of the FROB register semantics (firmware/src/frob_logic.h), the
// same code the RP2354B runs.  Expected behaviour from the reverse-engineered
// FROB card (retroabandon/apple2-re frob/hwdoc) and MAME's a2frob.cpp;
// where the two differ the hardware wins, and the test says so.
//
//   make -C test        (or: cc -std=c11 -Wall -Wextra -I../firmware/src test_frob.c && ./a.out)
#include <stdio.h>
#include <stdlib.h>

#include "frob_logic.h"

static int fails, checks;
#define CHECK(c) do { checks++; if (!(c)) { fails++; printf("%s:%d: FAIL %s\n", __FILE__, __LINE__, #c); } } while (0)

static frob_t f;

// one complete Apple access, as apple_bus.c performs it
static int apple_rd(bool iosel, uint8_t a) {
    uint8_t v;
    bool drv = frob_apple_read(&f, iosel, a, &v);
    frob_apple_read_done(&f, iosel, a);
    return drv ? v : -1;
}
static void apple_wr(bool iosel, uint8_t a, uint8_t d) { frob_apple_write(&f, iosel, a, d); }
#define C0N(x) false, (x)          // $C0n0 + x
#define CN(x)  true, (x)           // $Cn00 + x

// one complete 2600 access (A11..A0 with /CE low), as vcs_bus.c performs it
static int vcs_acc(uint16_t a, uint8_t wdata) {
    vcs_kind_t k = frob_vcs_decode(f.ctrl, a);
    if (k == VCS_FLOAT)
        return -1;
    int v = k == VCS_PORT_WR ? -2 : frob_vcs_value(&f, k, a);
    frob_vcs_done(&f, k, wdata);
    return v;
}

static void test_power_on(void) {
    frob_reset(&f);
    CHECK(f.ctrl == 0);
    CHECK(apple_rd(C0N(0)) == 0x80);          // may write, nothing to read
    CHECK(vcs_acc(0xffc, 0) == -1);           // RAM belongs to the Apple: the 2600 sees nothing
    // zeroed RAM can never look like a slot boot ROM ($Cn01=$20 $Cn03=$00 $Cn05=$03)
    CHECK(apple_rd(CN(1)) == 0 && apple_rd(CN(5)) == 0);
}

static void test_paging(void) {
    frob_reset(&f);
    for (int p = 0; p < 16; p++) {             // pmove.lst: STA $C0n0 with the page number
        apple_wr(C0N(0), p);
        for (int i = 0; i < 256; i++)
            apple_wr(CN(i), (uint8_t)(p * 16 + i * 7));
    }
    for (int p = 15; p >= 0; p--) {
        apple_wr(C0N(0), p);
        for (int i = 0; i < 256; i++)
            CHECK(apple_rd(CN(i)) == (uint8_t)(p * 16 + i * 7));
    }
    CHECK(f.mem[0x3a5] == (uint8_t)(3 * 16 + 0xa5 * 7));
    // D6/D7 of the control write are ignored ('174 latches D0-D5)
    apple_wr(C0N(0), 0xc2);
    CHECK(f.ctrl == 0x02);
    // the register pair mirrors through $C0n0-$C0nF on A0
    apple_wr(C0N(0xe), 0x05);
    CHECK(f.ctrl == 0x05);
}

static void test_ownership(void) {
    frob_reset(&f);
    apple_wr(C0N(0), 0x0f);
    apple_wr(CN(0xfc), 0x00);                  // reset vector $F000 at $FFFC
    apple_wr(CN(0xfd), 0xf0);
    apple_wr(C0N(0), 0x10);                    // RAM to the 2600, port off
    CHECK(vcs_acc(0xffc, 0) == 0x00 && vcs_acc(0xffd, 0) == 0xf0);
    CHECK(apple_rd(CN(0x10)) == -1);           // the Apple's window floats
    apple_wr(CN(0x10), 0x55);                  // and ignores writes
    apple_wr(C0N(0), 0x00);
    CHECK(apple_rd(CN(0x10)) == 0x00);
    CHECK(vcs_acc(0x000, 0) == -1);
    // with the port off, $FFF0-$FFF2 are plain RAM
    apple_wr(C0N(0), 0x0f);
    apple_wr(CN(0xf0), 0x11); apple_wr(CN(0xf1), 0x22); apple_wr(CN(0xf2), 0x33); apple_wr(CN(0xf3), 0x44);
    apple_wr(C0N(0), 0x10);
    CHECK(vcs_acc(0xff0, 0x99) == 0x11 && vcs_acc(0xff1, 0) == 0x22 && vcs_acc(0xff2, 0) == 0x33);
    CHECK(f.apple_full == 0);
    // port bit alone (RAM still the Apple's) enables nothing on the 2600 side (U10A needs both)
    apple_wr(C0N(0), 0x20);
    CHECK(vcs_acc(0xff1, 0) == -1);
    // port on: $FFF0-$FFF2 are the port, $FFF3 is RAM
    apple_wr(C0N(0), 0x30);
    CHECK(vcs_acc(0xff3, 0) == 0x44);
    CHECK(vcs_acc(0xff1, 0) == 0x80);
}

static void test_mailboxes(void) {
    frob_reset(&f);
    apple_wr(C0N(0), 0x30);                    // 2600 owns the RAM, port on
    // Apple -> 2600
    CHECK(apple_rd(C0N(0)) == 0x80);
    apple_wr(C0N(1), 0xa5);
    CHECK(apple_rd(C0N(0)) == 0x00);           // 'may write' drops
    CHECK(vcs_acc(0xff1, 0) == 0xc0);          // 2600: may write, may read
    CHECK(vcs_acc(0xff2, 0) == 0xa5);          // read clears '2600 full'
    CHECK(vcs_acc(0xff1, 0) == 0x80);
    CHECK(apple_rd(C0N(0)) == 0x80);
    // 2600 -> Apple
    CHECK(vcs_acc(0xff0, 0x5a) == -2);         // a write: the card does not drive
    CHECK(vcs_acc(0xff1, 0) == 0x00);          // 2600: may not write
    CHECK(apple_rd(C0N(0)) == 0xc0);           // Apple: may write, may read
    CHECK(apple_rd(C0N(1)) == 0x5a);
    CHECK(apple_rd(C0N(0)) == 0x80);
    CHECK(vcs_acc(0xff1, 0) == 0x80);
    // re-reading the Apple data port returns the latch (U14 holds it)
    CHECK(apple_rd(C0N(3)) == 0x5a);
    // any access to the data port clears 'Apple full' -- including a 6502 dummy
    // read (STA $C080,X reads the target first); U1B is cleared by the strobe itself
    vcs_acc(0xff0, 0x42);
    CHECK(f.apple_full);
    (void)apple_rd(C0N(0xf));                  // mirror of $C0n1
    CHECK(!f.apple_full);
    // the Apple may use the mailboxes whoever owns the RAM (U1/U4/U14 are always live)
    apple_wr(C0N(0), 0x00);
    apple_wr(C0N(1), 0x77);
    CHECK(f.vcs_full && f.byte_for_vcs == 0x77);
    CHECK(vcs_acc(0xff2, 0) == -1);            // ... but the 2600 cannot reach the port
    CHECK(f.vcs_full);
    // reading status has no side effects on either side
    apple_wr(C0N(0), 0x30);
    for (int i = 0; i < 3; i++) {
        CHECK(apple_rd(C0N(0)) == 0x00);
        CHECK(vcs_acc(0xff1, 0) == 0xc0);
    }
}

static void test_mame_agreement(void) {
    // MAME a2frob.cpp: read_c0nx(0) = (!vcs_full)<<7 | apple_full<<6;
    // a2600_read_fff1 = (!apple_full)<<7 | vcs_full<<6.  Same bits, all four states.
    for (int vf = 0; vf < 2; vf++)
        for (int af = 0; af < 2; af++) {
            frob_reset(&f);
            f.vcs_full = vf; f.apple_full = af;
            uint8_t v;
            frob_apple_read(&f, false, 0, &v);
            CHECK(v == (((!vf) << 7) | (af << 6)));
            CHECK(frob_vcs_status(&f) == (((!af) << 7) | (vf << 6)));
        }
    // Difference, deliberately: MAME maps $1FF0-$1FF2 unconditionally; the hardware
    // (theory.md, U2 '138 enabled by U10A = !(APL_CTL & BIDIR_EN)) only with both bits.
}

int main(void) {
    test_power_on();
    test_paging();
    test_ownership();
    test_mailboxes();
    test_mame_agreement();
    printf("test_frob: %d checks, %d failed\n", checks, fails);
    return fails ? EXIT_FAILURE : EXIT_SUCCESS;
}
