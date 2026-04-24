RADIUS = 2
TERRAIN_POOL = ['W']*4 + ['H']*3 + ['F']*4 + ['S']*4 + ['G']*3 + ['D']*1
NUMBER_TOKENS = [2,3,3,4,4,5,5,6,6,8,8,9,9,10,10,11,11,12]
RESOURCE_MAP = {'W':'wood','H':'brick','F':'grain','S':'sheep','G':'ore','D':None}
RESOURCE_NAMES = {'wood':'Wood','brick':'Brick','grain':'Grain','sheep':'Sheep','ore':'Ore'}
PLAYER_COLORS = ["#e74c3c","#3498db","#f39c12","#2ecc71"]
CANVAS_BG = "#87ceeb"

# Building costs
COSTS = {
    'settlement': {'wood':1, 'brick':1, 'grain':1, 'sheep':1},
    'city': {'grain':2, 'ore':3},
    'road': {'wood':1, 'brick':1},
    'dev_card': {'grain':1, 'sheep':1, 'ore':1}
}

# Development card deck
DEV_CARD_DECK = (['knight']*14 + ['victory_point']*5 +
                 ['road_building']*2 + ['year_of_plenty']*2 + ['monopoly']*2)

DEV_CARD_NAMES = {
    'knight': '⚔️ Knight',
    'victory_point': '🏆 Victory Point',
    'road_building': '🛤️ Road Building',
    'year_of_plenty': '🎁 Year of Plenty',
    'monopoly': '💰 Monopoly'
}

# AI Configuration
AI_CONFIG = {
    'depth': 10,
    'enable_pruning': True,
    'time_limit': 15.0,
    'enable_logging': True,
    'auto_play': True
}

# e.g. 
FelixAI_CONFIG = {
    'time_limit': 15.0,
    'enable_logging': True,
    'auto_play': True
}


# -------------------------
# FIXED HARBOR POSITIONS
# -------------------------
FIXED_HARBORS = [
    (( 0,-2, 2), ( 1,-2, 1), '3:1'),
    (( 1,-2, 1), ( 2,-2, 0), 'wood'),
    (( 2,-1,-1), ( 2, 0,-2), 'brick'),
    (( 2, 0,-2), ( 1, 1,-2), '3:1'),
    (( 0, 2,-2), (-1, 2,-1), 'ore'),
    ((-1, 2,-1), (-2, 2, 0), '3:1'),
    ((-2, 1, 1), (-2, 0, 2), 'sheep'),
    ((-2, 0, 2), (-1,-1, 2), 'grain'),
    ((-1,-1, 2), ( 0,-2, 2), '3:1'),
]

# -------------------------
# Helper functions
# -------------------------
def axial_to_cube(q, r):
    return (q, r, -q-r)

def generate_axial_positions_radius(radius=2):
    positions = []
    for q in range(-radius, radius+1):
        r1 = max(-radius, -q - radius)
        r2 = min(radius, -q + radius)
        for r in range(r1, r2+1):
            positions.append((q, r))
    positions.sort(key=lambda x: (abs(x[0]) + abs(x[1]) + abs(x[0]+x[1]))//2)
    return positions
