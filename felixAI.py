
# -------------------------
# Felix AI (helper-only)
# -------------------------
from collections import Counter
import time

from config import FelixAI_CONFIG

class MinimaxAI:
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
            return self.evaluate_board_state(self.game, self.player_id), None
        
        best_val, best_move = 0,0
        
        return best_val, best_move
  