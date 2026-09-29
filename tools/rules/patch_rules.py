"""Apply the WWII gameplay changes to rulesmd.ini (Yuri's Revenge + Ares only).

    python3 patch_rules.py ORIGINAL_rulesmd.ini OUTPUT_rulesmd.ini [ORIGINAL_artmd.ini OUTPUT_artmd.ini]

Starts from the original file of the mod and applies every change in one go,
so running it again always gives the same result. Only YR / Ares tags are used.
"""
import re
import sys

# ---------------------------------------------------------------- ini helpers


class Ini:
    def __init__(self, data):
        self.lines = data.split(b'\n')
        self._idx = None

    def _sections(self):
        if self._idx is not None:
            return self._idx
        idx = {}
        for i, l in enumerate(self.lines):
            m = re.match(rb'\s*\[([^\]]+)\]', l)
            if m:
                idx.setdefault(m.group(1).strip().upper().decode('latin1'), i)
        self._idx = idx
        return idx

    def _range(self, sec):
        idx = self._sections()
        start = idx.get(sec.upper())
        if start is None:
            return None, None
        end = len(self.lines)
        for j in range(start + 1, len(self.lines)):
            if self.lines[j].lstrip().startswith(b'['):
                end = j
                break
        return start, end

    def get(self, sec, key):
        s, e = self._range(sec)
        if s is None:
            return None
        for j in range(s + 1, e):
            m = re.match(rb'\s*([^=;]+?)\s*=\s*([^;\r]*)', self.lines[j])
            if m and m.group(1).decode('latin1').lower() == key.lower():
                return m.group(2).strip().decode('latin1')
        return None

    def has(self, sec):
        return self._range(sec)[0] is not None

    def set(self, sec, key, value):
        s, e = self._range(sec)
        if s is None:
            raise KeyError('section [%s] not found' % sec)
        line = ('%s=%s' % (key, value)).encode('latin1')
        for j in range(s + 1, e):
            m = re.match(rb'\s*([^=;]+?)\s*=', self.lines[j])
            if m and m.group(1).decode('latin1').lower() == key.lower():
                self.lines[j] = line
                return
        k = e
        while k > s + 1 and self.lines[k - 1].strip() == b'':
            k -= 1
        self.lines.insert(k, line)
        self._idx = None

    def set_everywhere(self, sec, key, value):
        """Set a key in every section with this name (the file has a few
        duplicated sections; the game merges them, later keys winning)."""
        starts = [i for i, l in enumerate(self.lines)
                  if re.match(rb'\s*\[' + re.escape(sec.encode('latin1')) + rb'\]', l, re.I)]
        line = ('%s=%s' % (key, value)).encode('latin1')
        for s in reversed(starts):
            e = next((j for j in range(s + 1, len(self.lines)) if self.lines[j].lstrip().startswith(b'[')),
                     len(self.lines))
            for j in range(s + 1, e):
                m = re.match(rb'\s*([^=;]+?)\s*=', self.lines[j])
                if m and m.group(1).decode('latin1').lower() == key.lower():
                    self.lines[j] = line
        self._idx = None

    def all_values(self, sec, key):
        out = []
        starts = [i for i, l in enumerate(self.lines)
                  if re.match(rb'\s*\[' + re.escape(sec.encode('latin1')) + rb'\]', l, re.I)]
        for s in starts:
            e = next((j for j in range(s + 1, len(self.lines)) if self.lines[j].lstrip().startswith(b'[')),
                     len(self.lines))
            for j in range(s + 1, e):
                m = re.match(rb'\s*([^=;]+?)\s*=\s*([^;\r]*)', self.lines[j])
                if m and m.group(1).decode('latin1').lower() == key.lower():
                    out.append(m.group(2).strip().decode('latin1'))
        return out

    def list_section(self, sec):
        s, e = self._range(sec)
        out = []
        if s is None:
            return out
        for j in range(s + 1, e):
            m = re.match(rb'\s*[^=;]+?\s*=\s*([^;\r]*)', self.lines[j])
            if m and m.group(1).strip():
                out.append(m.group(1).strip().decode('latin1'))
        return out

    def delete(self, sec, key):
        s, e = self._range(sec)
        if s is None:
            return
        for j in range(e - 1, s, -1):
            m = re.match(rb'\s*([^=;]+?)\s*=', self.lines[j])
            if m and m.group(1).decode('latin1').lower() == key.lower():
                del self.lines[j]
                self._idx = None

    def append(self, text):
        if self.lines and self.lines[-1].strip() != b'':
            self.lines.append(b'')
        self.lines.extend(text.strip('\n').encode('latin1').split(b'\n'))
        self.lines.append(b'')
        self._idx = None

    def data(self):
        return b'\n'.join(self.lines)


def sections_of(text):
    return [m.group(1) for m in re.finditer(r'^\[([^\]]+)\]', text, re.M)]


# ------------------------------------------------ 1. flight attitude fixes
# Low or missing PitchSpeed made aircraft keep chasing their pitch angle and
# show ghost images; RollAngle tilted aircraft on the airfield.
PITCH_SPEED_FIX = ['A10W', 'KPLN', 'JAFSD', 'JAGDS', 'STFIGHTER', 'GERR', 'GERS', 'GERL', 'HORNET', 'J35', 'SU34']
ATTITUDE = {('STFIGHTER', 'PitchAngle'): '0', ('STFIGHTER', 'RollAngle'): '0', ('B2BOMBER', 'RollAngle'): '0'}

# ------------------------------------------------ 2. WWII fighters
# How YR works (see Phobos docs on vanilla behaviour):
# * An aircraft strafes -- flies a straight gun run over the target, firing
#   5 times along its path, then turns back for the next run -- when its
#   weapon's projectile has ROT < 2 and Inviso=no. Ammo is deducted once per
#   run. In vanilla YR / Ares only the FIRST of the 5 shots uses Burst, so the
#   dense part of the run comes from a big Burst on the opening shot.
# * A projectile without Inaccurate "snaps" to its target on impact and counts
#   as a direct hit. Inaccurate=yes removes that, so a small-splash bullet
#   deals no damage (what happened in the previous version). Ares
#   BallisticScatter only works on Arcing=yes projectiles anyway.
# * The fighters that already worked in the air (GERS, FERD, GERZ...) use one
#   weapon with AA=yes and AG=yes; the new guns follow that layout.
# The old weapons were homing (ROT=104) with ROF=5, Burst=10, Speed=165.
#
# unit: (aircraft, Speed, ROT, Strength, Ammo = strafing runs, weapon)
# Speed ~ real top speed / 60 km/h; ROT from manoeuvrability; Strength from
# ruggedness.
FIGHTERS = {
    'ORCA':      ('P-40E Warhawk',        10, 4, 340, 3, 'WW2_US50_P40'),
    'AORCA':     ('P-40E Warhawk',        10, 4, 340, 3, 'WW2_US50_P40'),
    'BEAG':      ('P-51D Mustang',        12, 4, 320, 3, 'WW2_US50'),
    'F2002':     ('F4U-1D Corsair',       11, 4, 380, 3, 'WW2_US50'),
    'FERD':      ('Typhoon Mk.Ib',        11, 3, 400, 3, 'WW2_Hispano4'),
    'GERS':      ('Spitfire Mk.IX',       11, 5, 320, 3, 'WW2_Hispano'),
    'BEAG2':     ('Me 262A-1a',           14, 3, 330, 2, 'WW2_MK108'),
    'GERZ':      ('Bf 109G-6',            11, 4, 300, 3, 'WW2_MG151'),
    'GERL':      ('Ju 87G-2 Kanonenvogel', 7, 3, 380, 3, 'WW2_BK37'),
    'MIG2000':   ('Fw 190F-8',            10, 4, 400, 3, 'WW2_Fw190Guns'),
    'FIREFOX':   ('MC.205V Veltro',       11, 5, 300, 3, 'WW2_MC205Guns'),
    'STFIGHTER': ('Yak-3',                11, 6, 290, 3, 'WW2_ShVAK_Yak'),
    'GERN':      ('La-5FN',               11, 5, 340, 3, 'WW2_ShVAK_La'),
    'JAPVP':     ('A6M2 Zero',             9, 6, 240, 2, 'WW2_Type99'),
    'JAGDS':     ('Ki-84-I Hayate',       11, 5, 310, 3, 'WW2_Ho5'),
    'F23':       ('Ki-61-I Hien',         10, 4, 320, 3, 'WW2_Ho103'),
    'STBOMBER':  ('P-38L Lightning',      11, 3, 380, 3, 'WW2_P38Nose'),
}

# Skins (base unit + A/B/C): same WWII weapon as the base with the skin's
# bonuses from the 104-skin design list, applied to the new stats.
# skin: (base unit, damage x, ROF x, Ammo +, Speed +, Strength x)
SKIN_UNITS = {
    'FALCA':    ('ORCA',    1.00, 1.00, 0, 0, 1.12),   # hp +12% (as before)
    'BEAGA':    ('BEAG',    1.00, 1.00, 0, 1, 1.10),   # hp +10%, speed +1 (as before)
    'F2002A':   ('F2002',   1.00, 0.90, 0, 0, 1.00),   # air superiority: faster fire
    'F2002B':   ('F2002',   0.80, 1.00, 2, 1, 1.00),   # long sorties: ammo +2, speed +1, dmg -20%
    'F2002C':   ('F2002',   1.12, 1.00, 0, 1, 1.00),   # dmg +12%, speed +1
    'FERDA':    ('FERD',    1.15, 1.00, 0, 0, 1.10),   # dmg +15%, hp +10%
    'FERDB':    ('FERD',    1.00, 0.87, 1, 2, 0.90),   # interceptor: speed +2, ammo +1, faster, hp -10%
    'GERNA':    ('GERN',    0.90, 1.00, 1, 0, 1.00),   # air superiority: ammo +1
    'GERNB':    ('GERN',    1.20, 1.00, 0, 0, 1.00),   # heavy strike: dmg +20%
    'GERNC':    ('GERN',    0.80, 1.00, 2, -1, 1.00),  # endurance: ammo +2, dmg -20%, speed -1
    'GERND':    ('GERN',    1.10, 1.00, 0, -1, 1.15),  # anti-armour: dmg +10%, hp +15%, speed -1
    'GERSA':    ('GERS',    1.10, 1.00, 0, 0, 1.00),   # dmg +10%
    'GERZA':    ('GERZ',    1.15, 1.00, 0, 0, 1.10),   # dmg +15%, hp +10%
    'GERZB':    ('GERZ',    0.80, 1.00, 2, 1, 1.00),   # ammo +2, speed +1, dmg -20%
    'MIG2000A': ('MIG2000', 0.78, 1.00, 1, 0, 1.00),   # ammo +1, dmg -22%
}
# skins whose art section pointed at the base model; they get their own model
ART_OWN_IMAGE = ['FERDA', 'FERDB', 'GERNA', 'GERNB', 'GERNC', 'GERND', 'GERSA', 'GERZA', 'GERZB']
AIR_RANGE_BONUS = 6

# weapon: (Damage, Burst, ROF, projectile Speed, Range, Projectile, Warhead, Report, Anim)
# One strafing run = Burst rounds on the opening shot + 4 single rounds.
# Short Range: the aircraft opens fire close to the target, so the tracers go
# down in a short straight line instead of being lobbed from far away.
GUN = ('ArnoldAttack', 'MGMUZZLE')
WEAPONS = {
    'WW2_US50_P40':    (15, 10, 3, 160, 5, 'WW2_StrafeGunP', 'WW2_MG50WH') + GUN,       # 6 x .50
    'WW2_US50':        (16, 10, 3, 160, 5, 'WW2_StrafeGunP', 'WW2_MG50WH') + GUN,       # 6 x .50
    'WW2_Hispano':     (22, 8, 4, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # 2 x 20 mm + 2 x .50
    'WW2_Hispano4':    (23, 9, 4, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # Typhoon 4 x 20 mm
    'WW2_MG151':       (21, 8, 4, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # MG 151/20 + 2 x MG 131
    'WW2_Fw190Guns':   (23, 9, 4, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # 2 x MG 151/20 + 2 x MG 131
    'WW2_MC205Guns':   (21, 8, 4, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # 2 x MG 151/20 + 2 x Breda
    'WW2_ShVAK_Yak':   (20, 8, 3, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # ShVAK + 2 x UBS
    'WW2_ShVAK_La':    (22, 8, 4, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # 2 x ShVAK
    'WW2_Type99':      (21, 6, 5, 140, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # 2 x Type 99 20 mm, slow
    'WW2_Ho5':         (22, 8, 3, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # 2 x Ho-5 + 2 x Ho-103
    'WW2_Ho103':       (20, 8, 3, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # 2 x Ho-5 + 2 x Ho-103
    'WW2_P38Nose':     (20, 10, 3, 150, 5, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,   # concentrated nose battery
    'WW2_MK108':       (55, 6, 6, 130, 5, 'WW2_StrafeGunP', 'WW2_Cannon30WH') + GUN,    # 4 x MK 108 30 mm
    # Ju 87G: Stuka-style dive attack as the old GERL (AirDesem), ground only
    'WW2_BK37':        (45, 8, 4, 95, 10, 'WW2_StukaP', 'WW2_Cannon37APWH') + GUN,     # 2 x BK 3,7
    # carrier aircraft defensive / interception guns (Secondary, as HORNET's
    # original AA Secondary)
    'WW2_CarrierAirGun': (20, 4, 12, 100, 8, 'WW2_AirGunP', 'WW2_AirMGWH') + GUN,
}

PROJECTILES = '''
; ---- WWII aircraft guns --------------------------------------------------
; ROT=1, Inviso=no: strafing runs (same as the old GERL's AirDesem). No
; Inaccurate, so each round snaps to its target and counts as a hit; no
; Ranged, so a round is not cut off before it reaches the target.
[WW2_StrafeGunP]
Image=DART
Inviso=no
Shadow=no
Arcing=no
ROT=1
Proximity=no
Ranged=no
AA=yes
AG=yes
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Arm=0
High=no
VeryHigh=no

; Ju 87G: the old GERL's Stuka-style projectile (AirDesem), ground only
[WW2_StukaP]
Image=DART
Inviso=no
Arm=2
Shadow=no
Ranged=yes
ROT=1
AA=no
AG=yes
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Cluster=2

; carrier aircraft AA guns: homing tracer
[WW2_AirGunP]
Image=DART
Inviso=no
Shadow=no
Arcing=no
ROT=60
Proximity=yes
Ranged=yes
AA=yes
AG=no
Acceleration=8
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Arm=0
High=no
VeryHigh=no
'''

# Verses order: none, flak, plate, light, medium, heavy, wood, steel, concrete, special_1, special_2
WARHEADS = '''
; ---- WWII aircraft warheads -----------------------------------------------
; .50 cal / 12.7 mm machine guns: deadly to infantry and soft vehicles,
; almost nothing against a Tiger's armour.
[WW2_MG50WH]
CellSpread=.5
PercentAtMax=.7
Verses=100%,85%,70%,55%,30%,8%,40%,20%,8%,30%,100%
InfDeath=1
AnimList=PIFFPIFF,PIFF
Bullets=yes
ProneDamage=60%
Wall=no
Wood=yes

; 20 mm cannon: good against light vehicles, weak against heavy tanks
[WW2_Cannon20WH]
CellSpread=.6
PercentAtMax=.7
Verses=100%,90%,80%,70%,45%,15%,60%,35%,15%,40%,100%
InfDeath=3
AnimList=TWLT050,S_CLSN58
ProneDamage=60%
Wall=no
Wood=yes

; 30 mm MK 108 mine shell
[WW2_Cannon30WH]
CellSpread=.8
PercentAtMax=.6
Verses=100%,95%,90%,85%,60%,25%,85%,50%,25%,50%,100%
InfDeath=3
AnimList=S_CLSN58
ProneDamage=60%
Conventional=yes
Wall=yes
Wood=yes

; 37 mm tungsten AP (Ju 87G): hits tanks through the thin top/rear armour
[WW2_Cannon37APWH]
CellSpread=.4
PercentAtMax=.8
Verses=60%,50%,55%,90%,90%,75%,40%,45%,30%,60%,100%
InfDeath=3
AnimList=S_CLSN58
ProneDamage=50%
Conventional=yes
Wall=yes
Wood=yes

; carrier aircraft AA guns
[WW2_AirMGWH]
CellSpread=.15
PercentAtMax=.5
Verses=100%,90%,80%,75%,60%,35%,50%,30%,10%,40%,100%
InfDeath=1
AnimList=PIFFPIFF,PIFF
Bullets=yes
Wall=no
Wood=yes
'''


def weapon_block(name, spec, elite=False):
    dmg, burst, rof, speed, rng, proj, wh, report, anim = spec
    if elite:
        dmg = int(round(dmg * 1.15))
        rof = max(rof - 1, 1)
        rng = rng + 0.5
    lines = ['[%s%s]' % (name, 'E' if elite else ''), 'Damage=%d' % dmg, 'ROF=%d' % rof, 'Range=%s' % rng,
             'Projectile=%s' % proj, 'Speed=%d' % speed, 'Warhead=%s' % wh, 'Report=%s' % report,
             'Burst=%d' % burst]
    if anim:
        lines += ['Anim=%s' % anim, 'Bright=yes']
    return '\n'.join(lines) + '\n'


# ------------------------------------------------ 3. aircraft carriers
# Auto-launch within (launcher range - 10) and intercept enemy aircraft.
CARRIERS = {'CARRIER': ('HornetLauncher', 'HORNET'),
            'NIMITZ': ('J35Launcher', 'J35'),
            'NODCARRI': ('SU34Launcher', 'SU34')}
CARRIER_SIGHT = 12

# ------------------------------------------------ 4. the Tiger's gun can miss
# Only the Tiger (CRUSADER and its three skins) is changed; every other tank
# keeps the original rules.
# Its shells used the shared HeavyShellP_D3/D7 with ROT=1: ROT above 0 is a
# homing round, which follows its target, so it could never miss. Ares
# BallisticScatter only applies to Inaccurate=yes AND Arcing=yes projectiles,
# so the Tiger gets its own copies of those projectiles as flat ballistic
# rounds (faster weapon speed keeps the arc low). The warheads are untouched:
# BoocAPa has 1.8 cells of splash, so the scatter reaches beyond that for a
# real miss.
TIGERS = ['CRUSADER', 'CRUSADERA', 'CRUSADERB', 'CRUSADERC']
TIGER_SCATTER = ('0.6', '2.6')
TIGER_SHELL_SPEED = 450
# Gattling (cannon stage -> machine gun stage, Ares Gattling.Cycle): the old
# Stage1 was ROF+12, so the cannon could fire twice in its stage and the
# second reload ran past the end of the machine gun stage -- the MG never
# fired. Now the cannon stage ends just before the cannon reloads (one shot
# per cycle) and the MG gets MG_WINDOW frames after the reload.
MG_WINDOW = 60


def weapons_of(ini, unit):
    out = []
    for k in ('Primary', 'Secondary', 'ElitePrimary', 'EliteSecondary'):
        v = ini.get(unit, k)
        if v and v.lower() != 'none':
            out.append(v)
    n = ini.get(unit, 'WeaponCount')
    if n:
        for i in range(1, int(n) + 1):
            for k in ('Weapon%d' % i, 'EliteWeapon%d' % i):
                v = ini.get(unit, k)
                if v:
                    out.append(v)
    return out


def main(src, dst):
    ini = Ini(open(src, 'rb').read())
    log = []

    for u in PITCH_SPEED_FIX:
        ini.set(u, 'PitchSpeed', '1.1')
    for (u, k), v in ATTITUDE.items():
        ini.set(u, k, v)
    log.append('PitchSpeed=1.1 for %s; attitude fixes %s' % (', '.join(PITCH_SPEED_FIX), ATTITUDE))

    # new projectiles / warheads / weapons
    text = PROJECTILES + WARHEADS + '\n; ---- WWII aircraft weapons ------------------------------------------------\n'
    for name, spec in WEAPONS.items():
        text += weapon_block(name, spec) + '\n' + weapon_block(name, spec, elite=True) + '\n'
    for sec in sections_of(text):
        assert not ini.has(sec), 'section [%s] already exists' % sec
    ini.append(text)

    for unit, (plane, speed, rot, hp, ammo, weapon) in FIGHTERS.items():
        ini.set(unit, 'Primary', weapon)
        ini.set(unit, 'ElitePrimary', weapon + 'E')
        ini.delete(unit, 'Secondary')
        ini.delete(unit, 'EliteSecondary')
        ini.set(unit, 'Speed', speed)
        ini.set(unit, 'ROT', rot)
        ini.set(unit, 'Strength', hp)
        ini.set(unit, 'Ammo', ammo)
        ini.set(unit, 'OmniFire', 'yes')          # as the original fighters that could fight in the air
        ini.set(unit, 'Fighter', 'yes')
        ini.set(unit, 'PitchSpeed', '1.1')
        ini.set(unit, 'AirRangeBonus', AIR_RANGE_BONUS)
        log.append('%-9s %-22s Speed=%s ROT=%s Strength=%s Ammo=%s %s' % (unit, plane, speed, rot, hp, ammo, weapon))

    skin_text = ''
    for skin, (base, dm, rm, ammo_add, spd_add, hp_m) in SKIN_UNITS.items():
        _, speed, rot, hp, ammo, weapon = FIGHTERS[base]
        dmg, burst, rof, pspeed, rng, proj, wh, report, anim = WEAPONS[weapon]
        spec = (int(round(dmg * dm)), burst, max(1, int(round(rof * rm))), pspeed, rng, proj, wh, report, anim)
        wname = '%s_%s' % (weapon, skin)
        skin_text += weapon_block(wname, spec) + '\n' + weapon_block(wname, spec, elite=True) + '\n'
        ini.set(skin, 'Primary', wname)
        ini.set(skin, 'ElitePrimary', wname + 'E')
        ini.delete(skin, 'Secondary')
        ini.delete(skin, 'EliteSecondary')
        ini.set(skin, 'Speed', speed + spd_add)
        ini.set(skin, 'ROT', rot)
        ini.set(skin, 'Strength', int(round(hp * hp_m)))
        ini.set(skin, 'Ammo', ammo + ammo_add)
        ini.set(skin, 'OmniFire', 'yes')
        ini.set(skin, 'Fighter', 'yes')
        ini.set(skin, 'PitchSpeed', '1.1')
        ini.set(skin, 'AirRangeBonus', AIR_RANGE_BONUS)
        log.append('  skin %-8s of %-7s Speed=%s Strength=%s Ammo=%s %s dmg=%s ROF=%s' % (
            skin, base, speed + spd_add, int(round(hp * hp_m)), ammo + ammo_add, wname, spec[0], spec[2]))
    for sec in sections_of(skin_text):
        assert not ini.has(sec), sec
    ini.append('; ---- WWII aircraft weapons: skins -----------------------------------------\n' + skin_text)

    for carrier, (launcher, spawn) in CARRIERS.items():
        rng = float(ini.get(launcher, 'Range'))
        ini.set(carrier, 'CanPassiveAquire', 'yes')
        ini.set(carrier, 'GuardRange', '%g' % (rng - 10))
        sight = int(ini.get(carrier, 'Sight') or 0)
        if sight < CARRIER_SIGHT:
            ini.set(carrier, 'Sight', CARRIER_SIGHT)
        ini.set(launcher, 'Projectile', 'Invisible3')          # Inviso, AA=yes AG=yes: can target aircraft
        ini.set(spawn, 'Secondary', 'WW2_CarrierAirGun')
        ini.set(spawn, 'EliteSecondary', 'WW2_CarrierAirGunE')
        log.append('%s: auto-launch within %g cells (range %g), intercepts aircraft, %s gets AA guns' % (
            carrier, rng - 10, rng, spawn))
    assert (ini.get('Invisible3', 'AA') or '').lower() == 'yes'

    # Tiger: private ballistic copies of its shell projectiles
    copies = {}
    tiger_weapons = []
    for unit in TIGERS:
        for k in ('Primary', 'ElitePrimary', 'Weapon1', 'EliteWeapon1'):
            w = ini.get(unit, k)
            if w and w not in tiger_weapons:
                tiger_weapons.append(w)
    for w in tiger_weapons:
        proj = ini.get(w, 'Projectile')
        if proj.upper().startswith('WW2_TIGER'):
            continue
        if proj.upper() not in copies:
            name = 'WW2_Tiger' + proj
            body = ['[%s]' % name]
            s0, e0 = ini._range(proj)
            for line in ini.lines[s0 + 1:e0]:
                t = line.decode('latin1').strip()
                if t and not t.startswith(';') and '=' in t:
                    body.append(t)
            ini.append('\n'.join(body))
            for k, v in (('Arcing', 'yes'), ('ROT', '0'), ('Proximity', 'no'), ('Inaccurate', 'yes'),
                         ('BallisticScatter.Min', TIGER_SCATTER[0]), ('BallisticScatter.Max', TIGER_SCATTER[1])):
                ini.set(name, k, v)
            copies[proj.upper()] = name
        ini.set(w, 'Projectile', copies[proj.upper()])
        ini.set(w, 'Speed', TIGER_SHELL_SPEED)
    for unit in TIGERS:
        rof = int(float(ini.get(ini.get(unit, 'Weapon1'), 'ROF')))
        erof = int(float(ini.get(ini.get(unit, 'EliteWeapon1'), 'ROF')))
        ini.set(unit, 'Stage1', rof - 10)
        ini.set(unit, 'Stage2', rof + MG_WINDOW)
        ini.set(unit, 'EliteStage1', erof - 10)
        ini.set(unit, 'EliteStage2', erof + MG_WINDOW)
        log.append('  %s gattling: cannon ROF %d -> Stage1=%d Stage2=%d (elite ROF %d -> %d / %d)' % (
            unit, rof, rof - 10, rof + MG_WINDOW, erof, erof - 10, erof + MG_WINDOW))
    log.append('Tiger guns %s: ballistic, scatter %s-%s cells, Speed %d, own projectiles %s' % (
        tiger_weapons, TIGER_SCATTER[0], TIGER_SCATTER[1], TIGER_SHELL_SPEED, sorted(copies.values())))

    open(dst, 'wb').write(ini.data())
    print('\n'.join(log))


def patch_art(src, dst):
    art = Ini(open(src, 'rb').read())
    for sec in ART_OWN_IMAGE:
        art.set(sec, 'Image', sec)
    open(dst, 'wb').write(art.data())
    print('artmd: own skin models for %s' % ', '.join(ART_OWN_IMAGE))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
    if len(sys.argv) > 4:
        patch_art(sys.argv[3], sys.argv[4])
