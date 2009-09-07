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
PREFIX := /usr
PYTHON_INCDIR := $(PREFIX)/include/python
else
TMPDIR = /tmp
PREFIX := /opt/gg/usr
PYTHON_INCDIR := $(PREFIX)/include $(PREFIX)/include/python
endif

ifneq ($(findstring debug, $(MAKECMDGOALS)), debug)
DEFINES += NDEBUG
MODE    = final
else
DEFINES += Py_DEBUG
MODE    = debug
endif

BUILD_DATE    := $(shell /bin/date "+%Y.%m.%d")
COMPILE_DATE  := $(shell /bin/date "+%d.%m.%Y")
SVNVERSION	  := $(shell svnversion)

DEPDIR := $(BUILDDIR)/deps/$(MODE)
OBJDIR := $(BUILDDIR)/objs/$(MODE)
LIBSDIR := $(BUILDDIR)/libs/$(MODE)
INCDIR := $(BUILDDIR)/include

INCLUDES = $(SRCDIR) $(OBJDIR) .

ifneq ("$(OS)", "MorphOS")
INCLUDES += /opt/gg/os-private
else
INCLUDES += /MOSPRVINC
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
OPT = -O2 -mstring -mregnames -fomit-frame-pointer -fno-strict-aliasing -fcall-saved-r13 -ffixed-r13
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
LDFLAGS_SHARED = --traditional-format \
	--cref -Map=$(BUILDDIR)/mapfile.txt -m morphos \
	-fl libnix --warn-common --warn-once
LDLIBS = -lc -laboxstubs -labox -lc -lm -lmath -ldl

LIBS = -L$(PREFIX)/lib -lpython -lsyscall
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
.SUFFIXES: .c .h .s .o .d .db .sym .mcc

$(OBJDIR)/%.o : $(SRCDIR)/%.c
	-@test ! -d $(@D) && $(MAKINGDIR) && mkdir -p $(@D)
	@$(COMPILING)
	$(CC) -c $(CPPFLAGS) $< -o $@

%.sym: %.db
	@$(CREATING)
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

ALL_SOURCES += $(MCC_SRCS)

%.mcc.db:
	$(MAKE) $(MCC_OBJS) DEFINES="$(DEFINES) CLASS=\\\"$(MCC).mcc\\\" \
		VERSION=$(VERSION) REVISION=$(REVISION) VERSION_STR=\\\"$(VERSION).$(REVISION)\\\" \
		VERSION_STR=\\\"$(VERSION).$(REVISION)\\\""
	-@test ! -d $(@D) && $(MAKINGDIR) && mkdir -p $(@D)
	@$(LINKING)
	$(LD) -o $@ $(LDFLAGS_SHARED) $(MCC_OBJS) $(LDLIBS) $(LIBS)

##########################################################################
# General Rules

.DEFAULT: all
.PHONY: all clean distclean debug final pyfunc mkfuncarray sdk release force

force:;

debug final:

clean:
	rm -f mapfile.txt *.db *.sym
	-[ -d $(OBJDIR) ] && find $(OBJDIR) -name "*.o" -exec rm -v {} ";"

distclean: clean
	rm -rf $(BUILDDIR)/deps $(BUILDDIR)/objs $(BUILDDIR)/libs $(BUILDDIR)/include

all: $(BUILDDIR)/Curve.mcc.sym $(BUILDDIR)/Curve.mcc

$(BUILDDIR)/Curve.mcc.db: MCC:=Curve
$(BUILDDIR)/Curve.mcc.db: MCC_SRCS:=curve_mcc.c
$(BUILDDIR)/Curve.mcc.db: MCC_OBJS= $(MCC_SRCS:%.c=$(OBJDIR)/%.o)
$(BUILDDIR)/Curve.mcc.db: VERSION:=1
$(BUILDDIR)/Curve.mcc.db: REVISION:=0

$(BUILDDIR)/Curve.mcc: $(BUILDDIR)/Curve.mcc.db
	$(STRIP) $(STRIPFLAGS)
	chmod +x $@

######### Automatic deps inclusion

ifeq ("$(filter clean distclean,$(MAKECMDGOALS))","")
$(info Including dependencies...)
include $(ALL_SOURCES:%.c=$(DEPDIR)/%.d)
endif
