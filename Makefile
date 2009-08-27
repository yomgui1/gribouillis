## $Id:  $
##
## Top makefile designed to build Gribouillis for MorphOS platform.
##
## This file is Copyright by Guillaume ROGUEZ.
##

######### Environment

OS := $(shell uname)
BUILDDIR = .
SRCDIR   = .

ifeq ("$(OS)", "MorphOS")
TMPDIR = ram:t
else
TMPDIR = /tmp
endif

ifneq ($(findstring debug, $(MAKECMDGOALS)), debug)
DEFINES += NDEBUG
MODE    = final
else
DEFINES += 
MODE    = debug
endif

BUILD_DATE    := $(shell /bin/date "+%Y.%m.%d")
COMPILE_DATE  := $(shell /bin/date "+%d.%m.%Y")
SVNVERSION	  := $(shell svnversion)

DEPDIR := $(BUILDDIR)/deps/$(MODE)
OBJDIR := $(BUILDDIR)/objs/$(MODE)
LIBSDIR := $(BUILDDIR)/libs/$(MODE)
INCDIR := $(BUILDDIR)/include

INCLUDES = $(SRCDIR) $(SRCDIR)/MorphOS $(SRCDIR)/Include $(OBJDIR) .

ifeq ("$(OS)", "MorphOS")
PYTHON_INCDIR := /usr/include/python
else
PYTHON_INCDIR := /opt/gg/os-include/python
INCLUDES += /opt/gg/os-private
endif

INCLUDES += $(PYTHON_INCDIR)

DEFINES  += AROS_ALMOST_COMPATIBLE USE_INLINE_STDARG

VPATH := $(SRCDIR):$(OBJDIR)

VERSION_MAJOR    = 0
VERSION_MINOR	 = 1
VERSION_REVISION = 0
VERSION			 = $(VERSION_MAJOR).$(VERSION_MINOR).$(VERSION_REVISION)

######### Tools Binaries

CP        = cp -av
ECHO      = echo -e
CC        = ppc-morphos-gcc
LD        = ppc-morphos-ld
AR        = ppc-morphos-ar
NM        = ppc-morphos-nm
STRIP     = ppc-morphos-strip
CVINCLUDE = cvinclude.pl

######### Tools Flags

ARFLAGS = rcsv

CFLAGS = -noixemul -g
OPT = -O2 -mstring -mregnames -fomit-frame-pointer -fno-strict-aliasing -fcall-saved-r13
CC_WARNS = \
	-Wall \
	-Wno-format \
	-Wunused \
	-Wuninitialized \
	-Wstrict-prototypes

CPPFLAGS = $(CFLAGS) $(CC_WARNS) $(OPT) $(DEFINES:%=-D%) $(INCLUDES:%=-I%)
LINKFLAGS = $(CFLAGS) -Wl,--traditional-format \
	-Wl,--cref -Wl,--stats -Wl,-Map=mapfile.txt \
	-Wl,--warn-common -Wl,--warn-once

LIBS = -lpython -lauto -lsyscall
ifneq ("$(OS)", "MorphOS")
LDLIBS += -lnix
endif

STRIPFLAGS = -R.comment -o $@ $<

######### Shell output beautification

COLOR_EMPHASIZE  = "\033[37m"
COLOR_HIGHLIGHT1 = "\033[33m"
COLOR_HIGHLIGHT2 = "\033[32m"
COLOR_BOLD       = "\033[0m\033[1m"
COLOR_NORMAL     = "\033[0m"

CREATING  = $(ECHO) $(COLOR_BOLD)">> "$(COLOR_HIGHLIGHT1)"$@"$(COLOR_NORMAL)
COMPILING = $(ECHO) $(COLOR_BOLD)">> "$(COLOR_HIGHLIGHT1)"$@"$(COLOR_BOLD)" : "$(COLOR_HIGHLIGHT2)"$(notdir $^)"$(COLOR_NORMAL)
LINKING	  = $(ECHO) $(COLOR_HIGHLIGHT2)">> Linking "$(COLOR_HIGHLIGHT1)"$@"$(COLOR_NORMAL)
ARCHIVING = $(ECHO) $(COLOR_HIGHLIGHT2)">> Archiving "$(COLOR_HIGHLIGHT1)"$@"$(COLOR_BOLD)" : "$(COLOR_HIGHLIGHT2)"$(notdir $^)"$(COLOR_NORMAL)
MAKINGDIR = $(ECHO) $(COLOR_HIGHLIGHT2)">> Making directory "$(COLOR_BOLD)"$(@D)"$(COLOR_NORMAL)

######### Automatic rules

.SUFFIXES:
.SUFFIXES: .c .h .s .o .d .db .sym

$(OBJDIR)/%.o : $(SRCDIR)/%.c
	-@test ! -d $(@D) && $(MAKINGDIR) && mkdir -p $(@D)
	@$(COMPILING)
	$(CC) -c $(CPPFLAGS) $< -o $@

%.sym: %.db
	$(NM) -n $^ > $@

# Automatic dependencies generation

$(DEPDIR)/%.d : %.c
	-@test ! -z "$(@D)" -a ! -d "$(@D)" && $(MAKINGDIR) && mkdir -p "$(@D)"
	@$(CREATING)
	$(SHELL) -ec '$(CC) -MM $(CPPFLAGS) $< 2>/dev/null \
		| sed '\''s%\($(notdir $*)\)\.o[ :]*%$(OBJDIR)/$(dir $*)\1.o $@ : %g'\'' > $@; \
		[ -s $@ ] || rm -fv $@'

##########################################################################
# Target Rules and defines

TARGET = $(BUILDDIR)/Gribouillis.db

TARGET_SRCS = main.c
ALL_SOURCES += $(TARGET_SRCS)

TARGET_OBJS = $(TARGET_SRCS:%.c=$(OBJDIR)/%.o)

$(TARGET): DEFINES+=VERSION_STR=\"$(VERSION)\"
$(TARGET): OBJS=$(TARGET_OBJS)
$(TARGET): $(TARGET_OBJS)
	$(CC) $(LINKFLAGS) -o $@ $^ $(LIBS)

##########################################################################
# General Rules

.DEFAULT: all
.PHONY: all clean distclean debug final pyfunc mkfuncarray force sdk

force:;

debug final:

clean:
	rm -f mapfile.txt $(TARGET)
	-[ -d $(OBJDIR) ] && find $(OBJDIR) -name "*.o" -exec rm -v {} ";"

distclean: clean
	rm -rf $(BUILDDIR)/deps $(BUILDDIR)/objs $(BUILDDIR)/libs $(BUILDDIR)/include

all: $(TARGET)

######### Automatic deps inclusion

ifeq ("$(filter clean distclean,$(MAKECMDGOALS))","")
$(info Including dependencies...)
include $(ALL_SOURCES:%.c=$(DEPDIR)/%.d)
endif
