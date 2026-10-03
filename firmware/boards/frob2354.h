// Frob2354 Rev0: RP2354B (RP2350B + 2 MB flash in package), 12 MHz crystal.
// pico_cmake_set PICO_PLATFORM=rp2350-arm-s
#ifndef _BOARDS_FROB2354_H
#define _BOARDS_FROB2354_H

#define FROB2354

#define PICO_RP2350A 0                  // QFN-80 (B) package: 48 GPIOs
#define PICO_RP2350_A2_SUPPORTED 1

#define PICO_DEFAULT_LED_PIN 22

#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1
#ifndef PICO_FLASH_SPI_CLKDIV
#define PICO_FLASH_SPI_CLKDIV 2
#endif
// pico_cmake_set_default PICO_FLASH_SIZE_BYTES = (2 * 1024 * 1024)
#ifndef PICO_FLASH_SIZE_BYTES
#define PICO_FLASH_SIZE_BYTES (2 * 1024 * 1024)
#endif

#ifndef PICO_XOSC_STARTUP_DELAY_MULTIPLIER
#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64
#endif

#endif
