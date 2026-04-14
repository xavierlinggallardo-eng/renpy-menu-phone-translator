"""Punto de entrada."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from renpymenu.app import main
if __name__ == "__main__":
    main()
