import sys
import os

# CRITICAL: Add freeze_support BEFORE any other imports
import multiprocessing
if __name__ == '__main__':
    multiprocessing.freeze_support()

# Now do the other imports
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from simplified_map_editor import SimplifiedMapEditor

def main(): 
    """Main application entry point"""
    # Create and run the application
    app = QApplication(sys.argv)
    
    # Set application icon
    icon_path = os.path.join("icon", "avatar_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"Warning: Icon file not found at {icon_path}")
    
    editor = SimplifiedMapEditor()
    editor.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 