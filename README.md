# vim2vid

Generate realistic VIM typing videos from text files. Perfect for social media content.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Basic usage (uses default.json)
vim2vid input.txt output.mp4

# With custom config
vim2vid input.txt output.mp4 --config my_config.json
```

## Configuration

All settings are in JSON files. Create custom configs by copying and editing the provided examples:

```json
{
  "width": 1280,
  "height": 720,
  "font_size": 18,
  "typing_speed_base": 0.05,
  "highlight_patterns": ["TODO", "important"],
  "special_sequences": {
    "GPT-4": ["GPT-3", "GPT-4"]
  }
}
```

**Provided configs:**
- `default.json` - Basic settings
- `config_example.json` - With highlighting and special effects

## Features

- **Auto filename** - VIM shows your actual input file
- **JSON-only config** - No CLI parameter clutter
- **Progress bar** - Shows typing progress
- **Syntax highlighting** - Custom color patterns
- **Special sequences** - Dramatic corrections
- **Realistic behavior** - Variable speed, mistakes

## Examples

```bash
# LinkedIn square format
vim2vid farewell.txt linkedin.mp4

# Custom widescreen
vim2vid tutorial.py youtube.mp4 --config widescreen.json

# With French phrases highlighted  
vim2vid farewell.txt french.mp4 --config config_example.json
```

## License

MIT