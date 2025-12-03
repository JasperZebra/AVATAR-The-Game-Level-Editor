import sys
import os
import multiprocessing

# CRITICAL: Must be first
if __name__ == "__main__":
    multiprocessing.freeze_support()

def main():
    """Main application entry point with game selection"""

    # Prevent launching GUI inside worker processes
    if multiprocessing.current_process().name != "MainProcess":
        return

    # 👉 Move GUI imports here so workers NEVER import them
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from game_selector import GameSelectorDialog
    from simplified_map_editor import SimplifiedMapEditor

    app = QApplication(sys.argv)

    default_icon_path = os.path.join("icon", "avatar_icon.ico")
    if os.path.exists(default_icon_path):
        app.setWindowIcon(QIcon(default_icon_path))

    selector = GameSelectorDialog()
    result = selector.exec()

    if result == GameSelectorDialog.DialogCode.Accepted:
        selected_game = selector.get_selected_game()

        if selected_game:
            print(f"Selected game: {selected_game}")

            if "avatar" in selected_game.lower():
                icon_file = "avatar_icon.ico"
            elif any(x in selected_game.lower() for x in ["fc2", "farcry"]):
                icon_file = "fc2_icon.ico"
            else:
                icon_file = "avatar_icon.ico"

            icon_path = os.path.join("icon", icon_file)
            game_icon = QIcon(icon_path) if os.path.exists(icon_path) else None

            editor = SimplifiedMapEditor(game_mode=selected_game)

            if game_icon:
                editor.setWindowIcon(game_icon)
                app.setWindowIcon(game_icon)

            editor.show()
            sys.exit(app.exec())
        else:
            print("No game selected, exiting")
            sys.exit(0)
    else:
        print("User cancelled selection, exiting")
        sys.exit(0)

# CRITICAL: GUI + Qt imports MUST NOT exist at top level
if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
