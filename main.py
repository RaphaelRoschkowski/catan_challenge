# catan_complete.py
# Catan with Fixed Harbors + Dev Cards + Enhanced Minimax AI
import tkinter as tk
from copy import deepcopy

from game import Game
from ui import CatanUI
from entities import Player


# -------------------------
# Setup
# -------------------------
def create_players():
    return [
        Player(id=1, name="Red", is_computer=False, ai_type="felix"),
        Player(id=2, name="Blue", is_computer=False, ai_type="felix"),
        Player(id=3, name="Orange", is_computer=False, ai_type="felix"),
        Player(id=4, name="Green", is_computer=False, ai_type="felix"),
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