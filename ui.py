import math
import threading
import tkinter as tk

from tkinter import messagebox, scrolledtext, ttk
from collections import Counter

from config import AI_CONFIG, CANVAS_BG, DEV_CARD_NAMES, PLAYER_COLORS, RESOURCE_MAP, RESOURCE_NAMES, FelixAI_CONFIG
from felixAI import FelixAI, MinimaxAI
from game import Game
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
        #if self.trade_window and tk.Toplevel.winfo_exists(self.trade_window):
        #    self.trade_window.lift()
        #    return
        
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
