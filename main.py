import sys
import os
import multiprocessing
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from game_selector import GameSelectorDialog
from simplified_map_editor import SimplifiedMapEditor

if __name__ == '__main__':
    multiprocessing.freeze_support()

def main(): 
    """Main application entry point with game selection"""
    app = QApplication(sys.argv)
    
    # Set a default icon before anything else
    default_icon_path = os.path.join("icon", "avatar_icon.ico")
    if os.path.exists(default_icon_path):
        app.setWindowIcon(QIcon(default_icon_path))
    else:
        print(f"Warning: Default icon not found at {default_icon_path}")
    
    # Show the game selection dialog
    selector = GameSelectorDialog()
    result = selector.exec()
    
    if result == GameSelectorDialog.DialogCode.Accepted:
        selected_game = selector.get_selected_game()
        
        if selected_game:
            print(f"Selected game: {selected_game}")
            
            # Determine correct icon
            if "avatar" in selected_game.lower():
                icon_file = "avatar_icon.ico"
            elif "fc2" in selected_game.lower() or "farcry" in selected_game.lower():
                icon_file = "fc2_icon.ico"
            else:
                icon_file = "avatar_icon.ico"
            
            icon_path = os.path.join("icon", icon_file)
            game_icon = QIcon(icon_path) if os.path.exists(icon_path) else None
            
            # Launch the editor with selected game
            editor = SimplifiedMapEditor(game_mode=selected_game)
            
            # ✅ Apply new icon directly to the main window and app
            if game_icon:
                editor.setWindowIcon(game_icon)
                app.setWindowIcon(game_icon)
            else:
                print(f"Warning: Could not find icon for {selected_game} at {icon_path}")
            
            editor.show()
            sys.exit(app.exec())
        else:
            print("No game selected, exiting")
            sys.exit(0)
    else:
        print("User cancelled selection, exiting")
        sys.exit(0)

if __name__ == "__main__":
    main()
 