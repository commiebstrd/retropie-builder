#!env python3

import re
from enum import Enum

class Filters(Enum):
    Verified_Good_Dump = re.compile("\[!\]")
    Bad_Dump = re.compile("\[b\]")
    Fixed = re.compile("\[f\]") # altered in some way so that it will run better on a copier or emulator
    Pending_dump = re.compile("\[!p\]") # This is the closest dump to the original game to date, but the proper ROM is still waiting to be dumped.
    Alternate = re.compile("\[a\]")
    Pirate = re.compile("\[p\]")
    Trained = re.compile("\[t\]")
    OldTranslation = re.compile("\[T-\]") #
    NewerTranslation = re.compile("\[T+\]") #
    Overdump = re.compile("\[o\]") #
    Multilanguage = re.compile("\(M#\)") #
    Unclassified = re.compile("ZZZ-Unk") #
    Unlicensed = re.compile("\(Unl\)") #
    Old = re.compile("\(old\)")
    Language = re.compile("\[R-XXX\]")
    Pirate_multicart = re.compile("\?\?-in-1")
    Official_multicart = re.compile("\(Vol")
    wii_virtual_console = re.compile("\(VC\)")
    Hack = re.compile("\[([hf][#\dCIR]*|hack)\\]")
    Alpha = re.compile("\(Alpha\)")
    Beta = re.compile("\(Beta\)")
    Prototype = re.compile("\(Proto(type)?\)")
    Pre_release = re.compile("\(Pre-Release\)")
    Kiosks = re.compile("\(Kiosk")
    Multicart = re.compile("\(Menu\)")
    bios = re.compile("BIOS")
    Japan_Korea = re.compile("\(1\)") #
    NTSC = re.compile("\(4\)") #
    Australia = re.compile("\(A(u(s(trailia)?)?)?\)") #
    Japan = re.compile("\(J(ap(an)?)?\)") #
    Brazil = re.compile("\(B(ra(zil)?)?\)") #
    Korea = re.compile("\(K(or(ea)?)?\)")
    China = re.compile("\(C(h(ina)?)?\)")
    Netherlands = re.compile("\(NL\)")
    Europe = re.compile("\(E(u(r(ope)?)?)?\)")
    Public_Domain = re.compile("\(PD\)")
    France = re.compile("\(F(r(ance)?)?\)")
    Spain = re.compile("\(S(p(ain)?)?\)")
    French_Canadian = re.compile("\(FC\)")
    Sweden = re.compile("\(SW\)")
    Finland = re.compile("\(FN\)")
    USA = re.compile("\(Us?a?\)")
    Germany = re.compile("\(G(er(many)?)?\)")
    England = re.compile("\(UK\)")
    Greece = re.compile("\(GR\)")
    Unknown = re.compile("\(Unk\)")
    Hong_Kong = re.compile("\(HK\)")
    Italy = re.compile("\(I(t(aly)?)?\)")
    Holland = re.compile("\(H\)")
    World = re.compile("\((W(orld)?)?\)")
    
    def check(self, rom):
        if self.value.search(rom):
            return True
        return False
    
    @classmethod
    def fromstring(cls, str):
          return getattr(cls, str, None)
