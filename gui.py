"""Launch the Jarvis Modern UI (2D Web HUD by default, or --native for Tkinter)."""
import sys

if __name__ == "__main__":
    if "--native" in sys.argv:
        from jarvis.gui import run_gui
        sys.exit(run_gui())
    else:
        from run_web import main
        sys.exit(main())
