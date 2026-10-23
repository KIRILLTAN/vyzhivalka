"""Vyzhivalka.exe: без аргументов открывает лаунчер, с --game - саму игру.
Из исходников: python main.py - игра, python launcher.py - лаунчер."""
import sys


def main():
    if "--uninstall" in sys.argv:
        from game import install
        install.uninstall(sys.argv)
        return
    if getattr(sys, "frozen", False) and "--game" not in sys.argv:
        from launcher import Launcher
        Launcher().run()
        return
    from game.app import App
    App().run()


if __name__ == "__main__":
    main()
