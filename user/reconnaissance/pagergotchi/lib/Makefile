# Makefile for libpager.so - pager_gfx wrapper for Python
# Cross-compile for WiFi Pineapple Pager (MIPS)

# Cross-compiler (adjust path as needed)
CROSS_COMPILE ?= mipsel-openwrt-linux-musl-
CC = $(CROSS_COMPILE)gcc

# Compiler flags
CFLAGS = -Wall -O2 -fPIC -shared
LDFLAGS = -shared

# Target
TARGET = libpager.so

# Source files
SRCS = pager_wrapper.c

all: $(TARGET)

$(TARGET): $(SRCS) pager_gfx.h pager_gfx.c
	$(CC) $(CFLAGS) -o $(TARGET) $(SRCS) $(LDFLAGS)

clean:
	rm -f $(TARGET)

# For local testing (native compile)
native:
	gcc $(CFLAGS) -o $(TARGET) $(SRCS) $(LDFLAGS)

.PHONY: all clean native
