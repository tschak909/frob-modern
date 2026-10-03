cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD frob2354)
set(PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/boards)
set(PICO_PLATFORM rp2350-arm-s)

include(pico_sdk_import.cmake)
project(frob2354 C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

add_executable(frob2354 src/main.c src/apple_bus.c src/vcs_bus.c)
target_include_directories(frob2354 PRIVATE src)
target_compile_options(frob2354 PRIVATE -O2 -Wall -Wextra)
if (DEFINED FROB_SYS_KHZ)
    target_compile_definitions(frob2354 PRIVATE FROB_SYS_KHZ=${FROB_SYS_KHZ})
endif()
target_link_libraries(frob2354 pico_stdlib pico_multicore hardware_vreg)
# everything runs from SRAM: no XIP fetches in the bus loops
pico_set_binary_type(frob2354 copy_to_ram)
pico_enable_stdio_usb(frob2354 0)
pico_enable_stdio_uart(frob2354 0)
pico_add_extra_outputs(frob2354)
