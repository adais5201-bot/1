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
# Strafing: in YR an aircraft makes straight gun runs (fires along its path,
# flies past the target and turns back) when its ground weapon's projectile
# has ROT < 2 and Inviso=no. The old weapons used homing projectiles
# (ROT=104) with ROF=5, Burst=10 and Speed=165: a hail of fast bullets that
# ended fights at once. Air-to-air uses a separate homing Secondary weapon.
#
# unit: (aircraft, Speed, ROT, Strength, Ammo, ground weapon, air weapon)
# Speed ~ real top speed / 60 km/h; ROT from the type's manoeuvrability;
# Strength from its ruggedness.
FIGHTERS = {
    'ORCA':      ('P-40E Warhawk',        10, 4, 340, 3, 'WW2_US50_P40', 'WW2_AirUS50'),
    'AORCA':     ('P-40E Warhawk',        10, 4, 340, 3, 'WW2_US50_P40', 'WW2_AirUS50'),
    'BEAG':      ('P-51D Mustang',        12, 4, 320, 3, 'WW2_US50', 'WW2_AirUS50'),
    'F2002':     ('F4U-1D Corsair',       11, 4, 380, 3, 'WW2_US50', 'WW2_AirUS50'),
    'FERD':      ('Typhoon Mk.Ib',        11, 3, 400, 2, 'WW2_RP3Rockets', 'WW2_Air20mm'),
    'GERS':      ('Spitfire Mk.IX',       11, 5, 320, 3, 'WW2_Hispano', 'WW2_Air20mm'),
    'BEAG2':     ('Me 262A-1a',           14, 3, 330, 2, 'WW2_MK108', 'WW2_AirMK108'),
    'GERZ':      ('Bf 109G-6',            11, 4, 300, 3, 'WW2_MG151', 'WW2_Air20mm'),
    'GERL':      ('Ju 87G-2 Kanonenvogel', 7, 3, 380, 3, 'WW2_BK37', None),
    'MIG2000':   ('Fw 190F-8',            10, 4, 400, 3, 'WW2_Fw190Guns', 'WW2_Air20mmHeavy'),
    'FIREFOX':   ('MC.205V Veltro',       11, 5, 300, 3, 'WW2_MC205Guns', 'WW2_Air20mm'),
    'STFIGHTER': ('Yak-3',                11, 6, 290, 3, 'WW2_ShVAK_Yak', 'WW2_Air20mmLight'),
    'GERN':      ('La-5FN',               11, 5, 340, 3, 'WW2_ShVAK_La', 'WW2_Air20mm'),
    'JAPVP':     ('A6M2 Zero',             9, 6, 240, 2, 'WW2_Type99', 'WW2_Air20mmLight'),
    'JAGDS':     ('Ki-84-I Hayate',       11, 5, 310, 3, 'WW2_Ho5', 'WW2_Air20mm'),
    'F23':       ('Ki-61-I Hien',         10, 4, 320, 3, 'WW2_Ho103', 'WW2_Air20mmLight'),
    'STBOMBER':  ('P-38L Lightning',      11, 3, 380, 3, 'WW2_P38Nose', 'WW2_Air20mmHeavy'),
}

# weapon: (Damage, Burst, ROF, projectile Speed, Range, Projectile, Warhead, Report, Anim)
GUN = ('ArnoldAttack', 'MGMUZZLE')
WEAPONS = {
    # ground attack (strafing runs): a pass kills a few infantry and takes
    # roughly 10-15% off a light vehicle; only the 37 mm and rockets hurt tanks
    'WW2_US50_P40':    (20, 4, 10, 60, 8, 'WW2_StrafeGunP', 'WW2_MG50WH') + GUN,       # 6 x .50
    'WW2_US50':        (22, 4, 9, 60, 8, 'WW2_StrafeGunP', 'WW2_MG50WH') + GUN,        # 6 x .50
    'WW2_Hispano':     (30, 3, 10, 55, 8, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,   # 2 x 20 mm + 2 x .50
    'WW2_MG151':       (28, 3, 10, 55, 8, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,   # MG 151/20 + 2 x MG 131
    'WW2_Fw190Guns':   (32, 4, 10, 55, 8, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,   # 2 x MG 151/20 + 2 x MG 131
    'WW2_MC205Guns':   (29, 3, 10, 55, 8, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,   # 2 x MG 151/20 + 2 x Breda
    'WW2_ShVAK_Yak':   (26, 3, 9, 55, 8, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # ShVAK + 2 x UBS
    'WW2_ShVAK_La':    (30, 3, 10, 55, 8, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,   # 2 x ShVAK
    'WW2_Type99':      (28, 3, 12, 50, 7, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,   # 2 x Type 99 20 mm, slow
    'WW2_Ho5':         (30, 3, 9, 55, 8, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # 2 x Ho-5 + 2 x Ho-103
    'WW2_Ho103':       (26, 3, 9, 55, 8, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # 2 x Ho-5 + 2 x Ho-103
    'WW2_P38Nose':     (26, 5, 9, 55, 8, 'WW2_StrafeGunP', 'WW2_Cannon20WH') + GUN,    # concentrated nose battery
    'WW2_MK108':       (80, 2, 14, 45, 7, 'WW2_StrafeCannonP', 'WW2_Cannon30WH') + GUN,  # 4 x MK 108 30 mm
    'WW2_BK37':        (200, 1, 22, 50, 8, 'WW2_StrafeCannonP', 'WW2_Cannon37APWH') + GUN,  # 2 x BK 3,7 tank buster
    'WW2_RP3Rockets':  (180, 2, 20, 40, 9, 'WW2_RocketP', 'WW2_RocketWH', 'MigAttack', None),  # RP-3 60 lb rockets
    # air to air: strongly homing tracer, long enough range to engage while
    # both aircraft manoeuvre (needs OmniFire=yes on the fighter)
    'WW2_AirUS50':      (24, 5, 12, 100, 12, 'WW2_AirGunP', 'WW2_AirMGWH') + GUN,
    'WW2_Air20mmLight': (30, 3, 12, 100, 12, 'WW2_AirGunP', 'WW2_AirCannonWH') + GUN,
    'WW2_Air20mm':      (34, 3, 12, 100, 12, 'WW2_AirGunP', 'WW2_AirCannonWH') + GUN,
    'WW2_Air20mmHeavy': (34, 4, 12, 100, 12, 'WW2_AirGunP', 'WW2_AirCannonWH') + GUN,
    'WW2_AirMK108':     (70, 2, 16, 90, 11, 'WW2_AirGunP', 'WW2_AirCannonWH') + GUN,
    # carrier aircraft defensive / interception guns
    'WW2_CarrierAirGun': (20, 4, 12, 100, 8, 'WW2_AirGunP', 'WW2_AirMGWH') + GUN,
}

PROJECTILES = '''
; ---- WWII aircraft guns --------------------------------------------------
; ROT=0 and Inviso=no: aircraft fly straight gun runs (strafing) against
; ground targets. Inaccurate + Ares BallisticScatter spreads the rounds so a
; pass walks its fire across the target instead of always hitting.
[WW2_StrafeGunP]
Image=DART
Inviso=no
Shadow=no
Arcing=no
ROT=0
Proximity=no
Ranged=yes
AA=no
AG=yes
Inaccurate=yes
BallisticScatter.Min=0
BallisticScatter.Max=0.7
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Arm=0
High=no
VeryHigh=no

[WW2_StrafeCannonP]
Image=DART
Inviso=no
Shadow=no
Arcing=no
ROT=0
Proximity=no
Ranged=yes
AA=no
AG=yes
Inaccurate=yes
BallisticScatter.Min=0
BallisticScatter.Max=0.5
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Arm=0
High=no
VeryHigh=no

[WW2_RocketP]
Image=DRAGON
Inviso=no
Shadow=yes
Arcing=no
ROT=0
Proximity=no
Ranged=yes
AA=no
AG=yes
Inaccurate=yes
BallisticScatter.Min=0.2
BallisticScatter.Max=1.2
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Arm=0
High=no
VeryHigh=no

; air-to-air: homing tracer so fighters can hit a manoeuvring aircraft
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
Inaccurate=no
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
Verses=100%,85%,70%,55%,25%,6%,40%,20%,8%,30%,100%
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
Verses=100%,90%,80%,70%,40%,12%,60%,35%,15%,40%,100%
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

; RP-3 60 lb rocket: strong but scattered
[WW2_RocketWH]
CellSpread=.8
PercentAtMax=.3
Verses=90%,80%,80%,100%,90%,70%,80%,60%,40%,60%,100%
InfDeath=2
AnimList=EXPLOSML,EXPLOMED
ProneDamage=50%
Conventional=yes
Rocker=yes
Wall=yes
Wood=yes

; air-to-air
[WW2_AirMGWH]
CellSpread=.15
PercentAtMax=.5
Verses=100%,90%,80%,75%,60%,35%,50%,30%,10%,40%,100%
InfDeath=1
AnimList=PIFFPIFF,PIFF
Bullets=yes
Wall=no
Wood=yes

[WW2_AirCannonWH]
CellSpread=.25
PercentAtMax=.4
Verses=100%,100%,90%,90%,75%,55%,70%,45%,20%,50%,100%
InfDeath=3
AnimList=TWLT050,S_CLSN58
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

# ------------------------------------------------ 4. tank guns can miss
# The tank shells had ROT=1: any ROT above 0 is a homing round in YR, so it
# followed its target and Inaccurate/BallisticScatter never took effect.
# They now fly a flat ballistic trajectory (Arcing=yes, like artillery, whose
# scatter works) at twice the old speed so the arc stays low and still reads
# as a direct tracer shot, landing on a scattered point.
TANK_SHELLS = ['HeavyShellP_D%d' % i for i in range(1, 8)] + ['TankShellP_D%d' % i for i in range(1, 9)]
SHELL_SCATTER = ('0.2', '1.5')
SHELL_SPEED = 220
# Warheads (splash radius, edge damage) are left exactly as in the original.


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

    for unit, (plane, speed, rot, hp, ammo, ground, air) in FIGHTERS.items():
        ini.set(unit, 'Primary', ground)
        ini.set(unit, 'ElitePrimary', ground + 'E')
        if air:
            ini.set(unit, 'Secondary', air)
            ini.set(unit, 'EliteSecondary', air + 'E')
        else:
            ini.delete(unit, 'Secondary')
            ini.delete(unit, 'EliteSecondary')
        ini.set(unit, 'Speed', speed)
        ini.set(unit, 'ROT', rot)
        ini.set(unit, 'Strength', hp)
        ini.set(unit, 'Ammo', ammo)
        ini.set(unit, 'OmniFire', 'yes')          # needed to engage manoeuvring aircraft
        ini.set(unit, 'Fighter', 'yes')
        ini.set(unit, 'PitchSpeed', '1.1')
        log.append('%-9s %-22s Speed=%s ROT=%s Strength=%s Ammo=%s %s / %s' % (unit, plane, speed, rot, hp, ammo,
                                                                               ground, air))

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

    shells = set(p.upper() for p in TANK_SHELLS)
    for p in TANK_SHELLS:
        ini.set(p, 'Arcing', 'yes')
        ini.set(p, 'ROT', '0')
        ini.set(p, 'Proximity', 'no')
        ini.set(p, 'Inaccurate', 'yes')
        ini.set(p, 'BallisticScatter.Min', SHELL_SCATTER[0])
        ini.set(p, 'BallisticScatter.Max', SHELL_SCATTER[1])
    # weapons firing tank shells: faster so the ballistic arc stays flat
    weapons_done = set()
    for unit in ini.list_section('VehicleTypes'):
        for w in weapons_of(ini, unit):
            if (ini.get(w, 'Projectile') or '').upper() not in shells:
                continue
            if w.upper() not in weapons_done:
                sp = float(ini.get(w, 'Speed') or 0)
                if sp < SHELL_SPEED:
                    ini.set_everywhere(w, 'Speed', SHELL_SPEED)
                weapons_done.add(w.upper())
    log.append('tank shells: ballistic, scatter %s-%s cells, %d weapons at Speed %d; warheads unchanged' % (
        SHELL_SCATTER + (len(weapons_done), SHELL_SPEED)))

    open(dst, 'wb').write(ini.data())
    print('\n'.join(log))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
