"""Game selection dialog for choosing between Avatar and Far Cry 2"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QWidget, QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap

class GameSelectorDialog(QDialog):
    """Dialog for selecting which game to edit"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_game = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the game selection UI"""
        self.setWindowTitle("Select Game - Level Editor")
        self.setModal(True)
        self.setMinimumSize(700, 400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Title
        title_label = QLabel("Select Game to Edit")
        title_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Choose which game's levels you want to edit")
        subtitle_label.setFont(QFont("Arial", 12))
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #666;")
        layout.addWidget(subtitle_label)
        
        layout.addSpacing(20)
        
        # Game selection buttons layout
        games_layout = QHBoxLayout()
        games_layout.setSpacing(30)

        # Avatar: The Game button with icon
        avatar_button = self.create_game_button(
            "Avatar: The Game",
            "Single 16×16 sector grid per level",
            "#0E3250",
            icon_path="icon/avatar_icon.png"
        )
        avatar_button.clicked.connect(lambda: self.select_game("avatar"))
        games_layout.addWidget(avatar_button)

        # Far Cry 2 button with icon
        fc2_button = self.create_game_button(
            "Far Cry 2",
            "5×5 world grid\n(25 map regions, each 16×16 sectors)",
            "#FF5722",
            icon_path="icon/fc2_icon.png"
        )
        fc2_button.clicked.connect(lambda: self.select_game("farcry2"))
        games_layout.addWidget(fc2_button)

        layout.addLayout(games_layout)
        
        layout.addStretch()
        
        # Info label
        info_label = QLabel("Both games use 64-unit sectors")
        info_label.setFont(QFont("Arial", 9))
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #999; font-style: italic;")
        layout.addWidget(info_label)
    
    def create_game_button(self, title, description, color, icon_path=None):
        """Create a styled game selection button with optional icon, supports zooming small icons."""
        button = QPushButton()
        button.setMinimumSize(280, 200)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Layout for button content
        button_layout = QVBoxLayout(button)
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: white;")
        button_layout.addWidget(title_label)
        
        # Icon (optional)
        if icon_path:
            icon_label = QLabel()
            pixmap = QPixmap(icon_path)
            if pixmap.isNull():
                print(f"Warning: Could not load icon: {icon_path}")
            else:
                # Target display size for zoomed icon
                target_size = 240

                # If icon is smaller than target, scale it up with FastTransformation
                if pixmap.width() < target_size and pixmap.height() < target_size:
                    pixmap = pixmap.scaled(
                        target_size, target_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation  # nearest-neighbor, keeps it sharp
                    )
                else:
                    # Large icons scale down smoothly
                    pixmap = pixmap.scaled(
                        target_size, target_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )

                # Center the icon on a 120x120 canvas
                canvas = QPixmap(target_size, target_size)
                canvas.fill(Qt.GlobalColor.transparent)
                from PyQt6.QtGui import QPainter
                painter = QPainter(canvas)
                x = (target_size - pixmap.width()) // 2
                y = (target_size - pixmap.height()) // 2
                painter.drawPixmap(x, y, pixmap)
                painter.end()

                icon_label.setPixmap(canvas)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                button_layout.addWidget(icon_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Arial", 11))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: white;")
        button_layout.addWidget(desc_label)
        
        button_layout.addStretch()
        
        # Style button
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 3px solid {color};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
                border: 3px solid white;
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(color, 0.3)};
            }}
        """)
        
        return button
    
    def darken_color(self, hex_color, factor=0.2):
        """Darken a hex color by a factor"""
        # Remove '#' if present
        hex_color = hex_color.lstrip('#')
        
        # Convert to RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Darken
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def select_game(self, game):
        """Handle game selection"""
        self.selected_game = game
        self.accept()
    
    def get_selected_game(self):
        """Return the selected game"""
        return self.selected_game