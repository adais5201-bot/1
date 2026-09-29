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

    def replace_section(self, sec, pairs):
        """Replace every key of an existing section (all duplicates) with pairs,
        or append the section if it does not exist yet."""
        starts = [i for i, l in enumerate(self.lines)
                  if re.match(rb'\s*\[' + re.escape(sec.encode('latin1')) + rb'\]', l, re.I)]
        if not starts:
            self.append('[%s]\n' % sec + '\n'.join('%s=%s' % kv for kv in pairs))
            return 'new'
        for st in reversed(starts):
            e = next((j for j in range(st + 1, len(self.lines)) if self.lines[j].lstrip().startswith(b'[')),
                     len(self.lines))
            for j in range(e - 1, st, -1):
                if re.match(rb'\s*[^=;\s][^=;]*=', self.lines[j]):
                    del self.lines[j]
        self._idx = None
        for k, v in pairs:
            self.set(sec, k, v)
        return 'replaced'

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
# * Every original fighter that could fight in the air has ONE weapon, the
#   Primary, with a homing AA=yes AG=yes projectile and no Secondary. Tests
#   showed fighters never attack aircraft with a ground-only Primary plus an
#   AA Secondary, nor with a straight (ROT=1, strafing) AA Primary: aircraft
#   fire their Primary only, and a ROT=1 round cannot hit a flying target.
#   So the WWII guns are single homing guns like the original bullets
#   (AircraftCannonP_D1: ROT=104, Proximity). Homing rounds (ROT >= 2) do not
#   strafe: the fighter makes the classic firing pass of the original guns.
# * A projectile without Inaccurate "snaps" to its target on impact and counts
#   as a direct hit; the warheads also have a small splash.
# The old weapons were homing (ROT=104) with ROF=5, Burst=10, Speed=165.
#
# unit: (aircraft, Speed, ROT, Strength, Ammo, weapon)
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
    'NAFAF':     ('Yak-9',                10, 5, 300, 3, 'WW2_ShVAK_Yak9'),
}

# Weapon section each fighter uses. The unit's original weapon name is kept
# (its values are replaced) unless another unit shares it: Maverick stays
# with the P-40s, Maverick2 with the P-51s; FIREFOX and NAFAF get new names.
# Elite = name + 'E'; skins use their own original names (name + a/b/c/d).
WEAPON_NAME = {
    'ORCA': 'Maverick', 'AORCA': 'Maverick', 'BEAG': 'Maverick2', 'F2002': 'MSSL2', 'FERD': 'Maverick9',
    'GERS': 'StBomberSalvo', 'BEAG2': 'JafsdNeedles', 'GERZ': 'Beag2Hive', 'GERL': 'GroundBarrage',
    'MIG2000': 'PlasmaRifle', 'FIREFOX': 'MC205Guns', 'STFIGHTER': 'ChainGun', 'GERN': 'ClusterMissile',
    'JAPVP': 'MSSL3', 'JAGDS': 'BomMissile', 'F23': 'Maverick8', 'STBOMBER': 'Hellfire', 'NAFAF': 'Yak9Guns',
}
# RGI mortar infantry: deployed weapon (Secondary, DeployFireWeapon=1) +2 damage
MORTAR_DEPLOYED_BONUS = {'Thapao': 2, 'ThapaoE': 2}
MAX_ID = 24          # Ares refuses type IDs longer than 24 characters

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
    'NAFAFA':   ('NAFAF',   0.90, 1.00, 1, 0, 1.00),   # anti-ship role: ammo +1, less vs land
    'NAFAFB':   ('NAFAF',   0.75, 1.00, 1, 0, 1.08),   # ammo 2->3, dmg -25%, hp +8%
}
# skins whose art section pointed at the base model; they get their own model
ART_OWN_IMAGE = ['FERDA', 'FERDB', 'GERNA', 'GERNB', 'GERNC', 'GERND', 'GERSA', 'GERZA', 'GERZB']
# vehicle and ship skins with the same problem: [GERHB] Image=GERH showed the
# base model although gerhb.vxl (and ...tur/...barl) ship with the mod
ART_OWN_IMAGE += ['GERHB', 'GERHA', 'GEROA', 'GEROB', 'FERBA', 'GERJA', 'GERJB', 'GERIA', 'GERIB', 'GERIC',
                  'FERAA', 'FERAB', 'FERCA', 'FERCB', 'FERCC', 'GERQA', 'GERKA', 'GERUA', 'GERXA', 'GERXB',
                  'GERPA', 'GERPB', 'GERYA', 'GERYB', 'GERYC', 'GERYD', 'GERFA', 'GERFB', 'GERFC']
AIR_RANGE_BONUS = 6

# weapon: (Damage, Burst, ROF, projectile Speed, Range, Projectile, Warhead, Report, Anim)
# Fighter guns: one homing gun for air and ground (see WW2_FighterGunP).
# Range 7 (the original F4U/Fw 190 weapons used 7, the rest 14): the fighter
# closes in before firing instead of shooting from far away.
GUN = ('ArnoldAttack', 'MGMUZZLE')
WEAPONS = {
    'WW2_US50_P40':    (15, 10, 3, 160, 7, 'WW2_FighterGunP', 'WW2_MG50WH') + GUN,       # 6 x .50
    'WW2_US50':        (16, 10, 3, 160, 7, 'WW2_FighterGunP', 'WW2_MG50WH') + GUN,       # 6 x .50
    'WW2_Hispano':     (22, 8, 4, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # 2 x 20 mm + 2 x .50
    'WW2_Hispano4':    (23, 9, 4, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # Typhoon 4 x 20 mm
    'WW2_MG151':       (21, 8, 4, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # MG 151/20 + 2 x MG 131
    'WW2_Fw190Guns':   (23, 9, 4, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # 2 x MG 151/20 + 2 x MG 131
    'WW2_MC205Guns':   (21, 8, 4, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # 2 x MG 151/20 + 2 x Breda
    'WW2_ShVAK_Yak':   (20, 8, 3, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # ShVAK + 2 x UBS
    'WW2_ShVAK_La':    (22, 8, 4, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # 2 x ShVAK
    'WW2_Type99':      (21, 6, 5, 140, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # 2 x Type 99 20 mm, slow
    'WW2_Ho5':         (22, 8, 3, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # 2 x Ho-5 + 2 x Ho-103
    'WW2_Ho103':       (20, 8, 3, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # 2 x Ho-5 + 2 x Ho-103
    'WW2_P38Nose':     (20, 10, 3, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,   # concentrated nose battery
    # Me 262: 4 x MK 108 30 mm. Heavy, slow (540 m/s) mine shells: a few hits
    # bring down a bomber, but short range, few rounds, and the slow shells
    # turn less (ROT 48) so agile fighters are harder to hit.
    'WW2_MK108':       (75, 4, 9, 90, 6, 'WW2_MK108P', 'WW2_Cannon30WH') + GUN,
    'WW2_ShVAK_Yak9':  (20, 7, 3, 150, 7, 'WW2_FighterGunP', 'WW2_Cannon20WH') + GUN,    # Yak-9: ShVAK + UBS
    # Ju 87G: Stuka-style dive attack as the old GERL (AirDesem), ground only
    'WW2_BK37':        (45, 8, 4, 95, 10, 'WW2_StukaP', 'WW2_Cannon37APWH') + GUN,     # 2 x BK 3,7
}

PROJECTILES = '''
; ---- WWII aircraft guns --------------------------------------------------
; Fighters: one gun for air and ground, as every original fighter that could
; fight in the air (a single AA=yes AG=yes Primary, no Secondary; aircraft do
; not fire a Secondary). Same as the original AircraftCannonP_D1 bullets:
; homing tracer (ROT=104) that bursts next to the target (Proximity).
[WW2_FighterGunP]
Image=DART
Inviso=no
Shadow=no
Arcing=no
ROT=104
Proximity=yes
Ranged=yes
AA=yes
AG=yes
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Acceleration=8
Arm=0
High=no
VeryHigh=no

; Me 262 MK 108: big, slow 30 mm shell (the game's cannon shell image)
[WW2_MK108P]
Image=120MM
Inviso=no
Shadow=no
Arcing=no
ROT=48
Proximity=yes
Ranged=yes
AA=yes
AG=yes
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no
Acceleration=4
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
'''


def weapon_pairs(spec, elite=False):
    dmg, burst, rof, speed, rng, proj, wh, report, anim = spec
    if elite:
        dmg = int(round(dmg * 1.15))
        rof = max(rof - 1, 1)
        rng = rng + 0.5
    pairs = [('Damage', dmg), ('ROF', rof), ('Range', rng), ('Projectile', proj), ('Speed', speed),
             ('Warhead', wh), ('Report', report), ('Burst', burst)]
    if anim:
        pairs += [('Anim', anim), ('Bright', 'yes')]
    return pairs


def scaled(spec, dm, rm):
    return (int(round(spec[0] * dm)), spec[1], max(1, int(round(spec[2] * rm)))) + tuple(spec[3:])


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
# Auto-launch within (launcher range - 10). Ground attack only: launchers and
# carrier aircraft keep their original weapons (no anti-air).
CARRIERS = {'CARRIER': ('HornetLauncher', 'HORNET'),
            'NIMITZ': ('J35Launcher', 'J35'),
            'NODCARRI': ('SU34Launcher', 'SU34')}
CARRIER_SIGHT = 12

# ------------------------------------------------ 3b. bombers: a different bombing style each
# He 111 (ALPHA), Ju 88 (JAFSD), B-17 (B2BOMBER) and A-26 (A10W) keep their
# attacks. Pe-2 (GERR) keeps its guided dive bombs with a bomb model instead
# of a missile. B-25J, B-24 and Lancaster get new weapons (original weapon
# names kept, values replaced). A projectile with ROT < 2 makes a run along
# the target dropping 5 times (Burst on the first drop); ROT >= 2 releases
# everything in one pass.
BOMB_ART = ['WWFAB250', 'WWNAPALM', 'WWTALBOY']       # voxel bombs (tools/voxplane/bombs.py)
BOMBER_IMAGE = {'BSCannon2': 'WWFAB250'}               # Pe-2: FAB-250 instead of the FESSILE missile
# weapon: (Damage, elite Damage, Burst, ROF, Speed, Range, Projectile, Warhead, Report)
BOMBER_WEAPONS = {
    # B-25J (KPLN): napalm run -- low pass, 6 tanks, each splashing fire
    # around it (Cluster); burns infantry and light vehicles, weak on armour
    'TDNapalm':      (40, 52, 2, 12, 0, 4, 'WW2_NapalmP', 'WW2_NapalmWH', 'BlackEagleAttack'),
    # B-24 (F1172): carpet of fragmentation cluster bombs
    'Maverick5':     (34, 44, 3, 10, 20, 5, 'WW2_ClusterBombP', 'WW2_FragWH', 'KirovAttack'),
    # Lancaster (GERM): one Tallboy earthquake bomb per sortie
    'NafaRocketFan': (520, 680, 1, 60, 25, 4, 'WW2_TallboyP', 'WW2_TallboyWH', 'KirovAttack'),
}
BOMBER_AMMO = {'GERM': 1}

BOMBER_TEXT = '''
; ---- WWII bombs ------------------------------------------------------------
; B-25J napalm tank: dropped (weapon Speed 0), falls, bursts into 3 fires
[WW2_NapalmP]
Image=WWNAPALM
Shadow=yes
Arm=0
ROT=0
Proximity=no
Acceleration=1.3
AA=no
AG=yes
Cluster=3
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no

; B-24 fragmentation cluster bomb: scattered, each opens into 5 blasts
[WW2_ClusterBombP]
Image=DROPB
Shadow=yes
Arm=0
ROT=0
Arcing=yes
Inaccurate=yes
Proximity=no
Acceleration=1.5
AA=no
AG=yes
Cluster=5
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no

; Lancaster Tallboy: single aimed release (ROT >= 2, no run)
[WW2_TallboyP]
Image=WWTALBOY
Shadow=yes
Arm=0
ROT=4
Proximity=no
Acceleration=3
AA=no
AG=yes
SubjectToCliffs=no
SubjectToElevation=no
SubjectToWalls=no

; napalm: same explosion as the A-26's shells; wide, even burn
[WW2_NapalmWH]
CellSpread=1.6
PercentAtMax=.7
Verses=150%,140%,110%,90%,55%,30%,150%,40%,25%,100%,100%
AnimList=EXPLOLRG,BRRLEXP1
InfDeath=4
Fire=yes
Bright=yes
ProneDamage=100%
Wall=no
Wood=yes

[WW2_FragWH]
CellSpread=1
PercentAtMax=.5
Verses=140%,130%,90%,80%,50%,25%,110%,40%,25%,100%,100%
AnimList=EXPLOSML,EXPLOMED
InfDeath=2
ProneDamage=70%
Conventional=yes
Wall=yes
Wood=yes

; Tallboy: huge blast, cratering, best against buildings
[WW2_TallboyWH]
CellSpread=3
PercentAtMax=.35
Verses=100%,100%,100%,110%,120%,130%,150%,160%,200%,100%,100%
AnimList=TWLT100
InfDeath=2
Rocker=yes
Deform=25%
DeformThreshhold=200
PenetratesBunker=yes
ProneDamage=100%
Conventional=yes
Wall=yes
Wood=yes
'''


# ------------------------------------------------ 4. tanks: cannon -> machine gun timing
# Tanks with a cannon + machine gun use Gattling stages (Ares Gattling.Cycle):
# stage 1 = Weapon1 (cannon), stage 2 = Weapon3 (machine gun). In 26 of them
# Stage1 was the cannon ROF + 12 frames, so the cannon could fire twice in its
# stage and the second reload ran past the end of the machine gun stage: the
# machine gun never fired. The units that already worked (JATANK, IDRAG, KAMM,
# FERB...) use Stage1 = ROF - 24 and Stage2 = ROF + 48: one cannon shot per
# cycle, then 48 frames of machine gun fire once the cannon has reloaded.
# That layout is applied to every such tank; ROF values stay as they are.
GATTLING_BEFORE = 24
GATTLING_MG_WINDOW = 48
GATTLING_MIN_CANNON_ROF = 40     # skip rapid-fire autocannon layouts (GFIST)


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

    # new projectiles / warheads, carrier AA gun
    text = PROJECTILES + WARHEADS
    for sec in sections_of(text):
        assert not ini.has(sec), 'section [%s] already exists' % sec
    ini.append(text)

    written = {}

    def put(name, spec, elite):
        assert len(name) <= MAX_ID, 'ID too long for Ares (%d > %d): %s' % (len(name), MAX_ID, name)
        how = ini.replace_section(name, weapon_pairs(spec, elite))
        written[name] = how

    # fighters: WWII guns written under the unit's own weapon names
    for unit, (plane, speed, rot, hp, ammo, gun) in FIGHTERS.items():
        name = WEAPON_NAME[unit]
        spec = WEAPONS[gun]
        put(name, spec, False)
        put(name + 'E', spec, True)
        ini.set(unit, 'Primary', name)
        ini.set(unit, 'ElitePrimary', name + 'E')
        ini.delete(unit, 'Secondary')             # aircraft only fire the Primary
        ini.delete(unit, 'EliteSecondary')
        ini.set(unit, 'Speed', speed)
        ini.set(unit, 'ROT', rot)
        ini.set(unit, 'Strength', hp)
        ini.set(unit, 'Ammo', ammo)
        ini.set(unit, 'OmniFire', 'yes')          # as the original fighters that could fight in the air
        ini.set(unit, 'Fighter', 'yes')
        ini.set(unit, 'PitchSpeed', '1.1')
        ini.set(unit, 'AirRangeBonus', AIR_RANGE_BONUS)
        log.append('%-9s %-22s Speed=%s ROT=%s Strength=%s Ammo=%s %s / %s' % (
            unit, plane, speed, rot, hp, ammo, name, name + 'E'))

    # skins: the skin's own weapon names (original weapon + a/b/c/d)
    for skin, (base, dm, rm, ammo_add, spd_add, hp_m) in SKIN_UNITS.items():
        _, speed, rot, hp, ammo, gun = FIGHTERS[base]
        base_name = WEAPON_NAME[base]
        letter = skin[-1].lower()
        prim = ini.get(skin, 'Primary')
        eprim = ini.get(skin, 'ElitePrimary')
        if prim and prim.lower() != base_name.lower() and prim.lower() not in (v.lower() for v in WEAPON_NAME.values()):
            put(prim, scaled(WEAPONS[gun], dm, rm), False)
            put(eprim, scaled(WEAPONS[gun], dm, rm), True)
        else:                                    # skin shares the base weapon (FALCA, BEAGA)
            assert (dm, rm) == (1.0, 1.0), skin
            prim, eprim = base_name, base_name + 'E'
            ini.set(skin, 'Primary', prim)
            ini.set(skin, 'ElitePrimary', eprim)
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
        log.append('  skin %-8s of %-7s Speed=%s Strength=%s Ammo=%s %s/%s' % (
            skin, base, speed + spd_add, int(round(hp * hp_m)), ammo + ammo_add, prim,
            eprim))
    log.append('weapon sections: %d replaced in place, %d new: %s' % (
        sum(1 for v in written.values() if v == 'replaced'), sum(1 for v in written.values() if v == 'new'),
        ', '.join(sorted(k for k, v in written.items() if v == 'new'))))

    for carrier, (launcher, spawn) in CARRIERS.items():
        rng = float(ini.get(launcher, 'Range'))
        ini.set(carrier, 'CanPassiveAquire', 'yes')
        ini.set(carrier, 'GuardRange', '%g' % (rng - 10))
        sight = int(ini.get(carrier, 'Sight') or 0)
        if sight < CARRIER_SIGHT:
            ini.set(carrier, 'Sight', CARRIER_SIGHT)
        log.append('%s: auto-launch within %g cells (range %g)' % (carrier, rng - 10, rng))

    for sec in sections_of(BOMBER_TEXT):
        assert not ini.has(sec), 'section [%s] already exists' % sec
    ini.append(BOMBER_TEXT)
    for proj, img in BOMBER_IMAGE.items():
        ini.set(proj, 'Image', img)
    for w, (dmg, edmg, burst, rof, speed, rng, proj, wh, report) in BOMBER_WEAPONS.items():
        for name, d in ((w, dmg), (w + 'E', edmg)):
            ini.replace_section(name, [('Damage', d), ('ROF', rof), ('Range', rng), ('Projectile', proj),
                                       ('Speed', speed), ('Warhead', wh), ('Report', report),
                                       ('Burst', burst)])
        log.append('bomber weapon %s/%sE: %s, %s' % (w, w, proj, wh))
    for u, ammo in BOMBER_AMMO.items():
        ini.set(u, 'Ammo', ammo)

    fixed = []
    for unit in ini.list_section('VehicleTypes'):
        if (ini.get(unit, 'IsGattling') or '').lower() != 'yes':
            continue
        if ini.get(unit, 'WeaponStages') != '2' or ini.get(unit, 'WeaponCount') != '4':
            continue
        for w_key, s1_key, s2_key in (('Weapon1', 'Stage1', 'Stage2'), ('EliteWeapon1', 'EliteStage1', 'EliteStage2')):
            w = ini.get(unit, w_key)
            rof = int(float(ini.get(w, 'ROF') or 0))
            s1 = int(float(ini.get(unit, s1_key) or 0))
            if rof < GATTLING_MIN_CANNON_ROF or s1 <= rof - GATTLING_BEFORE:
                continue
            ini.set(unit, s1_key, rof - GATTLING_BEFORE)
            ini.set(unit, s2_key, rof + GATTLING_MG_WINDOW)
            fixed.append('%s %s: ROF %d -> %s=%d %s=%d' % (unit, w_key, rof, s1_key, rof - GATTLING_BEFORE,
                                                              s2_key, rof + GATTLING_MG_WINDOW))
    log.append('cannon/MG timing fixed on %d stage sets:' % len(fixed))
    log.extend('  ' + f for f in fixed)

    for w, add in MORTAR_DEPLOYED_BONUS.items():
        dmg = int(ini.get(w, 'Damage')) + add
        ini.set(w, 'Damage', dmg)
        log.append('%s (RGI mortar, deployed): Damage %d' % (w, dmg))

    open(dst, 'wb').write(ini.data())
    print('\n'.join(log))


# coastal gun (tools/shp/coastgun.py): the new barrel ends 58 voxels in front
# of the pivot and 29 voxels up (56 voxels per cell = 256 leptons; 15 px per
# 104 leptons of height), so the shot leaves the muzzle
ART_SET = {('GAGUN', 'PrimaryFireFLH'): '265,0,133'}


def patch_art(src, dst):
    art = Ini(open(src, 'rb').read())
    for (sec, key), val in ART_SET.items():
        art.set(sec, key, val)
    for sec in ART_OWN_IMAGE:
        art.set(sec, 'Image', sec)
    for sec in BOMB_ART:
        assert not art.has(sec)
    art.append('\n\n'.join('[%s]\nVoxel=yes' % sec for sec in BOMB_ART))
    open(dst, 'wb').write(art.data())
    print('artmd: own skin models for %s' % ', '.join(ART_OWN_IMAGE))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
    if len(sys.argv) > 4:
        patch_art(sys.argv[3], sys.argv[4])
