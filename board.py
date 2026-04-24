from entities import Tile, Vertex, Edge, Harbor
from typing import Dict, Tuple, List

import math
import random

from config import TERRAIN_POOL, NUMBER_TOKENS, RADIUS, generate_axial_positions_radius, axial_to_cube


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
