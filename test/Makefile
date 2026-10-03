CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror

test: test_frob
	./test_frob

test_frob: test_frob.c ../firmware/src/frob_logic.h
	$(CC) $(CFLAGS) -I../firmware/src -o $@ test_frob.c

clean:
	rm -f test_frob

.PHONY: test clean
