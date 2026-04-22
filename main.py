# catan_complete.py
# Catan with Fixed Harbors + Dev Cards + Enhanced Minimax AI
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional, Set
import math
import json
import time
import threading
from copy import deepcopy

# -------------------------
# Configuration
# -------------------------
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

# -------------------------
# Game Tracker
# -------------------------
class GameTracker:
    def __init__(self):
        self.game_id = f"game_{int(time.time())}"
        self.moves = []
        self.start_time = time.time()
        
    def log_move(self, player_id, action_type, details, game_state=None):
        self.moves.append({
            'timestamp': time.time() - self.start_time,
            'player_id': player_id,
            'action_type': action_type,
            'details': details,
        })
    
    def save_to_file(self):
        import os
        os.makedirs('game_logs', exist_ok=True)
        filename = f"game_logs/{self.game_id}.json"
        with open(filename, 'w') as f:
            json.dump({
                'game_id': self.game_id,
                'duration': time.time() - self.start_time,
                'moves': self.moves
            }, f, indent=2)
        return filename

# -------------------------
# Data classes
# -------------------------
@dataclass
class Tile:
    q: int
    r: int
    terrain: str
    token: Optional[int]
    robber: bool = False

@dataclass
class Vertex:
    id: int
    qx: float
    rx: float
    cube: Tuple[int,int,int]
    tiles: List[Tuple[int,int]] = field(default_factory=list)
    owner: Optional[int] = None
    is_city: bool = False

@dataclass
class Edge:
    id: int
    v1: int
    v2: int
    owner: Optional[int] = None

@dataclass
class Harbor:
    type: str
    v1_cube: Tuple[int,int,int]
    v2_cube: Tuple[int,int,int]
    v1_id: Optional[int] = None
    v2_id: Optional[int] = None
    position: Optional[Tuple[float,float]] = None

@dataclass
class Player:
    id: int
    name: str
    is_computer: bool = False
    ai_type: str = "felix"
    resources: Counter = field(default_factory=Counter)
    victory_points: int = 0
    roads: Set[int] = field(default_factory=set)
    settlements: Set[int] = field(default_factory=set)
    cities: Set[int] = field(default_factory=set)
    harbors: List[str] = field(default_factory=list)
    dev_cards: List[str] = field(default_factory=list)
    dev_cards_new: List[str] = field(default_factory=list)
    knights_played: int = 0
    longest_road: bool = False
    largest_army: bool = False

# -------------------------
# Board
# -------------------------
class Board:
    def __init__(self):
        self.tiles: Dict[Tuple[int,int], Tile] = {}
        self.vertices: Dict[int, Vertex] = {}
        self.edges: Dict[int, Edge] = {}
        self.vertex_map: Dict[Tuple[float,float], int] = {}
        self.vertex_cube_map: Dict[Tuple[int,int,int], int] = {}
        self.edge_map: Dict[Tuple[int,int], int] = {}
        self.harbors: List[Harbor] = []
        self.build()

    def axial_to_pixel(self, q, r, size):
        x = size * math.sqrt(3) * (q + r / 2.0)
        y = size * 3/2.0 * r
        return x, y

    def hex_corners_pixel_direct(self, q, r, size=100.0):
        cx, cy = self.axial_to_pixel(q, r, size)
        corners = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            x = cx + size * math.cos(angle)
            y = cy + size * math.sin(angle)
            corners.append((x, y))
        return corners

    def build(self):
        positions = generate_axial_positions_radius(RADIUS)
        pool = TERRAIN_POOL.copy()
        random.shuffle(pool)
        tokens = NUMBER_TOKENS.copy()
        random.shuffle(tokens)

        desert_idx = pool.index('D')
        if desert_idx > 0:
            pool[0], pool[desert_idx] = pool[desert_idx], pool[0]

        for pos, terrain in zip(positions, pool):
            token = None if terrain == 'D' else tokens.pop()
            self.tiles[(pos[0], pos[1])] = Tile(q=pos[0], r=pos[1], terrain=terrain, token=token)

        # First pass: collect all unique pixel corners with consistent rounding
        all_corners = {}
        for (q, r), tile in self.tiles.items():
            corners_pixel = self.hex_corners_pixel_direct(q, r, 100.0)
            for x, y in corners_pixel:
                key = (round(x, 3), round(y, 3))
                if key not in all_corners:
                    all_corners[key] = (x, y)

        # Second pass: create vertices with stable lookup keys
        vertex_lookup = {}
        self.vertices = {}
        next_vid = 0

        for key, (x, y) in all_corners.items():
            vertex_lookup[key] = next_vid
            cube_coords = axial_to_cube(int(key[0] // 173), int(key[1] // 150))  # Approximate
            self.vertices[next_vid] = Vertex(
                id=next_vid,
                qx=x,
                rx=y,
                cube=key
            )
            next_vid += 1

        # Third pass: assign tiles to vertices
        for (q, r), tile in self.tiles.items():
            corners_pixel = self.hex_corners_pixel_direct(q, r, 100.0)
            for x, y in corners_pixel:
                key = (round(x, 3), round(y, 3))
                vid = vertex_lookup[key]
                if (q, r) not in self.vertices[vid].tiles:
                    self.vertices[vid].tiles.append((q, r))

        self.vertex_map = vertex_lookup

        # Build edges
        self.edges = {}
        self.edge_map = {}
        edge_set = set()
        eid = 0

        for (q, r), tile in self.tiles.items():
            corners = self.hex_corners_pixel_direct(q, r, 100.0)
            vids = [vertex_lookup[(round(x,3), round(y,3))] for (x, y) in corners]
            for i in range(6):
                a, b = sorted((vids[i], vids[(i + 1) % 6]))
                if (a, b) not in edge_set:
                    edge_set.add((a, b))
                    self.edge_map[(a, b)] = eid
                    self.edges[eid] = Edge(id=eid, v1=a, v2=b)
                    eid += 1

        self.create_fixed_harbors()
        
        for t in self.tiles.values():
            if t.terrain == 'D':
                t.robber = True
                break

    def create_fixed_harbors(self):
        """Create harbors at fixed coastal positions according to standard Catan rules"""
        self.harbors = []
        
        # Standard Catan board distribution: 4x 3:1, 1 each of 5 resources
        # Ordered clockwise from top
        harbor_types_ordered = ['grain', '3:1', 'ore', '3:1', 'brick', 'sheep', '3:1', 'wood', '3:1']
        
        # Find border edges (edges where both vertices have < 3 adjacent tiles)
        border_edges = []
        
        for eid, edge in self.edges.items():
            v1_id, v2_id = edge.v1, edge.v2
            v1, v2 = self.vertices[v1_id], self.vertices[v2_id]
            
            # Check if this edge is on the border (both vertices have few adjacent tiles)
            v1_tile_count = len(v1.tiles)
            v2_tile_count = len(v2.tiles)
            
            if v1_tile_count < 3 and v2_tile_count < 3:
                border_edges.append((eid, edge, v1, v2))
        
        # Sort border edges by angle from center (clockwise starting from top)
        def get_angle_from_center(v1, v2):
            # Midpoint of the edge
            mid_x = (v1.qx + v2.qx) / 2.0
            mid_y = (v1.rx + v2.rx) / 2.0
            # Angle from center (0,0) - atan2 gives angle in radians
            # Starting from top (negative y) and going clockwise
            angle = math.atan2(mid_x, -mid_y)
            # Normalize to 0-2π range for proper clockwise ordering
            if angle < 0:
                angle += 2 * math.pi
            return angle
        
        border_edges.sort(key=lambda x: get_angle_from_center(x[2], x[3]))
        
        # Pick 9 evenly distributed harbor positions by spacing them around perimeter
        # With 18 border edges, pick every 2nd edge for balanced distribution
        step = max(1, len(border_edges) // 9)
        selected_edges = [border_edges[i] for i in range(0, len(border_edges), step)][:9]
        
        # Create harbors with the standard Catan distribution
        for i, (eid, edge, v1, v2) in enumerate(selected_edges):
            v1_id, v2_id = edge.v1, edge.v2
            harbor_type = harbor_types_ordered[i]
            harbor = Harbor(
                type=harbor_type,
                v1_cube=(v1_id, 0, 0),  # Use vertex ID as placeholder
                v2_cube=(v2_id, 0, 0),
                v1_id=v1_id,
                v2_id=v2_id
            )
            self.harbors.append(harbor)
                

    def get_harbor_pixel_position(self, harbor: Harbor, offset_x=0, offset_y=0):
        if harbor.v1_id is None or harbor.v2_id is None:
            return None
        
        v1 = self.vertices[harbor.v1_id]
        v2 = self.vertices[harbor.v2_id]
        
        mid_x = (v1.qx + v2.qx) / 2 + offset_x
        mid_y = (v1.rx + v2.rx) / 2 + offset_y
        
        center_x = offset_x
        center_y = offset_y
        
        dx = mid_x - center_x
        dy = mid_y - center_y
        length = math.sqrt(dx*dx + dy*dy)
        
        if length > 0:
            dx /= length
            dy /= length
            harbor_x = mid_x + dx * 40
            harbor_y = mid_y + dy * 40
            return (harbor_x, harbor_y)
        
        return (mid_x, mid_y)

    def vertices_of_tile(self, pos):
        corners = self.hex_corners_pixel_direct(pos[0], pos[1], 100.0)
        return [self.vertex_map[(round(x,3), round(y,3))] for (x, y) in corners]

    def edges_of_vertex(self, vid):
        return [eid for eid,e in self.edges.items() if e.v1==vid or e.v2==vid]

    def get_adjacent_vertices(self, vid):
        adjacent = set()
        for eid in self.edges_of_vertex(vid):
            e = self.edges[eid]
            other = e.v1 if e.v2 == vid else e.v2
            adjacent.add(other)
        return list(adjacent)




# -------------------------
# Felix AI (helper-only)
# -------------------------
class FelixAI:
    """
    Helper-only AI class: provides the same helper functions as MinimaxAI
    (move generation, trade ratio, apply-move helpers, dev-card simulation,
    evaluation helper, next-player helper) but does NOT implement any search
    or decision logic. get_best_move returns None (no decision).
    """

    def __init__(self, game, player_id, config=None):
        self.game = game
        self.player_id = player_id
        self.config = config or FelixAI_CONFIG
        self.start_time = 0
        

    # Reuse the same evaluation function so Felix can still score states if needed
    def evaluate_board_state(self, game, for_player_id):
        score = 0

        return score

    def get_possible_moves(self, game, player_id):
        # Copy of MinimaxAI.get_possible_moves (no changes)
        moves = []
        player = next(p for p in game.players if p.id == player_id)

        # Settlements
        for vid in game.board.vertices.keys():
            if game.can_place_settlement(player, vid)[0]:
                moves.append(('settlement', vid))

        # Cities
        for vid in player.settlements:
            if game.can_upgrade_to_city(player, vid)[0]:
                moves.append(('city', vid))

        # Roads
        for eid in game.board.edges.keys():
            if game.can_place_road(player, eid)[0]:
                moves.append(('road', eid))

        # Dev cards - buy
        if game.dev_card_deck and game.can_buy_dev_card(player)[0]:
            moves.append(('buy_dev_card', None))

        # Dev cards - play
        for card in set(player.dev_cards):
            if card != 'victory_point':
                moves.append(('play_dev_card', card))

        # Trading
        for give_res in ['wood', 'brick', 'grain', 'sheep', 'ore']:
            ratio = self.get_trade_ratio(player, give_res)
            if player.resources[give_res] >= ratio:
                for get_res in ['wood', 'brick', 'grain', 'sheep', 'ore']:
                    if give_res != get_res:
                        moves.append(('trade', (give_res, get_res)))

        moves.append(('end_turn', None))
        return moves

    def get_trade_ratio(self, player, resource):
        if resource in player.harbors:
            return 2
        if '3:1' in player.harbors:
            return 3
        return 4

    def apply_move(self, game, player_id, move):
        # Same helper to apply a move to a game copy
        move_type, move_data = move
        player = next(p for p in game.players if p.id == player_id)

        if move_type == 'settlement':
            game.place_settlement(player, move_data)
        elif move_type == 'city':
            game.upgrade_to_city(player, move_data)
        elif move_type == 'road':
            game.place_road(player, move_data)
        elif move_type == 'buy_dev_card':
            game.buy_dev_card(player)
        elif move_type == 'play_dev_card':
            self._simulate_dev_card(game, player, move_data)
        elif move_type == 'trade':
            give_res, get_res = move_data
            ratio = self.get_trade_ratio(player, give_res)
            player.resources[give_res] -= ratio
            player.resources[get_res] += 1
        elif move_type == 'end_turn':
            game.end_turn_cleanup(player)
            return True

        return False

    def _simulate_dev_card(self, game, player, card):
        if card not in player.dev_cards:
            return
        
        player.dev_cards.remove(card)
        
        if card == 'knight':
            player.knights_played += 1
            game.check_largest_army()
            # Simple robber simulation - move to best tile
            best_pos = None
            best_score = -999
            for pos, tile in game.board.tiles.items():
                if tile.robber:
                    continue
                score = sum(2 for vid in game.board.vertices_of_tile(pos)
                           if game.board.vertices[vid].owner not in (None, player.id))
                if score > best_score:
                    best_score = score
                    best_pos = pos
            if best_pos:
                for t in game.board.tiles.values():
                    t.robber = False
                game.board.tiles[best_pos].robber = True
        
        elif card == 'road_building':
            placed = 0
            for eid in game.board.edges:
                if placed >= 2:
                    break
                if game.can_place_road(player, eid, free=True)[0]:
                    player.roads.add(eid)
                    game.board.edges[eid].owner = player.id
                    placed += 1
            game.update_longest_road()
        
        elif card == 'year_of_plenty':
            needs = sorted(['wood','brick','grain','sheep','ore'], 
                          key=lambda r: player.resources[r])
            player.resources[needs[0]] += 1
            player.resources[needs[1]] += 1
        
        elif card == 'monopoly':
            tc = Counter()
            for opp in game.players:
                if opp.id != player.id:
                    tc.update(opp.resources)
            if tc:
                best_r = tc.most_common(1)[0][0]
                for opp in game.players:
                    if opp.id != player.id:
                        player.resources[best_r] += opp.resources[best_r]
                        opp.resources[best_r] = 0

    def get_next_player_id(self, game, current_player_id):
        current_idx = next(i for i, p in enumerate(game.players) if p.id == current_player_id)
        next_idx = (current_idx + 1) % len(game.players)
        return game.players[next_idx].id

    def get_best_move(self):
        """
        FelixAI intentionally does not implement search/decision logic.
        Return None to indicate no chosen move (caller can treat as 'end_turn' or
        use other logic).
        """
        return None, 0, 0, 0.0 # in meiner implementation hier  return move, zwei model_parameter und dann elapsed zeit


    def felix_ai(self):
        # hier bei mir rekursiver aufruf
        if time.time() - self.start_time > self.config['time_limit']:
            return self.evaluate_board_state(game, self.player_id), None
        
        best_val, best_move = 0,0
        
        return best_val, best_move
        
        

# -------------------------
# Game Logic
# -------------------------
class Game:
    def __init__(self, players: List[Player]):
        self.board = Board()
        self.players = players
        self.current = 0
        self.phase = "initial_settlement"
        self.initial_placements = 0
        self.initial_round = 0
        self.dice_rolled = False
        self.current_dice = (0, 0, 0)
        self.longest_road_player = None
        self.largest_army_player = None
        self.last_settlement_placed: Dict[int, int] = {}
        self.robber_pending = False
        self.free_roads_remaining = 0
        self.tracker = GameTracker()
        
        self.dev_card_deck = DEV_CARD_DECK.copy()
        random.shuffle(self.dev_card_deck)

    def roll_dice(self):
        d1, d2 = random.randint(1,6), random.randint(1,6)
        total = d1 + d2
        self.current_dice = (d1, d2, total)
        self.dice_rolled = True
        self.tracker.log_move(self.current, 'roll_dice', {'dice': (d1, d2, total)}, self)
        return d1, d2, total

    def distribute_resources(self, roll, log_func=print):
        if roll == 7:
            log_func("🎲 7! Robber!")
            self.handle_robber_discard(log_func)
            self.robber_pending = True
            return
        
        for pos, tile in self.board.tiles.items():
            if tile.token == roll and not tile.robber and tile.terrain != 'D':
                res = RESOURCE_MAP[tile.terrain]
                if res is None:
                    continue
                vids = self.board.vertices_of_tile(pos)
                for vid in vids:
                    v = self.board.vertices[vid]
                    if v.owner is not None:
                        owner = next(p for p in self.players if p.id == v.owner)
                        amount = 2 if v.is_city else 1
                        owner.resources[res] += amount
                        log_func(f"  {owner.name} +{amount} {RESOURCE_NAMES[res]}")

    def can_place_settlement(self, player: Player, vid: int, initial=False):
        v = self.board.vertices.get(vid)
        if not v:
            return False, "Invalid"
        if v.owner is not None:
            return False, "Occupied"
        
        for adj_vid in self.board.get_adjacent_vertices(vid):
            if self.board.vertices[adj_vid].owner is not None:
                return False, "Too close"
        
        if not initial:
            cost = COSTS['settlement']
            for res, amount in cost.items():
                if player.resources[res] < amount:
                    return False, f"Need {res}"
            
            connected = False
            for eid in self.board.edges_of_vertex(vid):
                e = self.board.edges[eid]
                if e.owner == player.id:
                    connected = True
                    break
            if not connected:
                return False, "Not connected"
        
        return True, "OK"

    def place_settlement(self, player: Player, vid: int, initial=False, free=False):
        ok, msg = self.can_place_settlement(player, vid, initial)
        if not ok:
            return False, msg
        
        if not free and not initial:
            cost = COSTS['settlement']
            for res, amount in cost.items():
                player.resources[res] -= amount
        
        self.board.vertices[vid].owner = player.id
        player.settlements.add(vid)
        player.victory_points += 1
        
        # Grant resources for second settlement (reverse phase)
        n = len(self.players)
        if initial and self.initial_placements >= n:
            v = self.board.vertices[vid]
            for tile_pos in v.tiles:
                tile = self.board.tiles.get(tile_pos)
                if tile and tile.terrain != 'D':
                    res = RESOURCE_MAP[tile.terrain]
                    if res:
                        player.resources[res] += 1
        
        for harbor in self.board.harbors:
            if vid in (harbor.v1_id, harbor.v2_id):
                if harbor.type not in player.harbors:
                    player.harbors.append(harbor.type)
        
        self.tracker.log_move(player.id, 'place_settlement', {'vid': vid}, self)
        return True, "OK"

    def can_upgrade_to_city(self, player: Player, vid: int):
        v = self.board.vertices.get(vid)
        if not v or v.owner != player.id or v.is_city or vid not in player.settlements:
            return False, "Cannot upgrade"
        
        cost = COSTS['city']
        for res, amount in cost.items():
            if player.resources[res] < amount:
                return False, f"Need {res}"
        return True, "OK"

    def upgrade_to_city(self, player: Player, vid: int):
        ok, msg = self.can_upgrade_to_city(player, vid)
        if not ok:
            return False, msg
        
        cost = COSTS['city']
        for res, amount in cost.items():
            player.resources[res] -= amount
        
        self.board.vertices[vid].is_city = True
        player.settlements.remove(vid)
        player.cities.add(vid)
        player.victory_points += 1
        self.tracker.log_move(player.id, 'upgrade_city', {'vid': vid}, self)
        return True, "OK"

    def can_place_road(self, player: Player, eid: int, initial=False, free=False):
        e = self.board.edges.get(eid)
        if not e or e.owner is not None:
            return False, "Invalid/occupied"
        
        if initial:
            last_settlement = self.last_settlement_placed.get(player.id)
            if last_settlement is None:
                return False, "No settlement"
            if eid not in self.board.edges_of_vertex(last_settlement):
                return False, "Must connect"
            return True, "OK"
        
        if not free:
            cost = COSTS['road']
            for res, amount in cost.items():
                if player.resources[res] < amount:
                    return False, f"Need {res}"
        
        v1, v2 = e.v1, e.v2
        if self.board.vertices[v1].owner == player.id or self.board.vertices[v2].owner == player.id:
            return True, "OK"
        
        for vid in (v1, v2):
            for other_eid in self.board.edges_of_vertex(vid):
                if other_eid != eid and self.board.edges[other_eid].owner == player.id:
                    return True, "OK"
        
        return False, "Not connected"

    def place_road(self, player: Player, eid: int, initial=False, free=False):
        ok, msg = self.can_place_road(player, eid, initial, free)
        if not ok:
            return False, msg
        
        if not free and not initial:
            cost = COSTS['road']
            for res, amount in cost.items():
                player.resources[res] -= amount
        
        self.board.edges[eid].owner = player.id
        player.roads.add(eid)
        self.update_longest_road()
        self.tracker.log_move(player.id, 'place_road', {'eid': eid}, self)
        return True, "OK"

    def can_buy_dev_card(self, player):
        if not self.dev_card_deck:
            return False, "Deck empty"
        cost = COSTS['dev_card']
        for res, amount in cost.items():
            if player.resources[res] < amount:
                return False, f"Need {res}"
        return True, "OK"

    def buy_dev_card(self, player):
        ok, msg = self.can_buy_dev_card(player)
        if not ok:
            return False, msg
        
        cost = COSTS['dev_card']
        for res, amount in cost.items():
            player.resources[res] -= amount
        
        card = self.dev_card_deck.pop()
        if card == 'victory_point':
            player.victory_points += 1
            player.dev_cards_new.append(card)
        else:
            player.dev_cards_new.append(card)
        
        self.tracker.log_move(player.id, 'buy_dev', {'card': card}, self)
        return True, card

    def play_dev_card(self, player, card, log_func=print, extra=None):
        if card not in player.dev_cards:
            return False, "Not playable"
        
        player.dev_cards.remove(card)
        self.tracker.log_move(player.id, 'play_dev', {'card': card}, self)
        
        if card == 'knight':
            player.knights_played += 1
            self.check_largest_army()
            self.robber_pending = True
            log_func(f"⚔️ {player.name} played Knight!")
        elif card == 'road_building':
            self.free_roads_remaining = 2
            log_func(f"🛤️ {player.name} Road Building!")
        elif card == 'year_of_plenty':
            r1, r2 = extra or ('wood', 'grain')
            player.resources[r1] += 1
            player.resources[r2] += 1
            log_func(f"🎁 {player.name} got {r1} + {r2}")
        elif card == 'monopoly':
            res = extra or 'wood'
            total = 0
            for opp in self.players:
                if opp.id != player.id:
                    total += opp.resources[res]
                    opp.resources[res] = 0
            player.resources[res] += total
            log_func(f"💰 {player.name} monopoly {res}: {total}")
        
        return True, "OK"

    def end_turn_cleanup(self, player):
        player.dev_cards.extend(player.dev_cards_new)
        player.dev_cards_new.clear()

    def update_longest_road(self):
        max_length = 4
        longest_player = None
        
        for player in self.players:
            if len(player.roads) < 5:
                continue
            length = self.calculate_longest_road_for_player(player)
            if length > max_length:
                max_length = length
                longest_player = player
        
        for player in self.players:
            old = player.longest_road
            player.longest_road = (player == longest_player)
            if player.longest_road and not old:
                player.victory_points += 2
            elif not player.longest_road and old:
                player.victory_points -= 2

    def calculate_longest_road_for_player(self, player: Player):
        if not player.roads:
            return 0
        
        graph = {}
        for eid in player.roads:
            e = self.board.edges[eid]
            v1, v2 = e.v1, e.v2
            v1_blocked = self.board.vertices[v1].owner not in (None, player.id)
            v2_blocked = self.board.vertices[v2].owner not in (None, player.id)
            
            if not v1_blocked:
                graph.setdefault(v1, []).append((v2, eid))
            if not v2_blocked:
                graph.setdefault(v2, []).append((v1, eid))
        
        max_length = 0
        for start_v in graph.keys():
            visited = set()
            length = self._dfs_longest(start_v, graph, visited)
            max_length = max(max_length, length)
        
        return max_length

    def _dfs_longest(self, v, graph, visited):
        best = 0
        for nv, eid in graph.get(v, []):
            if eid not in visited:
                visited.add(eid)
                best = max(best, 1 + self._dfs_longest(nv, graph, visited))
                visited.remove(eid)
        return best

    def check_largest_army(self):
        best_k = 2
        best_p = None
        for p in self.players:
            if p.knights_played > best_k:
                best_k = p.knights_played
                best_p = p
        
        for p in self.players:
            was = p.largest_army
            p.largest_army = (p == best_p)
            if p.largest_army and not was:
                p.victory_points += 2
            elif not p.largest_army and was:
                p.victory_points -= 2

    def move_robber(self, new_pos, player: Player, log_func=print):
        for t in self.board.tiles.values():
            t.robber = False
        
        target = self.board.tiles.get(new_pos)
        if not target:
            return False, "Invalid"
        
        target.robber = True
        log_func(f"🕵️ Robber → {new_pos}")
        
        victims = set()
        for vid in self.board.vertices_of_tile(new_pos):
            v = self.board.vertices[vid]
            if v.owner and v.owner != player.id:
                victims.add(v.owner)
        
        if not victims:
            return True, "No victims"
        
        victim_id = random.choice(list(victims))
        victim = next((p for p in self.players if p.id == victim_id), None)
        if victim is None:
            return True, "Victim not found"
        
        avail = [r for r, c in victim.resources.items() if c > 0]
        if not avail:
            return True, "Empty"
        
        stolen = random.choice(avail)
        victim.resources[stolen] -= 1
        player.resources[stolen] += 1
        log_func(f"💰 Stole {RESOURCE_NAMES[stolen]} from {victim.name}")
        
        return True, "OK"

    def handle_robber_discard(self, log_func=print):
        for p in self.players:
            total = sum(p.resources.values())
            if total > 7:
                n = total // 2
                log_func(f"⚠️ {p.name} discards {n}")
                for _ in range(n):
                    avail = [r for r, c in p.resources.items() if c > 0]
                    if avail:
                        r = random.choice(avail)
                        p.resources[r] -= 1

    def end_turn(self):
        player = self.players[self.current]
        self.end_turn_cleanup(player)
        self.dice_rolled = False
        self.current_dice = (0, 0, 0)
        self.free_roads_remaining = 0
        self.current = (self.current + 1) % len(self.players)

# -------------------------
# UI
# -------------------------
class CatanUI:
    def __init__(self, root, game: Game):
        self.root = root
        self.game = game
        self.board = game.board
        
        self.placement_mode = None
        self.trade_window = None
        self.ai_config_window = None
        self.dev_window = None
        self._ai_scheduled = False
        
        self.ai_instances = {}
        for p in game.players:
            if p.is_computer:
                # default to minimax if ai_type not set
                if getattr(p, 'ai_type', None) == 'felix':
                    self.ai_instances[p.id] = FelixAI(game, p.id, FelixAI_CONFIG)
                elif getattr(p, 'ai_type', None) == 'raphi':
                    self.ai_instances[p.id] = MinimaxAI(game, p.id, AI_CONFIG)
        
        main_frame = tk.Frame(root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        
        self.canvas = tk.Canvas(main_frame, width=900, height=700, bg=CANVAS_BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, rowspan=10, padx=5, pady=5, sticky="nsew")
        
        ctrl = tk.Frame(main_frame, bg="#34495e", padx=8, pady=8)
        ctrl.grid(row=0, column=1, rowspan=10, sticky="nsew", padx=5, pady=5)
        
        tk.Label(ctrl, text="⬡ CATAN ⬡", font=("Arial", 18, "bold"),
                bg="#34495e", fg="#ecf0f1").pack(pady=8)
        
        pf = tk.Frame(ctrl, bg="#2c3e50", relief=tk.RAISED, bd=2)
        pf.pack(fill=tk.BOTH, pady=5)
        
        self.player_label = tk.Label(pf, text="", font=("Arial", 10, "bold"),
                                     bg="#2c3e50", fg="#ecf0f1", justify=tk.LEFT)
        self.player_label.pack(padx=8, pady=6)
        
        self.resources_label = tk.Label(pf, text="", font=("Arial", 8),
                                        bg="#2c3e50", fg="#bdc3c7", justify=tk.LEFT)
        self.resources_label.pack(padx=8, pady=(0,6))
        
        self.dev_label = tk.Label(pf, text="", font=("Arial", 8),
                                 bg="#2c3e50", fg="#f39c12", justify=tk.LEFT)
        self.dev_label.pack(padx=8, pady=(0,6))
        
        df = tk.Frame(ctrl, bg="#34495e")
        df.pack(fill=tk.X, pady=8)
        
        self.dice_label = tk.Label(df, text="🎲 Roll", font=("Arial", 9),
                                   bg="#34495e", fg="#ecf0f1")
        self.dice_label.pack()
        
        self.roll_btn = tk.Button(df, text="🎲 ROLL", command=self.on_roll,
                                  font=("Arial", 11, "bold"), bg="#e74c3c", fg="white",
                                  cursor="hand2", relief=tk.RAISED, bd=3)
        self.roll_btn.pack(pady=4)
        
        bf = tk.LabelFrame(ctrl, text="Build", font=("Arial", 9, "bold"),
                          bg="#34495e", fg="#ecf0f1", bd=2)
        bf.pack(fill=tk.BOTH, pady=8)
        
        bc = {"font": ("Arial", 8), "cursor": "hand2", "relief": tk.RAISED, "bd": 2, "width": 16}
        
        self.s_btn = tk.Button(bf, text="🏠 Settlement",
                              command=lambda: self.set_mode('settlement'),
                              bg="#3498db", fg="white", **bc)
        self.s_btn.pack(pady=2, padx=4)
        
        self.c_btn = tk.Button(bf, text="🏛️ City",
                              command=lambda: self.set_mode('city'),
                              bg="#9b59b6", fg="white", **bc)
        self.c_btn.pack(pady=2, padx=4)
        
        self.r_btn = tk.Button(bf, text="🛤️ Road",
                              command=lambda: self.set_mode('road'),
                              bg="#f39c12", fg="white", **bc)
        self.r_btn.pack(pady=2, padx=4)
        
        self.d_btn = tk.Button(bf, text="🃏 Buy Dev",
                              command=self.on_buy_dev,
                              bg="#1abc9c", fg="white", **bc)
        self.d_btn.pack(pady=2, padx=4)
        
        self.p_btn = tk.Button(bf, text="▶ Play Dev",
                              command=self.open_dev_window,
                              bg="#16a085", fg="white", **bc)
        self.p_btn.pack(pady=2, padx=4)
        
        tk.Button(ctrl, text="🤝 Trade", command=self.open_trade,
                 bg="#2980b9", fg="white", font=("Arial", 9, "bold"),
                 cursor="hand2", bd=2).pack(fill=tk.X, pady=4)
        
        self.end_btn = tk.Button(ctrl, text="END TURN", command=self.end_turn,
                                bg="#27ae60", fg="white", font=("Arial", 10, "bold"),
                                cursor="hand2", bd=3, height=2)
        self.end_btn.pack(fill=tk.X, pady=8)
        
        if any(p.is_computer for p in game.players):
            tk.Button(ctrl, text="⚙️ AI", command=self.open_ai_cfg,
                     bg="#34495e", fg="white", font=("Arial", 7),
                     cursor="hand2", bd=2).pack(fill=tk.X, pady=2)
        
        tk.Label(ctrl, text="Log", font=("Arial", 9, "bold"),
                bg="#34495e", fg="#ecf0f1").pack(pady=(8,0))
        
        self.log = scrolledtext.ScrolledText(ctrl, width=28, height=9,
                                             font=("Courier", 7), bg="#2c3e50", fg="#ecf0f1")
        self.log.pack(fill=tk.BOTH, expand=True, pady=4)
        
        self.stats_lbl = tk.Label(ctrl, text="", font=("Arial", 6),
                                 bg="#34495e", fg="#95a5a6")
        self.stats_lbl.pack(pady=2)
        
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)
        
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_hover)
        self.root.bind("<Escape>", lambda e: self.set_mode(None))
        
        self.vp = {}
        self.scale = 50.0
        self.ox = 0.0
        self.oy = 0.0
        self.hv = None
        self.he = None
        
        self.root.after(50, self.init_draw)

    def init_draw(self):
        self.compute_layout()
        self.draw_board()
        self.update_ui()
        self.log_msg("🎮 Catan - Fixed Harbors + Dev Cards!")
        self.log_msg(f"AI d={AI_CONFIG['depth']} auto={AI_CONFIG['auto_play']}")
        self.schedule_ai()

    def schedule_ai(self, delay=400):
        if self._ai_scheduled:
            return
        p = self.game.players[self.game.current]
        if p.is_computer and AI_CONFIG.get('auto_play', True):
            self._ai_scheduled = True
            self.root.after(delay, self._run_ai)

    def _run_ai(self):
        self._ai_scheduled = False
        p = self.game.players[self.game.current]
        if p.is_computer:
            self.ai_move()

    def axial_px(self, q, r, size):
        return size * math.sqrt(3) * (q + r/2.0), size * 1.5 * r

    def compute_layout(self):
        self.root.update_idletasks()
        w = max(self.canvas.winfo_width(), 200)
        h = max(self.canvas.winfo_height(), 200)
        
        positions = list(self.board.tiles.keys())
        
        # Adjust scale to account for harbors on edges
        lo, hi, best = 20.0, 60.0, 20.0
        for _ in range(12):
            mid = (lo + hi) / 2.0
            pts = [self.axial_px(q, r, mid) for q, r in positions]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            # Account for harbors extending outward (~40px)
            if max(xs)-min(xs)+mid*2.5+80 <= w*.88 and max(ys)-min(ys)+mid*2.5+80 <= h*.88:
                best = mid
                lo = mid
            else:
                hi = mid
        
        self.scale = best
        
        tmp = {vid: (v.qx, v.rx) for vid, v in self.board.vertices.items()}
        xs = [p[0] for p in tmp.values()]
        ys = [p[1] for p in tmp.values()]
        
        # Center with extra margin for harbors
        self.ox = (w - (max(xs)-min(xs)))/2 - min(xs)
        self.oy = (h - (max(ys)-min(ys)))/2 - min(ys)
        
        self.vp = {vid: (x + self.ox, y + self.oy) for vid, (x, y) in tmp.items()}
        
        for harbor in self.board.harbors:
            harbor.position = self.board.get_harbor_pixel_position(harbor, self.ox, self.oy)

    def hcpx(self, q, r):
        return [(x + self.ox, y + self.oy) for x, y in self.board.hex_corners_pixel_direct(q, r)]

    def draw_board(self):
        self.canvas.delete("all")
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.create_rectangle(0, 0, cw, ch, fill=CANVAS_BG, outline="")
        
        for (q, r), tile in self.board.tiles.items():
            pts = self.hcpx(q, r)
            flat = [c for p in pts for c in p]
            self.canvas.create_polygon(flat, fill=self.terrain_color(tile.terrain),
                                      outline="#2c3e50", width=2)
            
            cx = sum(p[0] for p in pts) / 6
            cy = sum(p[1] for p in pts) / 6
            
            if tile.token:
                tr = self.scale * 0.35
                tc = "#ffe5b4" if tile.token in (6,8) else "#f4e4c1"
                self.canvas.create_oval(cx-tr, cy-tr, cx+tr, cy+tr,
                                       fill=tc, outline="#8b4513", width=2)
                
                fc = "#c0392b" if tile.token in (6,8) else "#2c3e50"
                fs = max(10, int(self.scale*.32))
                self.canvas.create_text(cx, cy, text=str(tile.token),
                                       font=("Arial", fs, "bold"), fill=fc)
                
                dots = 5 - abs(7 - tile.token)
                for i in range(dots):
                    dx = cx + (i - (dots-1)/2) * 4
                    self.canvas.create_oval(dx-1.5, cy+tr*.65, dx+1.5, cy+tr*.65+3,
                                           fill=fc, outline="")
            
            if tile.robber:
                rr = self.scale * 0.22
                self.canvas.create_oval(cx-rr, cy-rr, cx+rr, cy+rr,
                                       fill="#1a1a1a", outline="#fff", width=2)
                self.canvas.create_text(cx, cy, text="🚫",
                                       font=("Arial", int(self.scale*.26)))
        
        # Draw harbors
        for harbor in self.board.harbors:
            if harbor.position is None:
                continue
            
            hx, hy = harbor.position
            hr = self.scale * 0.28
            
            self.canvas.create_oval(hx-hr-2, hy-hr-2, hx+hr+2, hy+hr+2,
                                   fill="white", outline="#2c3e50", width=2)
            
            h_colors = {
                '3:1': '#ffffff', 'wood': '#2d5016', 'brick': '#8b4513',
                'grain': '#f4d03f', 'sheep': '#a8d08d', 'ore': '#7f8c8d'
            }
            hcol = h_colors.get(harbor.type, '#ffffff')
            self.canvas.create_oval(hx-hr, hy-hr, hx+hr, hy+hr,
                                   fill=hcol, outline="#2c3e50", width=2)
            
            h_text = {'3:1': '3:1', 'wood': 'W', 'brick': 'B',
                     'grain': 'G', 'sheep': 'Sh', 'ore': 'O'}
            txt = h_text.get(harbor.type, '?')
            txt_color = "white" if harbor.type in ('wood', 'brick', 'ore') else "#1a1a1a"
            fs = max(8, int(self.scale * 0.20))
            self.canvas.create_text(hx, hy, text=txt,
                                   font=("Arial", fs, "bold"), fill=txt_color)
            
            if harbor.v1_id in self.vp and harbor.v2_id in self.vp:
                v1x, v1y = self.vp[harbor.v1_id]
                v2x, v2y = self.vp[harbor.v2_id]
                self.canvas.create_line(hx, hy, v1x, v1y, fill="#3498db", width=1, dash=(2,2))
                self.canvas.create_line(hx, hy, v2x, v2y, fill="#3498db", width=1, dash=(2,2))
        
        for eid, e in self.board.edges.items():
            x1, y1 = self.vp[e.v1]
            x2, y2 = self.vp[e.v2]
            
            lw = max(2, int(self.scale*.08))
            col = "#7f8c8d"
            
            if e.owner is not None:
                col = PLAYER_COLORS[(e.owner-1) % len(PLAYER_COLORS)]
                lw = max(4, int(self.scale*.12))
            
            if self.he == eid and self.placement_mode == 'road':
                col = "#f39c12"
                lw = max(6, int(self.scale*.15))
            
            self.canvas.create_line(x1, y1, x2, y2, fill=col, width=lw, capstyle=tk.ROUND)
        
        for vid, v in self.board.vertices.items():
            x, y = self.vp[vid]
            r = max(7, int(self.scale*.15))
            
            fill = "#ecf0f1"
            outline = "#95a5a6"
            lw = 2
            
            if self.hv == vid and self.placement_mode in ('settlement', 'city'):
                outline = "#f39c12"
                lw = 3
                r = max(9, int(self.scale*.18))
            
            if v.owner is not None:
                fill = PLAYER_COLORS[(v.owner-1) % len(PLAYER_COLORS)]
                outline = "#2c3e50"
                lw = 3
                
                if v.is_city:
                    sz = max(10, int(self.scale*.2))
                    self.canvas.create_rectangle(x-sz, y-sz, x+sz, y+sz,
                                                 fill=fill, outline=outline, width=lw)
                    self.canvas.create_polygon(x, y-sz*1.3, x-sz, y-sz, x+sz, y-sz,
                                               fill=fill, outline=outline, width=lw)
                    continue
            
            self.canvas.create_oval(x-r, y-r, x+r, y+r,
                                   fill=fill, outline=outline, width=lw)

    def on_click(self, event):
        x, y = event.x, event.y
        
        if self.game.robber_pending:
            tile = self.tile_at(x, y)
            if tile:
                p = self.game.players[self.game.current]
                ok, msg = self.game.move_robber(tile, p, self.log_msg)
                if ok:
                    self.game.robber_pending = False
                    self.set_mode(None)
                    self.draw_board()
                    self.update_ui()
                    self.schedule_ai(200)
            return
        
        if self.game.free_roads_remaining > 0 and self.placement_mode == 'road':
            eid = self.nearest_edge(x, y)
            if eid is not None:
                self.try_free_road(eid)
            return
        
        cv = self.nearest_vertex(x, y)
        ce = self.nearest_edge(x, y)
        
        if self.placement_mode == 'settlement' and cv is not None:
            self.try_settlement(cv)
        elif self.placement_mode == 'city' and cv is not None:
            self.try_city(cv)
        elif self.placement_mode == 'road' and ce is not None:
            self.try_road(ce)

    def on_hover(self, event):
        x, y = event.x, event.y
        oh, oe = self.hv, self.he
        self.hv = self.nearest_vertex(x, y)
        self.he = self.nearest_edge(x, y)
        if oh != self.hv or oe != self.he:
            self.draw_board()

    def nearest_vertex(self, x, y):
        tol = max(12, int(self.scale*.2))**2
        return next((vid for vid, (vx,vy) in self.vp.items()
                    if (x-vx)**2+(y-vy)**2 <= tol), None)

    def nearest_edge(self, x, y):
        tol = max(8, int(self.scale*.15))
        for eid, e in self.board.edges.items():
            x1, y1 = self.vp[e.v1]
            x2, y2 = self.vp[e.v2]
            ll = math.hypot(x2-x1, y2-y1)
            if ll == 0:
                continue
            t = max(0, min(1, ((x-x1)*(x2-x1)+(y-y1)*(y2-y1))/ll**2))
            if math.hypot(x-(x1+t*(x2-x1)), y-(y1+t*(y2-y1))) <= tol:
                return eid
        return None

    def tile_at(self, x, y):
        for (q, r) in self.board.tiles:
            pts = self.hcpx(q, r)
            inside = False
            j = len(pts) - 1
            for i in range(len(pts)):
                xi, yi = pts[i]
                xj, yj = pts[j]
                if (yi>y) != (yj>y) and x < (xj-xi)*(y-yi)/(yj-yi+1e-9)+xi:
                    inside = not inside
                j = i
            if inside:
                return (q, r)
        return None

    def try_settlement(self, vid):
        p = self.game.players[self.game.current]
        init = self.game.phase in ("initial_settlement", "initial_road")
        ok, msg = self.game.place_settlement(p, vid, initial=init, free=init)
        
        if ok:
            self.log_msg(f"✓ {p.name} settlement @{vid}")
            self.game.last_settlement_placed[p.id] = vid
            
            # Log resources granted for second settlement (reverse phase)
            n = len(self.game.players)
            if init and self.game.initial_placements >= n:
                v = self.game.board.vertices[vid]
                for tile_pos in v.tiles:
                    tile = self.game.board.tiles.get(tile_pos)
                    if tile and tile.terrain != 'D':
                        res = RESOURCE_MAP[tile.terrain]
                        if res:
                            self.log_msg(f"  +1 {RESOURCE_NAMES[res]}")
            
            if init:
                self.game.phase = "initial_road"
                self.set_mode('road')
                self.log_msg("Place road...")
            else:
                self.set_mode(None)
            
            self.draw_board()
            self.update_ui()
        else:
            self.log_msg(f"✗ {msg}")
            messagebox.showwarning("Cannot Build", msg)

    def try_city(self, vid):
        p = self.game.players[self.game.current]
        ok, msg = self.game.upgrade_to_city(p, vid)
        
        if ok:
            self.log_msg(f"✓ {p.name} city @{vid}")
            self.set_mode(None)
            self.draw_board()
            self.update_ui()
        else:
            self.log_msg(f"✗ {msg}")
            messagebox.showwarning("Cannot Build", msg)

    def try_road(self, eid):
        p = self.game.players[self.game.current]
        init = (self.game.phase == "initial_road")
        ok, msg = self.game.place_road(p, eid, initial=init, free=init)
        
        if ok:
            self.log_msg(f"✓ {p.name} road @{eid}")
            
            if init:
                self.advance_init()
            else:
                self.set_mode(None)
            
            self.draw_board()
            self.update_ui()
        else:
            self.log_msg(f"✗ {msg}")
            messagebox.showwarning("Cannot Build", msg)

    def try_free_road(self, eid):
        p = self.game.players[self.game.current]
        ok, msg = self.game.place_road(p, eid, free=True)
        
        if ok:
            self.game.free_roads_remaining -= 1
            self.log_msg(f"✓ Free road ({self.game.free_roads_remaining} left)")
            
            if self.game.free_roads_remaining == 0:
                self.set_mode(None)
                self.log_msg("Road Building done!")
            
            self.draw_board()
            self.update_ui()
        else:
            self.log_msg(f"✗ {msg}")

    def advance_init(self):
        self.game.initial_placements += 1
        n = len(self.game.players)
        
        if self.game.initial_placements < n * 2:
            if self.game.initial_placements < n:
                self.game.current = (self.game.current + 1) % n
                self.game.initial_round = 0
            else:
                if self.game.initial_placements == n:
                    self.game.initial_round = 1
                else:
                    self.game.current = (self.game.current - 1) % n
            
            self.game.phase = "initial_settlement"
            self.set_mode('settlement')
            self.log_msg(f"--- {self.game.players[self.game.current].name} R{self.game.initial_round+1} ---")
        else:
            self.game.phase = "play"
            self.game.current = 0
            self.set_mode(None)
            self.log_msg("=== Game starts! ===")
        
        self.schedule_ai()

    def set_mode(self, mode):
        self.placement_mode = mode
        self.hv = None
        self.he = None
        
        for b in (self.s_btn, self.c_btn, self.r_btn):
            b.config(relief=tk.RAISED, state=tk.NORMAL)
        
        if mode == 'settlement':
            self.s_btn.config(relief=tk.SUNKEN, state=tk.DISABLED)
        elif mode == 'city':
            self.c_btn.config(relief=tk.SUNKEN, state=tk.DISABLED)
        elif mode == 'road':
            self.r_btn.config(relief=tk.SUNKEN, state=tk.DISABLED)
        
        self.draw_board()

    def on_roll(self):
        if self.game.robber_pending:
            messagebox.showinfo("Robber", "Move robber first!")
            return
        if self.game.phase != "play":
            messagebox.showinfo("Wait", "Finish initial placement!")
            return
        if self.game.dice_rolled:
            messagebox.showinfo("Already", "Already rolled!")
            return
        
        p = self.game.players[self.game.current]
        d1, d2, total = self.game.roll_dice()
        
        self.log_msg(f"🎲 {p.name}: {d1}+{d2}={total}")
        self.dice_label.config(text=f"🎲 {d1}+{d2}={total}")
        
        self.game.distribute_resources(total, self.log_msg)
        
        if self.game.robber_pending and not p.is_computer:
            self.set_mode('robber')
            self.log_msg("Click tile for robber")
        
        self.draw_board()
        self.update_ui()

    def end_turn(self):
        if self.game.phase != "play":
            return
        
        self.set_mode(None)
        self.game.end_turn()
        
        p = self.game.players[self.game.current]
        self.log_msg(f"--- {p.name}'s turn ---")
        self.dice_label.config(text="🎲 Roll")
        
        self.update_ui()
        self.draw_board()
        self.schedule_ai()

    def on_buy_dev(self):
        p = self.game.players[self.game.current]
        if p.is_computer:
            return
        
        ok, result = self.game.buy_dev_card(p)
        if ok:
            self.log_msg(f"🃏 Bought {DEV_CARD_NAMES.get(result, result)}")
            self.update_ui()
        else:
            messagebox.showwarning("Cannot Buy", result)

    def open_dev_window(self):
        p = self.game.players[self.game.current]
        if p.is_computer or not p.dev_cards:
            messagebox.showinfo("No Cards", "No playable cards")
            return
        
        if self.dev_window and tk.Toplevel.winfo_exists(self.dev_window):
            self.dev_window.lift()
            return
        
        w = tk.Toplevel(self.root)
        self.dev_window = w
        w.title("Play Dev Card")
        w.configure(bg="#34495e")
        
        tk.Label(w, text="Choose card:", font=("Arial", 11, "bold"),
                bg="#34495e", fg="#ecf0f1").pack(pady=8, padx=20)
        
        for card in sorted(set(p.dev_cards)):
            if card == 'victory_point':
                continue
            
            def cmd(c=card):
                self.human_play_dev(c)
                w.destroy()
            
            tk.Button(w, text=DEV_CARD_NAMES.get(card, card), command=cmd,
                     font=("Arial", 10), bg="#2980b9", fg="white",
                     width=20, pady=4).pack(pady=3, padx=20)
        
        tk.Button(w, text="Cancel", command=w.destroy, bg="#7f8c8d", fg="white",
                 font=("Arial", 9)).pack(pady=8)

    def human_play_dev(self, card):
        p = self.game.players[self.game.current]
        
        if card == 'year_of_plenty':
            self.ask_year_of_plenty(p)
            return
        if card == 'monopoly':
            self.ask_monopoly(p)
            return
        
        ok, msg = self.game.play_dev_card(p, card, self.log_msg)
        if not ok:
            messagebox.showwarning("Error", msg)
            return
        
        if card == 'knight':
            self.set_mode('robber')
            self.log_msg("Click tile for robber")
        if card == 'road_building':
            self.set_mode('road')
            self.log_msg(f"Place {self.game.free_roads_remaining} free roads")
        
        self.draw_board()
        self.update_ui()

    def ask_year_of_plenty(self, player):
        w = tk.Toplevel(self.root)
        w.title("Year of Plenty")
        w.configure(bg="#34495e")
        
        tk.Label(w, text="Choose 2 resources:", font=("Arial", 11, "bold"),
                bg="#34495e", fg="#ecf0f1").pack(pady=8, padx=20)
        
        r1 = tk.StringVar(value='wood')
        r2 = tk.StringVar(value='grain')
        rl = list(RESOURCE_NAMES.keys())
        
        for lbl, var in (("Resource 1:", r1), ("Resource 2:", r2)):
            f = tk.Frame(w, bg="#34495e")
            f.pack(fill=tk.X, padx=20, pady=3)
            tk.Label(f, text=lbl, bg="#34495e", fg="#ecf0f1", width=12).pack(side=tk.LEFT)
            ttk.Combobox(f, textvariable=var, values=rl, state="readonly", width=10).pack(side=tk.LEFT)
        
        def confirm():
            ok, msg = self.game.play_dev_card(player, 'year_of_plenty', self.log_msg, (r1.get(), r2.get()))
            w.destroy()
            if not ok:
                messagebox.showwarning("Error", msg)
            self.draw_board()
            self.update_ui()
        
        tk.Button(w, text="Confirm", command=confirm, bg="#27ae60", fg="white",
                 font=("Arial", 10, "bold")).pack(pady=10)

    def ask_monopoly(self, player):
        w = tk.Toplevel(self.root)
        w.title("Monopoly")
        w.configure(bg="#34495e")
        
        tk.Label(w, text="Choose resource:", font=("Arial", 11, "bold"),
                bg="#34495e", fg="#ecf0f1").pack(pady=8, padx=20)
        
        rv = tk.StringVar(value='wood')
        ttk.Combobox(w, textvariable=rv, values=list(RESOURCE_NAMES.keys()),
                    state="readonly", width=12).pack(pady=8)
        
        def confirm():
            ok, msg = self.game.play_dev_card(player, 'monopoly', self.log_msg, rv.get())
            w.destroy()
            if not ok:
                messagebox.showwarning("Error", msg)
            self.draw_board()
            self.update_ui()
        
        tk.Button(w, text="Confirm", command=confirm, bg="#27ae60", fg="white",
                 font=("Arial", 10, "bold")).pack(pady=10)

    def open_trade(self):
        if self.trade_window and tk.Toplevel.winfo_exists(self.trade_window):
            self.trade_window.lift()
            return
        
        p = self.game.players[self.game.current]
        w = tk.Toplevel(self.root)
        self.trade_window = w
        w.title("Trade")
        w.configure(bg="#34495e")
        
        tk.Label(w, text="🤝 Trade", font=("Arial", 12, "bold"),
                bg="#34495e", fg="#ecf0f1").pack(pady=10)
        
        ht = "Harbors: " + (", ".join(p.harbors) if p.harbors else "none (4:1)")
        tk.Label(w, text=ht, font=("Arial", 9), bg="#34495e", fg="#bdc3c7").pack()
        
        f = tk.Frame(w, bg="#2c3e50")
        f.pack(padx=20, pady=10)
        
        gv = tk.StringVar(value='wood')
        tv = tk.StringVar(value='brick')
        
        tk.Label(f, text="Give:", bg="#2c3e50", fg="#ecf0f1").grid(row=0, column=0)
        ttk.Combobox(f, textvariable=gv, values=list(RESOURCE_NAMES.keys()),
                    state="readonly", width=10).grid(row=0, column=1, padx=5)
        
        tk.Label(f, text="Get:", bg="#2c3e50", fg="#ecf0f1").grid(row=1, column=0, pady=5)
        ttk.Combobox(f, textvariable=tv, values=list(RESOURCE_NAMES.keys()),
                    state="readonly", width=10).grid(row=1, column=1, padx=5, pady=5)
        
        def do():
            give, get = gv.get(), tv.get()
            if give == get:
                messagebox.showwarning("Invalid", "Same resource!")
                return
            
            ratio = 4
            if '3:1' in p.harbors:
                ratio = 3
            if give in p.harbors:
                ratio = 2
            
            if p.resources[give] < ratio:
                messagebox.showwarning("Insufficient", f"Need {ratio} {give}")
                return
            
            p.resources[give] -= ratio
            p.resources[get] += 1
            
            self.log_msg(f"💱 {ratio}×{give}→{get}")
            self.update_ui()
            messagebox.showinfo("Done", f"Traded {ratio} {give} for 1 {get}")
        
        tk.Button(f, text="Trade", command=do, bg="#27ae60", fg="white",
                 font=("Arial", 10, "bold")).grid(row=2, column=0, columnspan=2, pady=8)

    def open_ai_cfg(self):
        if self.ai_config_window and tk.Toplevel.winfo_exists(self.ai_config_window):
            self.ai_config_window.lift()
            return
        
        w = tk.Toplevel(self.root)
        self.ai_config_window = w
        w.title("AI")
        w.configure(bg="#34495e")
        
        tk.Label(w, text="⚙️ AI", font=("Arial", 12, "bold"),
                bg="#34495e", fg="#ecf0f1").pack(pady=10)
        
        f = tk.Frame(w, bg="#2c3e50")
        f.pack(padx=20, pady=8)
        
        dv = tk.IntVar(value=AI_CONFIG['depth'])
        tv = tk.DoubleVar(value=AI_CONFIG['time_limit'])
        
        tk.Label(f, text="Depth:", bg="#2c3e50", fg="#ecf0f1").grid(row=0, column=0, pady=4)
        tk.Spinbox(f, from_=1, to=5, textvariable=dv, width=8).grid(row=0, column=1)
        
        tk.Label(f, text="Time:", bg="#2c3e50", fg="#ecf0f1").grid(row=1, column=0, pady=4)
        tk.Spinbox(f, from_=1, to=20, increment=.5, textvariable=tv, width=8).grid(row=1, column=1)
        
        pv = tk.BooleanVar(value=AI_CONFIG['enable_pruning'])
        tk.Checkbutton(f, text="Pruning", variable=pv, bg="#2c3e50", fg="#ecf0f1",
                      selectcolor="#34495e").grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
        
        av = tk.BooleanVar(value=AI_CONFIG['auto_play'])
        tk.Checkbutton(f, text="Auto-play", variable=av, bg="#2c3e50", fg="#ecf0f1",
                      selectcolor="#34495e").grid(row=3, column=0, columnspan=2, sticky="w", pady=2)
        
        def apply():
            AI_CONFIG['depth'] = dv.get()
            AI_CONFIG['time_limit'] = tv.get()
            AI_CONFIG['enable_pruning'] = pv.get()
            AI_CONFIG['auto_play'] = av.get()
            
            for ai in self.ai_instances.values():
                ai.config = AI_CONFIG
            
            self.log_msg(f"AI: d={AI_CONFIG['depth']} t={AI_CONFIG['time_limit']}s")
            messagebox.showinfo("Saved", "Updated!")
            w.destroy()
        
        tk.Button(w, text="Apply", command=apply, bg="#27ae60", fg="white",
                 font=("Arial", 10, "bold")).pack(pady=10)

    def ai_move(self):
        p = self.game.players[self.game.current]
        if not p.is_computer:
            return
        
        if self.game.phase in ("initial_settlement", "initial_road"):
            self.ai_init()
            return
        
        if self.game.robber_pending:
            self.ai_robber()
            self.schedule_ai(200)
            return
        
        if self.game.free_roads_remaining > 0:
            self.ai_free_roads()
            return
        
        if not self.game.dice_rolled:
            d1, d2, total = self.game.roll_dice()
            self.log_msg(f"🎲 {p.name}: {d1}+{d2}={total}")
            self.dice_label.config(text=f"🎲 {d1}+{d2}={total}")
            self.game.distribute_resources(total, self.log_msg)
            self.draw_board()
            self.update_ui()
            
            if self.game.robber_pending:
                self.schedule_ai(300)
                return
        
        self.log_msg(f"🤖 {p.name} thinking...")
        self.root.update()
        
        
        # muss hier bleiben
        if p.id not in self.ai_instances:
            if getattr(p, 'ai_type', None) == 'felix':
                self.ai_instances[p.id] = FelixAI(self.game, p.id, FelixAI_CONFIG)
            else:
                self.ai_instances[p.id] = MinimaxAI(self.game, p.id, AI_CONFIG)
        
        ai = self.ai_instances[p.id]
        ai.game = self.game
        
        def run():
            mv, n, cu, el = ai.get_best_move()
            self.root.after(0, lambda: self.apply_ai_move(p, ai, mv, n, cu, el))
        
        threading.Thread(target=run, daemon=True).start()

    def apply_ai_move(self, player, ai, best_move, nodes, cutoffs, elapsed):
        self.stats_lbl.config(text=f"N:{nodes} C:{cutoffs} {elapsed:.1f}s")
        self.log_msg(f"🧠 {nodes}n {elapsed:.1f}s")
        
        if best_move is None or best_move[0] == 'end_turn':
            self.log_msg(f"🤖 {player.name} ends")
            self.end_turn()
            return
        
        mt, md = best_move
        ok = False
        
        if mt == 'settlement':
            ok, msg = self.game.place_settlement(player, md)
            if ok:
                self.log_msg(f"🤖 settlement @{md}")
        elif mt == 'city':
            ok, msg = self.game.upgrade_to_city(player, md)
            if ok:
                self.log_msg(f"🤖 city @{md}")
        elif mt == 'road':
            ok, msg = self.game.place_road(player, md)
            if ok:
                self.log_msg(f"🤖 road @{md}")
        elif mt == 'buy_dev_card':
            ok, card = self.game.buy_dev_card(player)
            if ok:
                self.log_msg(f"🤖 bought {DEV_CARD_NAMES.get(card, card)}")
        elif mt == 'play_dev_card':
            card = md
            extra = None
            
            if card == 'year_of_plenty':
                needs = sorted(RESOURCE_NAMES.keys(), key=lambda r: player.resources[r])
                extra = (needs[0], needs[1])
            elif card == 'monopoly':
                tc = Counter()
                for opp in self.game.players:
                    if opp.id != player.id:
                        tc.update(opp.resources)
                extra = tc.most_common(1)[0][0] if tc else 'wood'
            
            ok, msg = self.game.play_dev_card(player, card, self.log_msg, extra)
            if ok:
                self.log_msg(f"🤖 played {DEV_CARD_NAMES.get(card, card)}")
                if self.game.robber_pending:
                    self.draw_board()
                    self.update_ui()
                    self.schedule_ai(300)
                    return
                if self.game.free_roads_remaining > 0:
                    self.draw_board()
                    self.update_ui()
                    self.schedule_ai(300)
                    return
        elif mt == 'trade':
            give, get = md
            ratio = ai.get_trade_ratio(player, give)
            if player.resources[give] >= ratio:
                player.resources[give] -= ratio
                player.resources[get] += 1
                self.log_msg(f"🤖 trade {ratio}×{give}→{get}")
                ok = True
        
        self.draw_board()
        self.update_ui()
        
        if ok:
            self.schedule_ai(300)
        else:
            self.log_msg("⚠️ Move failed, ending")
            self.end_turn()

    def ai_init(self):
        p = self.game.players[self.game.current]
        
        if p.ai_type == "felix":
            if self.game.phase == "initial_settlement":
                
                
                best_v, bs = None, -1
                for vid in self.board.vertices.keys():
                    if self.game.can_place_settlement(p, vid, initial=True)[0]:
                        best_v = self.board.vertices[vid]
                        
                if best_v:
                    self.game.place_settlement(p, best_v, initial=True, free=True)
                    self.game.last_settlement_placed[p.id] = best_v
                    self.log_msg(f"🤖 init settlement @{best_v}")
                    self.game.phase = "initial_road"
                    self.draw_board()
                    self.update_ui()
                    self.schedule_ai(300)
                
            if self.game.phase == "initial_road":
                ls = self.game.last_settlement_placed.get(p.id)
                if ls:
                    for eid in self.board.edges_of_vertex(ls):
                        if self.game.can_place_road(p, eid, initial=True)[0]:
                            self.game.place_road(p, eid, initial=True, free=True)
                            self.log_msg(f"🤖 init road @{eid}")
                            self.advance_init()
                            self.draw_board()
                            self.update_ui()
                            break  
                
                
                
        elif p.ai_type == "raphi":
            
            if self.game.phase == "initial_settlement":
                best_v, bs = None, -1
                for vid in self.board.vertices.keys():
                    if self.game.can_place_settlement(p, vid, initial=True)[0]:
                        best_v = self.board.vertices[vid]
                        
                if best_v:
                    self.game.place_settlement(p, best_v, initial=True, free=True)
                    self.game.last_settlement_placed[p.id] = best_v
                    self.log_msg(f"🤖 init settlement @{best_v}")
                    self.game.phase = "initial_road"
                    self.draw_board()
                    self.update_ui()
                    self.schedule_ai(300)
                
            if self.game.phase == "initial_road":
                ls = self.game.last_settlement_placed.get(p.id)
                if ls:
                    for eid in self.board.edges_of_vertex(ls):
                        if self.game.can_place_road(p, eid, initial=True)[0]:
                            self.game.place_road(p, eid, initial=True, free=True)
                            self.log_msg(f"🤖 init road @{eid}")
                            self.advance_init()
                            self.draw_board()
                            self.update_ui()
                            break  


    def ai_robber(self):
        p = self.game.players[self.game.current]
        if p.ai_type == "felix":
        
            best_pos, bs = None, -999
        
            for pos, tile in self.board.tiles.items():
                if tile.robber:
                    continue
                best_pos = pos
        
            if best_pos:
                self.game.move_robber(best_pos, p, self.log_msg)
                self.game.robber_pending = False
                self.draw_board()
                self.update_ui()
                self.schedule_ai(300)
        
        if p.ai_type == "raphi":
        
            best_pos, bs = None, -999
        
            for pos, tile in self.board.tiles.items():
                if tile.robber:
                    continue
                best_pos = pos
        
            if best_pos:
                self.game.move_robber(best_pos, p, self.log_msg)
                self.game.robber_pending = False
                self.draw_board()
                self.update_ui()
                self.schedule_ai(300)

    def ai_free_roads(self):
        p = self.game.players[self.game.current]
        
        if p.ai_type == "felix":
            for eid in list(self.board.edges):
                if self.game.free_roads_remaining <= 0:
                    break
                ok, _ = self.game.can_place_road(p, eid, free=True)
                if ok:
                    self.game.place_road(p, eid, free=True)
                    self.game.free_roads_remaining -= 1
                    self.log_msg(f"🤖 free road @{eid}")
            
            self.game.free_roads_remaining = 0
            self.draw_board()
            self.update_ui()
            self.schedule_ai(300)
            
            
        if p.ai_type == "raphi":
            for eid in list(self.board.edges):
                if self.game.free_roads_remaining <= 0:
                    break
                ok, _ = self.game.can_place_road(p, eid, free=True)
                if ok:
                    self.game.place_road(p, eid, free=True)
                    self.game.free_roads_remaining -= 1
                    self.log_msg(f"🤖 free road @{eid}")
            
            self.game.free_roads_remaining = 0
            self.draw_board()
            self.update_ui()
            self.schedule_ai(300)

    def update_ui(self):
        p = self.game.players[self.game.current]
        col = PLAYER_COLORS[(p.id-1) % len(PLAYER_COLORS)]
        
        vt = f"{p.name} - {p.victory_points} VP"
        if p.longest_road:
            vt += " 🛤️"
        if p.largest_army:
            vt += " ⚔️"
        
        self.player_label.config(text=vt, fg=col)
        
        rt = "Resources:\n"
        for r in ('wood', 'brick', 'grain', 'sheep', 'ore'):
            rt += f"  {RESOURCE_NAMES[r]}: {p.resources[r]}\n"
        
        if p.harbors:
            rt += f"\nHarbors: {', '.join(p.harbors)}"
        
        self.resources_label.config(text=rt)
        
        playable = sorted(p.dev_cards)
        new_ = sorted(p.dev_cards_new)
        dt = ""
        if playable:
            dt += "Cards: " + " | ".join(DEV_CARD_NAMES.get(c, c) for c in playable) + "\n"
        if new_:
            dt += "(next): " + " | ".join(DEV_CARD_NAMES.get(c, c) for c in new_)
        
        self.dev_label.config(text=dt)
        
        leaders = sorted(self.game.players, key=lambda x: -x.victory_points)
        if leaders[0].victory_points >= 10:
            w = leaders[0]
            self.log_msg(f"🎉 {w.name} WINS ({w.victory_points} VP)!")
            fn = self.game.tracker.save_to_file()
            messagebox.showinfo("Win", f"{w.name} wins!\nLog: {fn}")

    def log_msg(self, text):
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def terrain_color(self, t):
        return {
            'W': "#2d5016", 'H': "#8b4513", 'F': "#f4d03f",
            'S': "#a8d08d", 'G': "#7f8c8d", 'D': "#f39c12"
        }.get(t, "#bdc3c7")

# -------------------------
# Setup
# -------------------------
def create_players():
    return [
        Player(id=1, name="Red", is_computer=True, ai_type="felix"),
        Player(id=2, name="Blue", is_computer=True, ai_type="felix"),
        Player(id=3, name="Orange", is_computer=True, ai_type="felix"),
        Player(id=4, name="Green", is_computer=True, ai_type="felix"),
    ]

def main():
    root = tk.Tk()
    root.title("⬡ Catan - Complete ⬡")
    root.geometry("1380x880")
    root.configure(bg="#34495e")
    
    CatanUI(root, Game(create_players()))
    root.mainloop()

if __name__ == "__main__":
    main()