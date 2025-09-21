![GitHub release (latest by date)](https://img.shields.io/github/v/release/JasperZebra/AVATAR-The-Game-Level-Editor?style=for-the-badge&logo=github&color=00ffff&logoColor=white&labelColor=1a4d66)
![Total Downloads](https://img.shields.io/github/downloads/JasperZebra/Avatar-The-Game-Level-Editor/total?style=for-the-badge&logo=github&color=00ffff&logoColor=white&labelColor=1a4d66) 
![Platform](https://img.shields.io/badge/platform-windows-00ffff?style=for-the-badge&logo=windows&logoColor=00ffff&labelColor=1a4d66) 
![Made for](https://img.shields.io/badge/made%20for-2009_AVATAR:_The_Game-00ffff?style=for-the-badge&logo=gamepad&logoColor=00ffff&labelColor=1a4d66) 
![Tool Type](https://img.shields.io/badge/type-level%20editor-00ffff?style=for-the-badge&logo=edit&logoColor=00ffff&labelColor=1a4d66)


# Avatar: The Game Level Editor

A level editor for modifying **Avatar: The Game** level files with full FCB to XML conversion support and real-time xml file editing capabilities.

**NOTE:** To run from SC, download the SC `.zip` and also download this [tools](https://drive.google.com/file/d/1ODFv-8vchhmCzvmx5WS6GT7gApLQ-lDz/view?usp=sharing) folder too and extract it to the root of the editor.

## Features

- **Dual-Format Support**: Seamlessly works with both FCB and XML file formats with automatic conversion
- **Visual Entity Management**: Drag-and-drop positioning, rotation gizmos, and real-time property editing
- **Smart Entity Operations**: Copy/paste, duplication with auto-generated IDs, and batch operations
- **Interactive Canvas**: Color-coded entity visualization with adaptive grid system
- **Sector Management**: Visual boundary display with violation detection

## Quick Start

### Loading a Level
1. Click **"Select Level"** and follow the two-step process:
   - **Step 1**: Select your `worlds` folder (contains XML files like mapsdata.xml)
   - **Step 2**: Select your `levels` folder (contains worldsectors)
2. Files are automatically loaded and converted as needed

### Basic Controls
- **Select**: Left-click 
- **Move**: Drag entities or use Entity Editor
- **Rotate**: Use the blue rotation gizmo
- **Edit**: Open Entity Editor **(Ctrl+E**) for detailed properties
- **Save**: Use **"Save Level"** to convert back to FCB format

## Keyboard Shortcuts

| Action | Shortcut | Description |
|--------|----------|-------------|
| **File Operations** |
| Open Level | `Ctrl+O` | Two-step level loading |
| Save Level | `Ctrl+S` | Save changes to FCB format |
| **Editing** |
| Entity Editor | `Ctrl+E` | Open property editor |
| Copy | `Ctrl+C` | Copy selected entities |
| Paste | `Ctrl+V` | Paste entities |
| Duplicate | `Ctrl+D` | Duplicate with +20 X/Y offset |
| Delete | `Delete` | Remove selected entities |
| **View Controls** |
| Reset View | `R` | Center and reset camera |
| Toggle Entities | `E` | Show/hide entity visibility |
| Toggle Grid | `G` | Show/hide grid lines |
| Camera Movement | `WASD` | Move camera (Shift for speed boost) |
| Zoom | `Mouse Wheel` | Cursor-centered zooming |

## Entity Types & Visualization

Entities are automatically color-coded by type with size-based scaling:

- **Blue**: Vehicles (cars, boats, aircraft)
- **Green**: NPCs/Characters  
- **Red**: Weapons/Combat items
- **Orange**: Spawn points
- **Purple**: Mission objects
- **Yellow**: Triggers/Zones
- **Light Yellow**: Lights
- **Teal**: Effects/Particles
- **Gray**: Props/Static objects
- **Dark Gray**: Unknown types

## Supported Files

### Primary Files
- `mapsdata.xml/.fcb` - Main map data and entities
- `managers.xml/.fcb` - Game system managers
- `omnis.xml/.fcb` - Universal objects
- `sectorsdep.xml/.fcb` - Sector dependencies
- `worldsector*.data.fcb` - Individual sector data

Both FCB (native game format) and XML (human-readable) formats are supported with automatic conversion.

## Editor Components

### Entity Editor
- Real-time property editing with live preview
- Component system support (vehicle physics, graphics, missions)
- Direct XML field manipulation with type detection
- Optional auto-save functionality

### Visual Tools
- **Rotation Gizmo**: Interactive rotation with real-time angle display
- **Grid System**: Multi-level grids that adapt to zoom level
- **Sector Boundaries**: Visual boundaries with violation detection
- **Entity Browser**: Searchable, filterable entity management

## Safety & Best Practices

⚠️ **Important**: Always backup your level files before editing

### Recommendations
- Close Avatar: The Game completely before saving changes
- Test modifications by loading the level in-game
- Use the Entity Editor for precise property changes
- Keep sector boundaries visible to avoid placement issues

## Work in Progress Features

- Enhanced fence object detection and rendering
- Entity collection export/import system  
- New sector creation tools
