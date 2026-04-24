from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional, Set
from collections import Counter
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
