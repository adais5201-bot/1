"""Apply the WWII gameplay changes to rulesmd.ini (Yuri's Revenge + Ares only).

    python3 patch_rules.py ORIGINAL_rulesmd.ini OUTPUT_rulesmd.ini

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

# weapon: (Damage, Burst, ROF, projectile Speed, Range, Projectile, Warhead, Report, Anim)
# One strafing run = Burst rounds on the opening shot + 4 single rounds.
GUN = ('ArnoldAttack', 'MGMUZZLE')
WEAPONS = {
    'WW2_US50_P40':    (20, 6, 5, 100, 10, 'WW2_StrafeGunP', 'WW2_MG50WH') + GUN,        # 6 x .50
    'WW2_US50':        (22, 6, 4, 100, 10, 'WW2_StrafeGunP', 'WW2_MG50WH') + GUN,        # 6 x .50
    'WW2_Hispano':     (30, 4, 5, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # 2 x 20 mm + 2 x .50
    'WW2_Hispano4':    (32, 5, 5, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # Typhoon 4 x 20 mm
    'WW2_MG151':       (28, 4, 5, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # MG 151/20 + 2 x MG 131
    'WW2_Fw190Guns':   (32, 5, 5, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # 2 x MG 151/20 + 2 x MG 131
    'WW2_MC205Guns':   (29, 4, 5, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # 2 x MG 151/20 + 2 x Breda
    'WW2_ShVAK_Yak':   (26, 4, 4, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # ShVAK + 2 x UBS
    'WW2_ShVAK_La':    (30, 4, 5, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # 2 x ShVAK
    'WW2_Type99':      (28, 3, 6, 90, 9, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,      # 2 x Type 99 20 mm, slow
    'WW2_Ho5':         (30, 4, 4, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # 2 x Ho-5 + 2 x Ho-103
    'WW2_Ho103':       (26, 4, 4, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # 2 x Ho-5 + 2 x Ho-103
    'WW2_P38Nose':     (26, 6, 4, 95, 10, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,     # concentrated nose battery
    'WW2_MK108':       (75, 3, 8, 85, 9, 'WW2_StrafeGunP', 'WW2_Cannon30WH') + GUN,      # 4 x MK 108 30 mm
    'WW2_BK37':        (200, 2, 10, 90, 10, 'WW2_StrafeAGP', 'WW2_Cannon37APWH') + GUN,  # 2 x BK 3,7, ground only
    # carrier aircraft defensive / interception guns (Secondary, as HORNET's
    # original AA Secondary)
    'WW2_CarrierAirGun': (20, 4, 12, 100, 8, 'WW2_AirGunP', 'WW2_AirMGWH') + GUN,
}

PROJECTILES = '''
; ---- WWII aircraft guns --------------------------------------------------
; ROT=0, Inviso=no: strafing runs. No Inaccurate, so each round snaps to its
; target and counts as a hit (air or ground).
[WW2_StrafeGunP]
Image=DART
Inviso=no
Shadow=no
Arcing=no
ROT=0
Proximity=no
Ranged=yes
AA=yes
AG=yes
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Arm=0
High=no
VeryHigh=no

; the Ju 87G's 37 mm guns: ground targets only
[WW2_StrafeAGP]
Image=DART
Inviso=no
Shadow=no
Arcing=no
ROT=0
Proximity=no
Ranged=yes
AA=no
AG=yes
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Arm=0
High=no
VeryHigh=no

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
CellSpread=.3
PercentAtMax=.5
Verses=100%,85%,70%,55%,30%,8%,40%,20%,8%,30%,100%
InfDeath=1
AnimList=PIFFPIFF,PIFF
Bullets=yes
ProneDamage=60%
Wall=no
Wood=yes

; 20 mm cannon: good against light vehicles, weak against heavy tanks
[WW2_Cannon20WH]
CellSpread=.35
PercentAtMax=.35
Verses=100%,90%,80%,70%,45%,15%,60%,35%,15%,40%,100%
InfDeath=3
AnimList=TWLT050,S_CLSN58
ProneDamage=60%
Wall=no
Wood=yes

; 30 mm MK 108 mine shell
[WW2_Cannon30WH]
CellSpread=.4
PercentAtMax=.3
Verses=100%,95%,90%,85%,60%,25%,85%,50%,25%,50%,100%
InfDeath=3
AnimList=S_CLSN58
ProneDamage=60%
Conventional=yes
Wall=yes
Wood=yes

; 37 mm tungsten AP (Ju 87G): hits tanks through the thin top/rear armour
[WW2_Cannon37APWH]
CellSpread=.2
PercentAtMax=.5
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
TIGER_SHELL_SPEED = 220


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
        log.append('%-9s %-22s Speed=%s ROT=%s Strength=%s Ammo=%s %s' % (unit, plane, speed, rot, hp, ammo, weapon))

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
        if float(ini.get(w, 'Speed') or 0) < TIGER_SHELL_SPEED:
            ini.set(w, 'Speed', TIGER_SHELL_SPEED)
    log.append('Tiger guns %s: ballistic, scatter %s-%s cells, Speed %d, own projectiles %s' % (
        tiger_weapons, TIGER_SCATTER[0], TIGER_SCATTER[1], TIGER_SHELL_SPEED, sorted(copies.values())))

    open(dst, 'wb').write(ini.data())
    print('\n'.join(log))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
