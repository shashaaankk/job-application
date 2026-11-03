"""The screen. Every rule that rejects a posting, in one place.

Nothing here is a judgement about what he would like. Each rule cites the file and
the rule number that authorises it, because four earlier versions were built from
my impressions of samples and two of them contradicted his documented record.

Two stages, cheapest first.

  screen_title(title, company, location, cell)
      Decides whether a description is worth fetching. Reads the title and the
      lister only, so it costs nothing.

  screen_description(text, location, allowed, cell)
      Decides whether the posting survives its own description. This is where the
      real screening happens, because the two largest error classes, a description
      naming none of his work and a stated years figure, are invisible in a title.

Measured on one sweep of 6817 postings across thirteen countries. The title stage
left 466 and the description stage left 227, so the title stage is right about
half the time and is meant to be generous rather than accurate.
"""

import re
import unicodedata

import places

# ===================================================================== KEEP
# 04. preferences 2.1, the ten roles, in the forms a posting writes them across the
# languages the matrix searches.
ROLES = {
    "robotics engineer":       r"robot|robotik|robotique|robotica|cobot",
    "embedded software":       r"embedded|embarqu|eingebettet|incorporad|\bbsp\b|yocto|\brtos\b|freertos|bare.?metal|mikrocontroller|microcontroller",
    "firmware":                r"firmware",
    "embedded or physical AI": r"edge ai|physical ai|embodied|tinyml|on.?device|edge comput",
    "ADAS or automotive sw":   r"\badas\b|fahrerassistenz|autosar|automotive|fahrzeug|vehicle|powertrain|\bcan bus\b|diagnos",
    "R&D engineer":            r"\br&d\b|\brnd\b|research engineer|forschung|entwicklungsingenieur",
    "autonomous systems":      r"autonom|autonomy|self.?driving|unmanned|\buav\b|\buas\b|drone|drohne",
    "C++ developer":           r"\bc\+\+|\bcpp\b|\bc/c\+\+",
    "automation and controls": r"automation|automatisierung|control|regelung|steuerung|mechatron",
    "AI/ML on embedded":       r"machine learning|deep learning|neural|computer vision|perception|bildverarbeitung|\bslam\b|sensor fusion|signal processing|signalverarbeitung|\bdsp\b|radar",
}

# 04. preferences 2.1, the eight domains. A domain qualifies a title whose role noun
# is generic, since the domain is what he selected for.
DOMAINS = {
    "robotics":              r"robot|robotik|cobot",
    "aerospace":             r"aerospace|aeronaut|avionic|luftfahrt|flight|aircraft|a[eé]ronautique",
    "automotive":            r"automotive|fahrzeug|vehicle|\badas\b|powertrain|autosar",
    "industrial automation": r"industrial automation|industrielle automat|process control|machine.?bau|machinebouw",
    "consumer electronics":  r"consumer electronic|audio|wearable|smart home|\biot\b",
    "biomedical":            r"medical|medizin|biomedical|clinical|surgical|patient|healthcare",
    "space and defense":     r"\bspace\b|satellit|spacecraft",
    "computing technology":  r"kernel|linux|device driver|compiler|operating system",
}

# ===================================================================== DROP
# rule 2, the experience ceiling. Senior is out on the title alone.
R2_TITLE = (r"\bsenior\b|\bsr\.?\b|\bstaff\b|\bprincipal\b|\bhead\b|\blead\b|\bleader\b|"
            r"\bleitung\b|projektleit|\bdirector\b|\bchief\b|\bvp\b|\bmanager\b|"
            r"teamlead|team lead|\bexpert\b|\bspezialist\b|\bspecialist\b|"
            # German writes the title as one word, so "\bleiter\b" missed
            # Gruppenleiter, Teamleiter, Abteilungsleiter and Bereichsleiter. The
            # negative lookahead protects Leiterplatte, which is a circuit board and
            # is his field, and Leiterquerschnitt, which is a conductor.
            r"\w*leiter(?!platte|querschnitt|bahn)(?:in)?\b|\w*leitung\b")
R2_YEARS = r"\b([6-9]|[1-9][0-9])\s*\+?\s*(years?|yrs?|jahre|anni|ans)\b"

# rule 3, the level floor
R3 = (r"praktikum|internship|\bintern\b|werkstudent|working student|thesis|"
      r"abschlussarbeit|apprentice|ausbildung|\bazubi\b|dual stud|duales stud|"
      # a trainee or graduate programme is below the floor too. It was missing, and
      # "Automation & Logistics Operations Trainee" reached the board because of it.
      r"\btrainee\b|traineeship|graduate programme|graduate program\b|"
      r"\bvolontariat\b|berufseinsteiger|quereinsteiger|schulpraktik")

# rule 10, semiconductor chip design. The ASIC and FPGA family is here on his
# instruction, since most of what it matched was already out of scope.
R10_CHIP = (r"chip design|\bvlsi\b|\brtl\b|physical design|design verification|\bdft\b|"
            r"analog (ic|design)|standard cell|tapeout|\bpdk\b|\basic\b|\bfpga\b|\bsoc\b|"
            r"\bvhdl\b|verilog|semiconductor")

# rule 10, a job board or aggregator repost, meaning the lister is not the employer.
# A body-leasing firm or consultancy is NOT here, see rule 12 below.
R10_BOARD = [
    "jobster", "jobbird", "synsel", "jobgether", "haystack", "alignerr", "joblift",
    "jooble", "talent com", "whatjobs", "trabajo", "experteer", "instaffo",
    "jobcrexa", "zyoin", "signify technology", "selby jennings", "lawrence harvey",
    "mobiskill", "turing", "jobrapido", "neuvoo", "careerjet", "adzuna",
]

# rule 11, European defence is out of scope on his instruction. India is unaffected.
R11_TITLE = (r"defen[cs]e|wehrtechnik|armament|military|munition|weapon|electronic warfare|"
             r"\bcomint\b|\belint\b|\bsigint\b|naval|submarine|missile|ammunition|\bc.uas\b")
# rule 11 again, on the description rather than the title. The lister's title hides
# the work, so Trinamics advertised "System Engineer - Electrical Vehicles" and the
# description's own heading read "Systems Engineer, Defence Vehicle Systems". The
# title stage could not have caught it. Dutch, German, French and Swedish are here
# because the posting is written in the country's language, not in English.
R11_DESC = re.compile(
    r"\bdefen[cs]e\b|\bdefensie\b|defensieplatform|\bverteidigung|wehrtechnik|"
    r"\bbundeswehr\b|\bd[eé]fense\b|\bf[oö]rsvar|\bmilitar(y|y)\b|\bmilitair|"
    r"\bmilit[aä]r|\bmilitaire|\barmament|\bmunition|\bammunition\b|\bweapon|"
    r"\bwaffen|\bmissile|\bnaval\b|\bsubmarine\b|electronic warfare|"
    r"\bcomint\b|\belint\b|\bsigint\b|\bnato\b|\bc.uas\b|krijgsmacht|"
    r"\bbattle\b|\bcombat\b|armoured vehicle|armored vehicle|gepanzerte|"
    # German naval defence, which none of the above reached. ATLAS ELEKTRONIK scored
    # band 3 and reached `to apply` while describing itself as a "Systemhaus für
    # Marineelektronik" supplying "Führungssystemen für U-Boote und
    # Überwasserschiffe" and "Minenabwehrsystemen". High precision terms only, so
    # "Marine" alone is not here and marine biology or a maritime civil role is safe.
    r"marineelektronik|\bu.boot|\buboot\b|uberwasserschiff|[uü]berwasserschiff|"
    r"minenabwehr|\btorpedo|fregatte|korvette|kampfschiff|streitkr[aä]fte|"
    r"r[uü]stungs|waffensystem|f[uü]hrungssystem|marinen auf",
    re.I)

# The same word appears for two different reasons, and only one of them is the role.
# An agency lists the sectors it staffs, so Scalian wrote "Automotive, Energie, Luft-
# und Raumfahrt, Bahn und Verteidigung" and Bertrandt wrote "Automotive, Luftfahrt,
# Defence und Maschinenbau". Neither posting is a defence job. A match sitting inside
# such an enumeration is company boilerplate and is discounted, which is decided by
# whether two or more other industries are named beside it.
R11_SECTORS = re.compile(
    r"automotive|a[eé]ronautique|aeronautic|aerospace|luftfahrt|raumfahrt|spatial|"
    r"\benergie\b|\benergy\b|\bbahn\b|\brail\b|ferroviaire|maschinenbau|"
    r"medical|medizin|m[eé]dical|\bindustrie\b|industry|telecom|halbleiter|"
    r"semiconductor|consumer|\bbanking\b|\bfinance\b|chemie|pharma|\bnaval\b",
    re.I)
# An equal opportunity clause names veteran status, which is not a statement about
# the work either.
R11_EEO = re.compile(r"veteran status|equal opportunit|discriminat", re.I)


def r11_is_the_role(text):
    """Whether a defence term in the description describes the work.

    Returns True on the first match that is neither an industry enumeration nor an
    equal opportunity clause. Three postings were wrongly rejected before this
    existed, all of them agencies naming defence among the sectors they staff.
    """
    for m in R11_DESC.finditer(text):
        ctx = text[max(0, m.start() - 90):m.end() + 90]
        if R11_EEO.search(ctx):
            continue
        others = {x.group(0).lower() for x in R11_SECTORS.finditer(ctx)}
        if "," in ctx and len(others) >= 2:
            continue
        return True
    return False


R11_EMPLOYER = [
    "rheinmetall", "hensoldt", "knds", "mbda", "diehl defence", "diehl defense",
    "airbus defence", "airbus defense", "elbit", "saab", "nexter", "kongsberg",
    "babcock", "qinetiq", "bae systems", "leonardo", "thales", "safran", "patria",
    "milrem", "arquus", "hanwha", "general atomics", "anduril", "helsing",
    "quantum-systems", "quantum systems", "tytan", "sphere defense", "harmattan",
    # naval, added after ATLAS ELEKTRONIK passed every title and employer test
    "atlas elektronik", "tkms", "thyssenkrupp marine", "naval group", "fincantieri",
    "damen naval", "navantia",
]
EU = {"Germany", "France", "Netherlands", "Sweden", "Belgium", "Italy", "Switzerland",
      "Denmark", "Finland", "Norway", "Spain", "Austria", "Portugal", "Ireland",
      "Czechia", "Poland", "Romania", "United Kingdom"}

# rule 12, body leasing is in scope in every country, his ruling 2026-10-15. These
# listers are flagged on the card as information and never rejected or demoted.
R12_AGENCY = [
    "akkodis", "alten", "teoresi", "sii ", "segula", "capgemini", "ferchau",
    "amaris", "astek", "accenture", "modis", "expleo", "altran", "tata consultancy",
    "infosys", "wipro", "cognizant", "luxoft", "nttdata", "ntt data", "ust ",
    "quest global", "randstad", "adecco", "hays", "brunel", "tintschl", "etteplan",
]
GERMANY = r"\bgermany\b|\bdeutschland\b"

# His instruction, five German states are out of scope. Written as the GeoNames
# admin1 names the gazetteer carries, because that is what `places.state_of` returns.
# A bare town name is resolved through the gazetteer, so "Gera" is caught as
# Thuringia even though the posting never names the state.
EXCLUDED_STATES = {
    "Brandenburg",
    "Mecklenburg-Vorpommern",
    "Saxony",
    "Saxony-Anhalt",
    "Thuringia",
}

# His instruction, not his field and not flagged but dropped.
NOT_INTERESTED = (
    # sales
    r"\bsales\b|vertrieb|account manager|business development|pre.?sales|"
    # the Microsoft stack
    r"\.net\b|dotnet|\bc#\b|csharp|\basp\.net\b|\bwpf\b|\bwinforms\b|"
    r"\bvb\.net\b|\bsharepoint\b|\bdynamics 365\b|\bazure devops\b|"
    # the Windows desktop application trade. "C++ Software Engineer, Windows
    # Applications" passed as a C++ role, because C++ is a language and the title
    # said nothing the lists forbade.
    r"windows application|windows desktop|windows software|windows front.?end|"
    r"\bwin32\b|\bmfc\b|\buwp\b|\bwinui\b|\bwinapi\b|"
    # Salesforce and its ecosystem
    r"salesforce|\bapex\b developer|\bcrm\b|mulesoft|\bveeva\b|\bcpq\b|"
    # PLC and the programmable-controller trade, his instruction. It was a positive
    # until now and produced SPS-Programmierer adverts, which are not his field.
    # PLC only, his instruction. Step 7, TIA Portal and Codesys are PLC programming
    # environments so they belong here; DeltaV, DCS and HMI panel work are a
    # different thing and I added them on my own, so they are out of this list.
    r"\bplc\b|\bsps\b.?programmier|programmable logic|step ?7|tia.?portal|codesys|"
    # robotic process automation and workforce management, which are office software.
    # An insurance group's group leader for "Workforce Management und
    # Prozessautomatisierung" reached the board on the word automatisierung.
    r"robotic process|\brpa\b|uipath|blue prism|power automate|"
    r"workforce management|business process (automation|management)|\bbpm\b|"
    # web and mobile test tooling, which is not his verification work. HIL, SIL,
    # processor in the loop and MC/DC stay his field and are not here.
    r"\bqa\b.?automation|automation (qa|tester)|selenium|appium|cypress|"
    r"\btosca\b|soapui|katalon|robot framework|"
    # data roles
    r"data engineer|data scientist|data analyst|data architect|data platform|"
    r"data warehouse|\betl\b|\belt\b pipeline|big data|business intelligence|"
    r"\bbi\b developer|analytics engineer|databricks|snowflake|\bdbt\b|"
    r"power ?bi|tableau|looker|data governance|master data")

# The same trade, read from the description rather than the title. M&I Broadcast
# advertised a C++ role and the work is the Windows front end of a desktop player,
# written in C++ and C# .NET 8.0. The title stage could not see that and the
# description stage did not look, because the only question it asked was whether the
# description named one of his areas, and C++ is a language rather than a kind of work.
#
# A strong term is one that names the desktop application itself. A weak term is one
# an unrelated posting can mention in passing, so two of those are needed. A platform
# list such as "cross-platform on Windows and Linux" matches neither, which is why
# the strong patterns all require the word application, desktop or front end beside it.
MS_STRONG = re.compile(
    # every pattern names Windows. A bare "desktop application" was here and it
    # rejected a Qt and C++ 3D graphics role, since Qt desktop work is cross platform
    # and not the Microsoft stack at all.
    r"windows application|windows desktop|native windows|"
    r"windows front.?end|windows client|\bwpf\b|\bwinforms\b|\bmfc\b|"
    r"\bwin32\b|\bwinapi\b|\buwp\b|\bwinui\b|windows presentation foundation",
    re.I)
MS_WEAK = re.compile(r"\bc#\b|csharp|\.net\s?\d|\.net\b|dotnet|asp\.net|"
                     r"visual basic|\bvb\.net\b|\bxaml\b|entity framework|"
                     r"\bblazor\b|\bsharepoint\b", re.I)

# ============================================= what his work looks like in a description
# Used by the description stage. The count of these present is the rank.
# rule 79, mechanical engineering is not his field. It is a reject list rather than a
# scoring input, because the screen rejects and does not rank.
#
# Tesla's "Robotics CAE Engineer, Optimus" reached the board carrying ten of these
# terms. It passed because the only thing the screen asked of the description was
# whether it named one of his work areas, and "robot" and "automotive" are market
# words that every advert a robotics company writes contains, whatever the
# discipline.
#
# The strong list is the practice and the tooling, which no software role carries by
# accident. The title list is the handful of titles that are mechanical on their face.
R10_MECH_STRONG = re.compile(
    r"\bcae\b|\bfea\b|\bfem\b|\bcfd\b|finite element|finite.?elemente|"
    r"structural analys|stress analys|festigkeitsberechnung|\bnvh\b|"
    r"fatigue (life|analys)|durability (test|analys)|tolerance stack|\bgd&t\b|"
    r"\bcatia\b|solidworks|\bcreo\b|\bnx cad\b|inventor|autocad|"
    r"\bansys\b|\babaqus\b|nastran|ls.?dyna|hypermesh|\boptistruct\b|"
    r"\bmoldflow\b|sheet metal|blechbearbeitung|spritzgus|injection mould|"
    r"injection mold|zerspanung|\bcnc\b|\bcam\b programming|"
    r"technische zeichnung|technical drawing|\bbom\b release|"
    r"konstruktionszeichnung|maschinenelement|getriebe|hydraulik|pneumatik",
    re.I)
# A title that declares the controller trade itself. This is separate from the word
# automation, which stays a role of his, because industrial automation is one of his
# eight domains while PLC programming is the trade he has ruled out. "SPS /
# Automatisierungs-Ingenieur" and "Softwareentwickler Steuerungstechnik" are the trade.
R_PLC_TITLE = re.compile(
    r"\bsps\b|\bplc\b|steuerungstechnik|leittechnik|speicherprogrammierbar|"
    r"tia.?portal|codesys|automatisierungstechniker|elektroniker f[uü]r automat",
    re.I)

# rule 85, his instruction. He uses computer vision and does not want to research or
# develop its algorithms, so a role whose SUBJECT is computer vision is out while
# perception work stays in.
#
# This is a title rule on purpose. I tried to separate algorithm development from
# applied vision by reading the description for research verbs against deployment
# verbs, and it does not work. "PhD preferred" appears as a qualification in roles
# that are plainly applied, which inflates the research side, and a thin advert
# scores zero both ways. The title is what states whose job it is.
#
# "perception" is deliberately absent from this pattern. He said perception includes
# computer vision and that only the computer vision roles go.
R85_VISION_ROLE = re.compile(
    r"computer vision|machine vision|\bvision\b (engineer|scientist|developer|specialist)|"
    r"image processing|bildverarbeitung|\bcv\b engineer", re.I)
# A title whose role noun is his, with vision as the setting rather than the job,
# stays. "Embedded Vision Software Engineer" is his field; "Computer Vision
# Engineer" is not.
R85_ANCHOR = re.compile(
    r"embedded|firmware|microcontroller|mikrocontroller|\brtos\b|\bbsp\b|"
    r"robotic|robotik|\bros2?\b|autonom|\badas\b|automotive|avionic|aerospace|"
    r"\bsoc\b|driver|kernel|real.?time|echtzeit", re.I)

# rule 86, his instruction, and he drew the line himself. Qt works. Working on
# embedded Linux works. Kernel development and operating system development do not.
#
# So the test is whether the platform is the product. A role building the Linux
# platform itself, meaning the kernel, a BSP, a Yocto distribution, a bootloader or
# a device tree, is out. A role writing software that runs on embedded Linux is in,
# which is why "Embedded Linux Engineer" passes and "Embedded Linux Engineer
# (Yocto)" does not. He named Yocto himself.
R86_PLATFORM = re.compile(
    r"\bkernel\b|\byocto\b|board support package|\bbsp\b|buildroot|\bu.boot\b|"
    r"\buboot\b|device tree|\bdistro\b|\bhypervisor\b|silicon enablement|"
    r"operating system (developer|engineer|development)|\bos\b development|"
    r"betriebssystem.?entwickl", re.I)

R10_MECH_TITLE = re.compile(
    r"\bcae\b|\bfea\b|\bcfd\b|\bnvh\b|konstrukteur|konstruktion(singenieur)?|"
    r"berechnungsingenieur|maschinenbauingenieur|zerspanungsmechanik|"
    r"werkzeugmechanik|technische.?r? zeichner|stress engineer|"
    r"mechanical design|design engineer mechanic|ing[eé]nieur m[eé]canique",
    re.I)
# The number of strong terms a description may carry before it reads as mechanical.
# One is a passing mention, such as an embedded role that also releases a drawing.
R10_MECH_FLOOR = 2
# The areas that name a discipline rather than a market. A description carrying
# mechanical practice is kept only when one of these is present, because then the
# posting is a software role in a mechanical setting rather than a mechanical role.
DISCIPLINE = {"embedded", "c++", "control", "signal/ml", "v&v", "autonomy"}

HIS_WORK = {
    "embedded":   r"embedded|firmware|microcontroller|bare.?metal|\brtos\b|freertos|yocto|\bbsp\b",
    # the lookahead keeps robotic process automation out, which is office software
    # and not a robot. An insurance group's "robotics und Prozessautomatisierung"
    # counted as robotics work before it was here.
    "robotics":   r"\brobot(?!ic\s?process|ics\s?process|ics? und prozess)|robotik|cobot|\bros2?\b|manipulator",
    # "\bcan\b" stood here for the CAN bus and matched the English verb instead, so a
    # commodity trader writing "we can offer" counted as automotive work. The bus is
    # always written with its suffix, so the suffix is required.
    "automotive": (r"\badas\b|autosar|automotive|vehicle dynamic|powertrain|flexray|"
                   r"\bcan.?bus\b|\bcan.?fd\b|canopen|\bcan\b (bus|protocol|"
                   r"communication|kommunikation)|\bj1939\b|\bobd\b"),
    "autonomy":   r"autonom|\bslam\b|motion planning|path planning|perception|sensor fusion",
    "aero/space": r"aerospace|avionic|satellit|spacecraft|flight software|\buav\b|drone",
    "c++":        r"\bc\+\+|\bc/c\+\+",
    "control":    r"control (system|loop|algorithm)|closed.?loop|regelung|\bpid\b|state estimation",
    "signal/ml":  r"signal processing|\bdsp\b|radar|computer vision|machine learning|deep learning|neural network",
    "v&v":        r"\bhil\b|\bsil\b|processor.?in.?the.?loop|mc/dc|gtest|aspice|iso 26262",
}

# ===================================================================== THE TRADES
# A reject rule that runs on the title only cannot work, and that single mistake let
# in every posting he has had to point out. The title stage carried eight reject
# rules and the description stage carried one admit rule, so a posting with a clean
# title and one keyword in its description always got through.
#
# So the trades are a table, and the table runs at the description as well as the
# title. A new ruling from him is a row here plus a case in screen-cases.tsv, never
# a patch at one stage.
#
# `floor` is how many distinct terms are needed, because one term can be a passing
# mention. `core_guard` means the reject is waived when the description names his own
# discipline, which is what separates a PLC role from a C++ role that talks to a PLC.
# A rule whose trade IS his language, such as the Windows one, sets it to False,
# since a Windows C++ role names C++ by definition.
R_PLC = re.compile(
    r"\bplc\b|\bsps\b|programmable logic|step ?7|tia.?portal|codesys|siemens s7|"
    r"beckhoff|twincat|allen.?bradley|profinet|profibus|speicherprogrammierbar|"
    r"\bwincc\b|\bscada\b|\bhmi\b panel|leitsystem", re.I)
R_FPGA = re.compile(
    r"\bfpga\b|\bvhdl\b|verilog|systemverilog|\brtl\b|\basic\b|xilinx|altera|"
    r"\bzynq\b|quartus|vivado|high.?level synthesis|\bhdl\b|"
    # "\buvm\b" stood here for the UVM verification methodology and matched the
    # German abbreviation u.v.m., meaning "und vieles mehr", in two lift engineer
    # adverts. A three letter acronym that is also an ordinary abbreviation needs
    # its own words, so the methodology is written out instead.
    r"universal verification methodology|"
    r"timing closure|synthes(is|e) constraint", re.I)
R_RPA = re.compile(
    r"robotic process|\brpa\b|uipath|blue prism|power automate|workforce management|"
    r"business process (automation|management)|\bitil\b|\bservicenow\b", re.I)

# His own disciplines, in the words a description uses. Deliberately NOT the market
# words robotics, automotive or aerospace, because those appear in every advert a
# company in that market writes, whatever the discipline it is hiring for. Reading a
# market word as evidence of his work is the single error behind the Tesla CAE role,
# the commodity trader and the insurance group leader.
CORE = re.compile(
    r"\bc\+\+|\bc/c\+\+|\bembedded\b|\bfirmware\b|microcontroller|mikrocontroller|"
    r"bare.?metal|\brtos\b|freertos|\byocto\b|\bbsp\b|device driver|"
    r"\blinux\b|\bros2?\b|autosar|\bcan.?bus\b|\bslam\b|sensor fusion|"
    r"computer vision|motion planning|\bhil\b|\bsil\b|mc/dc", re.I)

TRADES = [
    # (reason, pattern, floor, core_guard)
    ("rule 10, PLC and the programmable controller trade", R_PLC, 1, True),
    ("rule 10, FPGA and RTL design", R_FPGA, 1, True),
    ("rule 79, mechanical engineering", R10_MECH_STRONG, 2, True),
    ("not his field, office and process automation", R_RPA, 1, True),
]


def trade_verdict(text):
    """(reason, terms) for the first trade the text is actually about, or (None, None).

    A trade term plus none of his disciplines is a posting in that trade. A trade
    term alongside his disciplines is a posting in his field that talks to that
    trade, which is Alpitronic naming FPGA beside firmware and Gerhard Schubert
    naming TwinCAT beside C++ and ROS.
    """
    has_core = bool(CORE.search(text))
    for reason, pat, floor, guard in TRADES:
        hits = {m.group(0).lower() for m in pat.finditer(text)}
        if len(hits) < floor:
            continue
        if guard and has_core:
            continue
        return reason, sorted(hits)
    return None, None


# rule 2, a stated figure in the description
DESC_YEARS = re.compile(r"\b(\d{1,2})\s*(?:\+|plus)?\s*(?:years?|yrs?|jahre|jahren|anni|ans)\b", re.I)
_YEARS_CONTEXT = ("experience", "erfahrung", "esperienza", "experiencia", "berufserfahrung")

# 04. preferences 1.0 lists Hybrid and Onsite, so a fully remote role is outside it
FULLY_REMOTE = re.compile(r"\b(fully|100%|completely|entirely)[- ]?remote\b|"
                          r"\bremote[- ]?(first|only)\b|work from anywhere|"
                          r"\bvollst[aä]ndig remote\b", re.I)

# rule 87, his amendment to rule 6. A language requirement still flags rather than
# rejects, except when the posting states C1 or C2 outright, which is beyond what he
# can reach for the application and so ends the posting.
#
# English is excluded by design. His CV states English C1 and German A2, so an
# English C1 or C2 demand is already met and must not reject anything. 29 of the
# C1/C2 demands in the corpus are for English and 88 are for German.
# Each language in its own tongue as well as in English and German, because a
# posting states its language requirement in the language it is written in. A
# French advert says "Niveau C1 en français", which the English and German spellings
# alone did not reach.
C1_OTHER = re.compile(
    r"german|deutsch|allemand|duits|tyska|"
    r"french|franz[oö]sisch|fran[cç]ais|frans|franska|"
    r"dutch|niederl[aä]ndisch|n[eé]erlandais|nederlands|"
    r"swedish|schwedisch|su[eé]dois|svenska|"
    r"spanish|spanisch|espagnol|espa[nñ]ol|"
    r"italian|italienisch|italien|italiano", re.I)
C1_ENGLISH = re.compile(r"english|englisch|anglais|engels|engelska", re.I)
C1_LEVEL = re.compile(r"\b(c1|c2)\b", re.I)
# the same sentence framed as a wish rather than a bar, which flags as before
R87_OPTIONAL = re.compile(r"\bplus\b|nice to have|advantage|ideally|vorteil|"
                          r"w[uü]nschenswert|optional|bonus", re.I)


def demands_c1(text):
    """The level a posting demands in a language he does not hold, or None.

    Resolved by nearest language word rather than by one regex. A single pattern
    spanning language to level broke on "Sehr gute Deutsch- (mind. C1)", because the
    abbreviation's full stop fell inside the span, and widening the span to any
    character made it cross sentence boundaries and read an English level as a
    German one.
    """
    for m in C1_LEVEL.finditer(text):
        lo, hi = max(0, m.start() - 70), m.end() + 70
        window = text[lo:hi]
        if R87_OPTIONAL.search(window):
            continue                      # a wish rather than a bar, rule 6 applies
        # The language on the LEFT of the level binds to it, because both English
        # and German put the language first, as in "Deutschkenntnisse (mindestens
        # C2-Niveau)" and "Fluent English (C1)". Nearest-word resolution failed
        # here, since "und gute Englischkenntnisse" trailing the clause sat closer
        # to the level than the Deutsch it belonged to.
        left = [(m.start() - x.end(), "other") for x in C1_OTHER.finditer(window)
                if x.end() + lo <= m.start()]
        left += [(m.start() - x.end(), "english") for x in C1_ENGLISH.finditer(window)
                 if x.end() + lo <= m.start()]
        right = [(x.start() - m.end(), "other") for x in C1_OTHER.finditer(window)
                 if x.start() + lo >= m.end()]
        right += [(x.start() - m.end(), "english") for x in C1_ENGLISH.finditer(window)
                  if x.start() + lo >= m.end()]
        near = left or right
        if not near:
            continue                      # a C1 that names no language is not this
        if min(near)[1] == "other":
            return m.group(1).upper()
    return None


# rule 6, a language requirement flags and never rejects
GERMAN_REQUIRED = re.compile(
    r"(german|deutsch)\w*[^.]{0,60}\b(c1|c2|b2|fluent|flie[sß]end|verhandlungssicher|"
    r"native|muttersprach|required|erforderlich|vorausgesetzt|zwingend)\b", re.I)
GERMAN_OPTIONAL = re.compile(r"(german|deutsch)\w*[^.]{0,60}\b(nice to have|plus|advantage|"
                             r"vorteil|w[uü]nschenswert|optional|a1|a2|b1)\b", re.I)


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


def clean_company(c):
    """The employer's name without its profile tagline.

    A portal's company field carries marketing, so FERCHAU reads as
    "FERCHAU - Connecting People and Technologies". The tagline is display, not
    information, and it made the review list unreadable.
    """
    c = re.split(r"\s*[|•·]\s*|\s+[-–—]\s+", c or "")[0]
    c = re.sub(r"\s*,?\s*(a |an )?part of .*$", "", c, flags=re.I)
    c = re.sub(r"\s*,?\s*a [\w\s]+ company$", "", c, flags=re.I)
    return c.strip() or "unknown"


def screen_title(title, company, location, cell=None):
    """(keep, reason, flags) on the title and the lister alone.

    Generous by design. A description now costs an anonymous request of about a
    third of a second, so this stage exists to avoid paying for thousands of them,
    not to decide fit.

    `cell` carries the country the query asked for. The state check of rule 84 needs
    it, and would misfire on a bare town name without it.
    """
    t, c, loc = norm(title), norm(clean_company(company)), norm(location)
    searched = places.searched_country(cell)
    country = places.country_of(location, searched) or searched
    flags = []

    if any(a in c for a in R10_BOARD):
        return False, "rule 10, agency repost", flags
    if re.search(R3, t):
        return False, "rule 3, below the level floor", flags
    if re.search(R2_TITLE, t):
        return False, "rule 2, seniority above the ceiling", flags
    if re.search(R2_YEARS, t):
        return False, "rule 2, title states more than five years", flags
    if re.search(R10_CHIP, t):
        return False, "rule 10, semiconductor chip design", flags
    if re.search(NOT_INTERESTED, t):
        return False, "not his field, sales or the Microsoft stack", flags
    if R10_MECH_TITLE.search(t):
        return False, "rule 79, mechanical engineering", flags
    if R_PLC_TITLE.search(t):
        return False, "rule 10, PLC and the programmable controller trade", flags
    if R85_VISION_ROLE.search(t) and not R85_ANCHOR.search(t):
        return False, "rule 85, the role itself is computer vision", flags
    if R86_PLATFORM.search(t):
        return False, "rule 86, the platform is the product, kernel or OS work", flags

    role = [k for k, p in ROLES.items() if re.search(p, t)]
    domain = [k for k, p in DOMAINS.items() if re.search(p, t)]
    if not role and not domain:
        return False, "names none of his ten roles or eight domains", flags

    state = places.state_of(location, searched)
    if state in EXCLUDED_STATES:
        return False, f"rule 84, {state} is out of scope", flags

    is_agency = any(x in c for x in R12_AGENCY)
    if is_agency:
        flags.append("agency")

    # His instruction supersedes the EU scope. He does not want defence roles, and he
    # did not qualify that by market, so the country test is gone.
    if re.search(R11_TITLE, t) or any(x in c for x in R11_EMPLOYER):
        return False, "rule 11, defence", flags

    return True, ",".join(role + domain), flags


def stated_years(text):
    """The largest required-years figure the description states, or None."""
    best = None
    for m in DESC_YEARS.finditer(text):
        v = int(m.group(1))
        if 1 <= v <= 25:
            ctx = text[max(0, m.start() - 60):m.end() + 60].lower()
            if any(k in ctx for k in _YEARS_CONTEXT):
                best = v if best is None else max(best, v)
    return best


def screen_description(text, location, allowed=None, cell=None):
    """(keep, reason, areas, flags) on the description itself.

    The order is deliberate. Location first because it is certain, then the hard
    preference checks, then whether the work described is his at all.

    `cell` is the ledger row's sweep cell. It carries the country the query asked
    for, which settles a town name held by two countries and supplies the country
    for a town the gazetteer does not hold. Passing it is not optional in the
    pipeline, because without it a bare German town name is unresolvable and 88
    postings were dropped that way in one run.
    """
    flags = []
    ok, why = places.in_preferences(location, allowed, cell)
    if not ok:
        return False, why, [], flags

    state = places.state_of(location, places.searched_country(cell))
    if state in EXCLUDED_STATES:
        return False, f"rule 84, {state} is out of scope", [], flags

    y = stated_years(text)
    if y is not None and y > 5:
        return False, f"rule 2, states {y} years", [], flags
    if y is not None:
        flags.append(f"{y}y stated")

    if FULLY_REMOTE.search(text):
        return False, "fully remote, outside his workplace preference", [], flags

    # rule 87, an explicit C1 or C2 in a language he does not hold ends the posting
    level = demands_c1(text)
    if level:
        return False, f"rule 87, the posting demands {level}", [], flags

    # rule 6, a language requirement below that flags and never rejects
    if GERMAN_REQUIRED.search(text) and not GERMAN_OPTIONAL.search(text):
        flags.append("German")

    t = norm(text)
    areas = [k for k, p in HIS_WORK.items() if re.search(p, t)]
    if not areas:
        return False, "the description names none of his work", [], flags

    # rule 11 on the description, because the lister's title hides the work. Checked
    # after the areas, so the reason names the real cause rather than an empty match.
    if r11_is_the_role(text):
        return False, "rule 11, the description is defence work", [], flags

    # the trades, run on the description. This is the stage that was missing.
    reason, terms = trade_verdict(text)
    if reason:
        return False, f"{reason} ({', '.join(terms[:4])})", [], flags

    # rule 80, the Windows desktop and the Microsoft stack. Read from the work, not
    # from the title, because a C++ title says nothing about what the C++ is for.
    ms_s = set(m.group(0).lower() for m in MS_STRONG.finditer(text))
    ms_w = set(m.group(0).lower() for m in MS_WEAK.finditer(text))
    if ms_s or len(ms_w) >= 2:
        named = sorted(ms_s) + sorted(ms_w)
        return False, ("rule 80, the Windows desktop and Microsoft stack "
                       f"({', '.join(named[:4])})"), [], flags

    return True, why, areas, flags
