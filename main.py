
import tkinter as tk
from reversi_gui import ReversiGUI

def main():
    root = tk.Tk()
    # Make window not resizable for simplicity
    root.resizable(False, False)
    app = ReversiGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
