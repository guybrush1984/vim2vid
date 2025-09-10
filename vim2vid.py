#!/usr/bin/env python3
"""
vim2vid - Convert text to a realistic VIM typing video
Perfect for creating engaging technical content for social media.
"""

import argparse
import json
import os
import sys
import time
import random
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont


@dataclass
class VideoConfig:
    """Configuration for video generation"""
    # Video settings
    width: int
    height: int
    fps: int
    font_size: int
    font_path: Optional[str]
    
    # VIM settings
    columns: int
    rows: int
    show_greeting: bool
    greeting_duration: float
    greeting_file: Optional[str]
    
    # Typing behavior
    typing_speed_base: float
    typing_speed_variance: float
    burst_probability: float
    burst_speed: float
    
    # Mistakes
    mistake_rate: float
    correction_pause: float
    
    # Pauses
    sentence_pause: float
    punctuation_pause: float
    space_pause: float
    newline_pause: float
    
    # Colors (RGB tuples)
    color_bg: Tuple[int, int, int]
    color_text: Tuple[int, int, int]
    color_cursor: Tuple[int, int, int]
    color_tilde: Tuple[int, int, int]
    color_status: Tuple[int, int, int]
    color_highlight: Tuple[int, int, int]
    color_command: Tuple[int, int, int]
    
    # Special effects
    highlight_patterns: List[str]
    special_sequences: dict
    
    # Runtime properties (not in config file)
    filename_in_vim: str = field(default="", init=False)
    greeting_lines: List[str] = field(default_factory=list, init=False)
    
    @classmethod
    def from_json(cls, path: str) -> 'VideoConfig':
        """Load configuration from JSON file"""
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Convert color lists to tuples
        for key in data:
            if key.startswith('color_') and isinstance(data[key], list):
                data[key] = tuple(data[key])
        
        # Create the config instance
        config = cls(**data)
        
        # Load greeting lines
        greeting_file = config.greeting_file or 'default_greeting.json'
        config_dir = os.path.dirname(path)
        greeting_path = os.path.join(config_dir, greeting_file)
        
        with open(greeting_path, 'r') as f:
            greeting_data = json.load(f)
            config.greeting_lines = greeting_data.get('lines', [])
        
        return config
    
    def to_json(self, path: str) -> None:
        """Save configuration to JSON file"""
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)


class VimVideoGenerator:
    """Generate realistic VIM typing videos"""
    
    def __init__(self, config: VideoConfig):
        self.config = config
        self.lines = [""]
        self.cursor_row = 0
        self.cursor_col = 0
        self.mode = "NORMAL"
        self.command_buffer = ""
        self.scroll_offset = 0
        self.video_writer = None
        
        # Load font
        self.font = self._load_font()
        self.char_width, self.char_height = self._calculate_char_size()
        
        # Auto-adjust width based on columns to ensure text fits
        required_width = (self.config.columns * self.char_width) + 100  # 100px for margins
        if self.config.width < required_width:
            print(f"📐 Auto-adjusting width from {self.config.width} to {required_width} to fit {self.config.columns} columns")
            self.config.width = required_width
        
    def _load_font(self) -> ImageFont.FreeTypeFont:
        """Load the best available monospace font"""
        if self.config.font_path and Path(self.config.font_path).exists():
            return ImageFont.truetype(self.config.font_path, self.config.font_size)
        
        # Try common font paths
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/System/Library/Fonts/Monaco.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "C:\\Windows\\Fonts\\consola.ttf",
            "/usr/share/fonts/truetype/ubuntu/UbuntuMono-B.ttf",
        ]
        
        for path in font_paths:
            try:
                return ImageFont.truetype(path, self.config.font_size)
            except:
                continue
        
        # Fallback to default
        return ImageFont.load_default()
    
    def _calculate_char_size(self) -> Tuple[int, int]:
        """Calculate character dimensions"""
        bbox = self.font.getbbox("M")
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    def generate(self, text_file: str, output_file: str) -> None:
        """Generate video from text file"""
        # Read input text
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Initialize video writer
        self._init_video(output_file)
        
        try:
            # Generate the video
            self._simulate_typing(text)
            
        finally:
            # Always close the video writer first
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
        
        # Now compress after video is properly closed
        raw_size = os.path.getsize(output_file) / (1024 * 1024)
        print(f"✅ Raw video saved: {output_file} ({raw_size:.2f} MB)")
        
        # Compress with ffmpeg if available
        self._compress_video(output_file)
    
    def _init_video(self, output_file: str) -> None:
        """Initialize video writer with MP4/H.264 and 2 Mbps bitrate"""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        self.video_writer = cv2.VideoWriter(
            output_file, fourcc, self.config.fps,
            (self.config.width, self.config.height)
        )
        
        # Set 2 Mbps bitrate if possible
        try:
            self.video_writer.set(cv2.CAP_PROP_BITRATE, 2000000)  # 2 Mbps
        except:
            pass  # Some OpenCV builds don't support this
        
        if not self.video_writer.isOpened():
            raise RuntimeError("Failed to initialize video writer")
            
    def _compress_video(self, output_file: str) -> None:
        """Compress video using ffmpeg if available"""
        import subprocess
        import shutil
        
        # Check if ffmpeg is available
        if not shutil.which('ffmpeg'):
            final_size = os.path.getsize(output_file) / (1024 * 1024)
            print(f"💡 Install ffmpeg for smaller file sizes. Current: {final_size:.2f} MB")
            return
        
        try:
            temp_file = output_file.replace('.mp4', '_temp.mp4')
            
            # Compress with ffmpeg - good quality at 2 Mbps
            cmd = [
                'ffmpeg', '-i', output_file,
                '-c:v', 'libx264', '-b:v', '2M', '-maxrate', '2M', '-bufsize', '4M',
                '-preset', 'medium', '-crf', '23',
                '-movflags', '+faststart',
                '-y', temp_file
            ]
            
            print("🗜️  Re-compressing video with ffmpeg...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(temp_file):
                # Replace original with compressed version
                os.replace(temp_file, output_file)
                
                final_size = os.path.getsize(output_file) / (1024 * 1024)
                print(f"✅ Compressed video: {output_file} ({final_size:.2f} MB)")
            else:
                # Compression failed, clean up temp file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                final_size = os.path.getsize(output_file) / (1024 * 1024)
                print(f"❌ Compression failed (return code: {result.returncode}). Keeping original: {final_size:.2f} MB")
                print("🔍 Full ffmpeg output:")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                
        except Exception as e:
            final_size = os.path.getsize(output_file) / (1024 * 1024)
            print(f"❌ Compression error: {e}. Current: {final_size:.2f} MB")
    
    def _simulate_typing(self, text: str) -> None:
        """Simulate VIM typing with the text"""
        # Show VIM greeting
        if self.config.show_greeting:
            self._add_frame(self.config.greeting_duration)
        
        # Open file
        self.command_buffer = f":e {self.config.filename_in_vim}"
        self._add_frame(0.4)
        self.command_buffer = ""
        self._add_frame(0.2)
        
        # Enter insert mode
        self.command_buffer = "i"
        self._add_frame(0.3)
        self.command_buffer = ""
        self.mode = "INSERT"
        self._add_frame(0.2)
        
        # Type the text
        self._type_text(text)
        
        # Exit and save
        self.mode = "NORMAL"
        self._add_frame(1.0)
        
        self.command_buffer = ":w"
        self._add_frame(0.6)
        self.command_buffer = f'"{self.config.filename_in_vim}" written'
        self._add_frame(2.0)
    
    def _type_text(self, text: str) -> None:
        """Type text with realistic behavior"""
        lines = text.split('\n')
        total_chars = sum(len(line) for line in lines)
        chars_typed = 0
        
        print(f"⌨️  Typing {total_chars} characters...")
        
        for line_idx, line in enumerate(lines):
            char_idx = 0
            
            while char_idx < len(line):
                # Check for special sequences
                special_handled = False
                for pattern, sequence in self.config.special_sequences.items():
                    if line[char_idx:].startswith(pattern):
                        # Handle both tuple and list formats
                        if isinstance(sequence, (list, tuple)) and len(sequence) == 2:
                            typo, correct = sequence[0], sequence[1]
                        else:
                            # If it's just a string, use the pattern as the correct version
                            typo, correct = sequence, pattern
                        self._type_special_sequence(typo, correct)
                        char_idx += len(pattern)
                        special_handled = True
                        break
                
                if special_handled:
                    continue
                
                # Type regular character
                char = line[char_idx]
                self._type_character(char)
                
                # Calculate pause duration
                pause = self._calculate_pause(char)
                self._add_frame(pause)
                
                # Random mistake
                if random.random() < self.config.mistake_rate and char_idx > 5:
                    self._make_mistake()
                
                char_idx += 1
                chars_typed += 1
                
                # Show progress every 50 characters
                if chars_typed % 50 == 0:
                    progress = (chars_typed / total_chars) * 100
                    print(f"\r   Progress: {progress:.1f}% ({chars_typed}/{total_chars})", end="", flush=True)
            
            # Add newline
            if line_idx < len(lines) - 1:
                self._type_character('\n')
                self._add_frame(self.config.newline_pause)
        
        # Final progress
        print(f"\r   Progress: 100.0% ({total_chars}/{total_chars}) ✅", flush=True)
    
    def _type_special_sequence(self, typo: str, correct: str) -> None:
        """Type a special sequence with correction"""
        # Type the typo
        for char in typo:
            self._type_character(char)
            self._add_frame(self.config.typing_speed_base)
        
        # Pause (realizing mistake)
        self._add_frame(self.config.correction_pause)
        
        # Backspace the difference
        for _ in range(len(typo) - len(os.path.commonprefix([typo, correct]))):
            self._backspace()
            self._add_frame(0.06)
        
        # Type the correction
        suffix = correct[len(os.path.commonprefix([typo, correct])):]
        for char in suffix:
            self._type_character(char)
            self._add_frame(self.config.typing_speed_base)
    
    def _make_mistake(self) -> None:
        """Make and correct a typing mistake"""
        wrong_char = random.choice('qwertyuiop')
        self._type_character(wrong_char)
        self._add_frame(0.15)
        
        self._add_frame(self.config.correction_pause)
        
        self._backspace()
        self._add_frame(0.1)
    
    def _calculate_pause(self, char: str) -> float:
        """Calculate pause duration after a character"""
        if char in '.!?':
            return self.config.sentence_pause
        elif char in ',;:':
            return self.config.punctuation_pause
        elif char == ' ':
            return self.config.space_pause
        else:
            # Variable typing speed
            if random.random() < self.config.burst_probability:
                return self.config.burst_speed
            else:
                base = self.config.typing_speed_base
                variance = base * self.config.typing_speed_variance
                return base + random.uniform(-variance, variance)
    
    def _type_character(self, char: str) -> None:
        """Add a character at cursor position"""
        if self.cursor_row >= len(self.lines):
            self.lines.append("")
        
        line = self.lines[self.cursor_row]
        
        if char == '\n':
            rest = line[self.cursor_col:]
            self.lines[self.cursor_row] = line[:self.cursor_col]
            self.cursor_row += 1
            self.lines.insert(self.cursor_row, rest)
            self.cursor_col = 0
        else:
            self.lines[self.cursor_row] = line[:self.cursor_col] + char + line[self.cursor_col:]
            self.cursor_col += 1
    
    def _backspace(self) -> None:
        """Delete character before cursor"""
        if self.cursor_col > 0:
            line = self.lines[self.cursor_row]
            self.lines[self.cursor_row] = line[:self.cursor_col - 1] + line[self.cursor_col:]
            self.cursor_col -= 1
        elif self.cursor_row > 0:
            prev_line = self.lines[self.cursor_row - 1]
            current_line = self.lines[self.cursor_row]
            self.cursor_col = len(prev_line)
            self.lines[self.cursor_row - 1] = prev_line + current_line
            del self.lines[self.cursor_row]
            self.cursor_row -= 1
    
    def _add_frame(self, duration: float) -> None:
        """Add frame(s) to video for given duration"""
        frame = self._render_frame()
        num_frames = max(1, int(duration * self.config.fps))
        
        for _ in range(num_frames):
            self.video_writer.write(frame)
    
    def _render_frame(self) -> np.ndarray:
        """Render current VIM state as frame"""
        # Create image
        img = Image.new('RGB', (self.config.width, self.config.height), self.config.color_bg)
        draw = ImageDraw.Draw(img)
        
        # Show greeting or content
        if len(self.lines) == 1 and self.lines[0] == "" and self.mode == "NORMAL":
            self._draw_greeting(draw)
        else:
            self._draw_content(draw)
        
        # Draw status line
        self._draw_status(draw)
        
        # Draw command line
        if self.command_buffer:
            draw.text((25, self.config.height - 20), self.command_buffer,
                     fill=self.config.color_command, font=self.font)
        
        # Convert to OpenCV format
        frame_array = np.array(img)
        return cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR)
    
    def _draw_greeting(self, draw: ImageDraw.Draw) -> None:
        """Draw VIM greeting screen"""
        welcome_lines = self.config.greeting_lines
        
        visible_rows = (self.config.height - 100) // (self.char_height + 4)
        start_row = (visible_rows - len(welcome_lines)) // 2
        y_pos = 30 + start_row * (self.char_height + 4)
        
        for line in welcome_lines:
            if line:
                line_width = len(line) * self.char_width
                x_center = (self.config.width - line_width) // 2
                draw.text((x_center, y_pos), line, fill=self.config.color_text, font=self.font)
            
            draw.text((25, y_pos), "~", fill=self.config.color_tilde, font=self.font)
            y_pos += self.char_height + 4
    
    def _wrap_line(self, text: str, width: int) -> list:
        """Wrap a line of text to fit within the specified width"""
        if len(text) <= width:
            return [text]
        
        wrapped = []
        words = text.split(' ')
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
            else:
                if current_line:
                    wrapped.append(current_line)
                if len(word) > width:
                    # Word is too long, split it
                    while len(word) > width:
                        wrapped.append(word[:width])
                        word = word[width:]
                    current_line = word
                else:
                    current_line = word
        
        if current_line:
            wrapped.append(current_line)
        
        return wrapped if wrapped else [""]

    def _draw_content(self, draw: ImageDraw.Draw) -> None:
        """Draw file content with cursor and proper line wrapping"""
        # Process all lines with wrapping
        display_lines = []
        cursor_display_row = 0
        cursor_display_col = self.cursor_col
        
        for i, line in enumerate(self.lines):
            # Don't wrap if line is empty or short enough
            if len(line) <= self.config.columns - 1:
                if i == self.cursor_row:
                    cursor_display_row = len(display_lines)
                    cursor_display_col = self.cursor_col
                display_lines.append(line)
            else:
                # Line needs wrapping
                wrapped = self._wrap_line(line, self.config.columns - 1)
                if i == self.cursor_row:
                    # Find which wrapped line the cursor is on
                    char_count = 0
                    for j, wrapped_line in enumerate(wrapped):
                        if char_count + len(wrapped_line) >= self.cursor_col:
                            cursor_display_row = len(display_lines) + j
                            cursor_display_col = self.cursor_col - char_count
                            break
                        char_count += len(wrapped_line) + 1  # +1 for the space between wrapped words
                    else:
                        # Cursor is at the end
                        cursor_display_row = len(display_lines) + len(wrapped) - 1
                        cursor_display_col = len(wrapped[-1])
                display_lines.extend(wrapped)
        
        # Calculate visible area
        visible_rows = (self.config.height - 100) // (self.char_height + 4)
        
        # Auto-scroll when cursor goes below visible area
        if cursor_display_row >= self.scroll_offset + visible_rows:
            self.scroll_offset = cursor_display_row - visible_rows + 1
        elif cursor_display_row < self.scroll_offset:
            self.scroll_offset = cursor_display_row
        
        # Draw wrapped display lines
        y_pos = 30
        for screen_row in range(visible_rows):
            display_idx = screen_row + self.scroll_offset
            
            if display_idx < len(display_lines):
                line = display_lines[display_idx]
                # Check if cursor is on this display line
                if self.mode == "INSERT" and display_idx == cursor_display_row:
                    self._draw_line_with_cursor(draw, line, cursor_display_col, y_pos)
                else:
                    self._draw_line_plain(draw, line, y_pos)
            else:
                draw.text((25, y_pos), "~", fill=self.config.color_tilde, font=self.font)
            
            y_pos += self.char_height + 4
    
    def _draw_line_with_cursor(self, draw: ImageDraw.Draw, line: str, cursor_col: int, y_pos: int) -> None:
        """Draw a line with cursor at specified position"""
        x_pos = 25
        
        for col, char in enumerate(line):
            if col == cursor_col:
                # Draw cursor
                cursor_rect = [x_pos, y_pos - 2, x_pos + self.char_width + 2, y_pos + self.char_height + 2]
                draw.rectangle(cursor_rect, fill=self.config.color_cursor)
                draw.text((x_pos + 1, y_pos), char, fill=self.config.color_bg, font=self.font)
            else:
                color = self._get_char_color(line, col)
                draw.text((x_pos, y_pos), char, fill=color, font=self.font)
            x_pos += self.char_width
        
        # Cursor at end of line
        if cursor_col >= len(line):
            cursor_rect = [x_pos, y_pos - 2, x_pos + self.char_width + 2, y_pos + self.char_height + 2]
            draw.rectangle(cursor_rect, fill=self.config.color_cursor)
    
    def _draw_line_plain(self, draw: ImageDraw.Draw, line: str, y_pos: int) -> None:
        """Draw a regular line without cursor"""
        x_pos = 25
        
        for col, char in enumerate(line):
            color = self._get_char_color(line, col)
            draw.text((x_pos, y_pos), char, fill=color, font=self.font)
            x_pos += self.char_width
    
    def _get_char_color(self, line: str, col: int) -> Tuple[int, int, int]:
        """Get color for character based on highlighting rules"""
        for pattern in self.config.highlight_patterns:
            if pattern in line:
                start = line.find(pattern)
                if start <= col < start + len(pattern):
                    return self.config.color_highlight
        return self.config.color_text
    
    def _draw_status(self, draw: ImageDraw.Draw) -> None:
        """Draw VIM status line"""
        status_y = self.config.height - 60
        draw.rectangle([0, status_y, self.config.width, status_y + self.char_height + 12],
                      fill=self.config.color_status)
        
        status_text = f" {self.config.filename_in_vim} "
        if self.mode == "INSERT":
            status_text += "-- INSERT --"
        status_text += f"  {self.cursor_row + 1},{self.cursor_col + 1}"
        
        draw.text((25, status_y + 6), status_text, fill=self.config.color_text, font=self.font)


def display_config_parameters(config: VideoConfig, config_file: str) -> None:
    """Display all loaded configuration parameters"""
    print(f"📋 Configuration loaded from: {config_file}")
    print("=" * 50)
    
    # Group parameters by category for better readability
    categories = {
        'Video Settings': [
            ('width', config.width),
            ('height', config.height), 
            ('fps', config.fps),
            ('font_size', config.font_size),
            ('font_path', config.font_path),
        ],
        'VIM Display': [
            ('columns', config.columns),
            ('rows', config.rows),
            ('show_greeting', config.show_greeting),
            ('greeting_duration', config.greeting_duration),
            ('greeting_file', config.greeting_file),
        ],
        'Typing Behavior': [
            ('typing_speed_base', config.typing_speed_base),
            ('typing_speed_variance', config.typing_speed_variance),
            ('burst_probability', config.burst_probability),
            ('burst_speed', config.burst_speed),
        ],
        'Mistakes & Corrections': [
            ('mistake_rate', config.mistake_rate),
            ('correction_pause', config.correction_pause),
        ],
        'Timing Pauses': [
            ('sentence_pause', config.sentence_pause),
            ('punctuation_pause', config.punctuation_pause),
            ('space_pause', config.space_pause),
            ('newline_pause', config.newline_pause),
        ],
        'Colors (RGB)': [
            ('color_bg', config.color_bg),
            ('color_text', config.color_text),
            ('color_cursor', config.color_cursor),
            ('color_tilde', config.color_tilde),
            ('color_status', config.color_status),
            ('color_highlight', config.color_highlight),
            ('color_command', config.color_command),
        ],
        'Special Effects': [
            ('highlight_patterns', config.highlight_patterns),
            ('special_sequences', config.special_sequences),
        ],
        'Greeting Lines': [
            ('greeting_lines', f"{len(config.greeting_lines)} lines loaded"),
        ]
    }
    
    for category, params in categories.items():
        print(f"\n{category}:")
        for name, value in params:
            if name == 'greeting_lines':
                print(f"  {name}: {value}")
                for i, line in enumerate(config.greeting_lines[:3]):  # Show first 3 lines
                    print(f"    [{i}] \"{line}\"")
                if len(config.greeting_lines) > 3:
                    print(f"    ... and {len(config.greeting_lines) - 3} more lines")
            else:
                print(f"  {name}: {value}")
    
    print("=" * 50)
    print()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate realistic VIM typing videos from text files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (uses default.json)
  %(prog)s input.txt output.mp4
  
  # With custom configuration
  %(prog)s input.txt output.mp4 --config my_config.json
        """
    )
    
    # Positional arguments
    parser.add_argument('input', help='Input text file')
    parser.add_argument('output', help='Output video file')
    
    # Configuration
    parser.add_argument('--config', help='Configuration file (default: default.json)')
    
    args = parser.parse_args()
    
    # Validate input file
    if not Path(args.input).exists():
        parser.error(f"Input file not found: {args.input}")
    
    # Load configuration
    config_file = args.config if args.config else 'default.json'
    
    # Check if config file exists
    if not Path(config_file).exists():
        # If default.json doesn't exist in current dir, try to find it next to the script
        script_dir = Path(__file__).parent
        default_config = script_dir / 'default.json'
        if default_config.exists():
            config_file = str(default_config)
        else:
            print(f"❌ Configuration file not found: {config_file}", file=sys.stderr)
            print("Please create a default.json or specify a config file with --config", file=sys.stderr)
            sys.exit(1)
    
    try:
        config = VideoConfig.from_json(config_file)
    except Exception as e:
        print(f"❌ Error loading config from {config_file}: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Set filename in VIM from input file
    config.filename_in_vim = Path(args.input).name
    
    # Display all loaded configuration parameters
    display_config_parameters(config, config_file)
    
    # Generate video
    print(f"🎬 Generating video from {args.input}")
    print(f"📐 Resolution: {config.width}x{config.height} @ {config.fps}fps")
    print(f"🔤 Font size: {config.font_size}px")
    
    try:
        generator = VimVideoGenerator(config)
        generator.generate(args.input, args.output)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()