import time
import json
import random

from typing import Dict, List

from config import COSTS, DEV_CARD_DECK, RESOURCE_MAP, RESOURCE_NAMES
from entities import Player
from board import Board
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


