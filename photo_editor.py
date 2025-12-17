#!/usr/bin/env python3
"""
Photo Editor for Scanned Film Photos

A simple GUI tool for reviewing and correcting scanned photos:
- Mirror/rotate images to fix scanning errors
- Crop edges by dragging handles inward (for removing white bars from scans)
- Add date metadata to EXIF
- Quick date selection from recently used dates

Keyboard shortcuts:
    M           - Mirror image horizontally
    R           - Rotate 90° clockwise
    Shift+R     - Rotate 90° counter-clockwise
    D           - Enter new date
    1-9         - Quick select from recent dates
    C           - Reset crop (remove all crop adjustments)
    Right/N     - Next image
    Left/P      - Previous image
    S           - Save current image
    U           - Undo all changes to current image
    Q/Escape    - Quit

Crop feature:
    - Drag the blue handles on any edge inward to crop
    - Cropped areas appear darkened with red boundary lines
    - Crop is applied when saving the image
    - Press C to reset crop, or U to undo all changes
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk, ImageOps
import piexif
from datetime import datetime
import sys
import re


class PhotoEditor:
    def __init__(self, folder_path: str):
        self.folder = Path(folder_path)
        self.images = sorted([
            f for f in self.folder.iterdir()
            if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
        ])

        if not self.images:
            print(f"No images found in {folder_path}")
            sys.exit(1)

        self.current_index = 0
        self.current_image: Image.Image | None = None
        self.original_image: Image.Image | None = None
        self.current_date: str | None = None
        self.original_date: str | None = None  # Date from file's EXIF
        self.has_changes = False

        # Crop state: offsets in image pixels from each edge
        self.crop_left = 0
        self.crop_top = 0
        self.crop_right = 0
        self.crop_bottom = 0

        # Crop interaction state
        self.dragging_edge: str | None = None  # 'left', 'right', 'top', 'bottom', or None
        self.drag_start_pos = 0
        self.drag_start_crop = 0
        self.display_scale = 1.0  # Scale factor from image to display
        self.image_display_x = 0  # Top-left corner of displayed image
        self.image_display_y = 0
        self.display_width = 0
        self.display_height = 0

        # Track recent dates for quick selection (folder-specific)
        self.recent_dates: list[str] = []

        # Set up the GUI
        self.root = tk.Tk()
        self.root.title("Photo Editor")
        self.root.configure(bg='#1e1e1e')

        # Make window large but not fullscreen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.window_width = int(screen_width * 0.9)
        self.window_height = int(screen_height * 0.9)
        self.root.geometry(f"{self.window_width}x{self.window_height}")

        # Create main frame
        self.main_frame = tk.Frame(self.root, bg='#1e1e1e')
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Status bar at top
        self.status_frame = tk.Frame(self.main_frame, bg='#2d2d2d', height=60)
        self.status_frame.pack(fill=tk.X, side=tk.TOP)
        self.status_frame.pack_propagate(False)

        self.filename_label = tk.Label(
            self.status_frame,
            text="",
            font=('Consolas', 14, 'bold'),
            bg='#2d2d2d',
            fg='white'
        )
        self.filename_label.pack(side=tk.LEFT, padx=20, pady=15)

        self.counter_label = tk.Label(
            self.status_frame,
            text="",
            font=('Consolas', 12),
            bg='#2d2d2d',
            fg='#888888'
        )
        self.counter_label.pack(side=tk.LEFT, padx=10, pady=15)

        self.date_label = tk.Label(
            self.status_frame,
            text="",
            font=('Consolas', 12),
            bg='#2d2d2d',
            fg='#4fc3f7'
        )
        self.date_label.pack(side=tk.RIGHT, padx=20, pady=15)

        self.modified_label = tk.Label(
            self.status_frame,
            text="",
            font=('Consolas', 12, 'bold'),
            bg='#2d2d2d',
            fg='#ff9800'
        )
        self.modified_label.pack(side=tk.RIGHT, padx=10, pady=15)

        # Content area (canvas + right panel)
        self.content_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # Image canvas
        self.canvas = tk.Canvas(self.content_frame, bg='#1e1e1e', highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind mouse events for crop dragging
        self.canvas.bind('<Motion>', self.on_mouse_move)
        self.canvas.bind('<Button-1>', self.on_mouse_down)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)

        # Right info panel
        self.info_panel = tk.Frame(self.content_frame, bg='#252525', width=200)
        self.info_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_panel.pack_propagate(False)

        # Date section in info panel
        tk.Label(
            self.info_panel, text="DATE", font=('Consolas', 10, 'bold'),
            bg='#252525', fg='#666666'
        ).pack(pady=(20, 5))

        self.info_date_label = tk.Label(
            self.info_panel, text="(none)", font=('Consolas', 16, 'bold'),
            bg='#252525', fg='#4fc3f7'
        )
        self.info_date_label.pack(pady=(0, 5))

        self.info_date_status = tk.Label(
            self.info_panel, text="", font=('Consolas', 9),
            bg='#252525', fg='#888888'
        )
        self.info_date_status.pack(pady=(0, 20))

        # Separator
        tk.Frame(self.info_panel, bg='#333333', height=1).pack(fill=tk.X, padx=15)

        # Image info section
        tk.Label(
            self.info_panel, text="IMAGE", font=('Consolas', 10, 'bold'),
            bg='#252525', fg='#666666'
        ).pack(pady=(20, 5))

        self.info_dimensions_label = tk.Label(
            self.info_panel, text="", font=('Consolas', 11),
            bg='#252525', fg='#aaaaaa'
        )
        self.info_dimensions_label.pack(pady=(0, 10))

        # Help bar at bottom
        self.help_frame = tk.Frame(self.main_frame, bg='#2d2d2d', height=70)
        self.help_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.help_frame.pack_propagate(False)

        # Create a container for the key groups
        help_container = tk.Frame(self.help_frame, bg='#2d2d2d')
        help_container.pack(expand=True)

        # Define key groups with colors
        key_groups = [
            ('#ff9800', [('M', 'Mirror'), ('R', 'Rotate CW'), ('Shift+R', 'Rotate CCW')]),
            ('#4fc3f7', [('D', 'Set Date'), ('1-9', 'Quick Date')]),
            ('#ff6b6b', [('Drag Edge', 'Crop'), ('C', 'Reset Crop')]),
            ('#81c784', [('←/P', 'Previous'), ('→/N', 'Next')]),
            ('#ce93d8', [('S', 'Save + Next'), ('U', 'Undo')]),
            ('#888888', [('Q/Esc', 'Quit')]),
        ]

        for color, keys in key_groups:
            group_frame = tk.Frame(help_container, bg='#2d2d2d')
            group_frame.pack(side=tk.LEFT, padx=15)
            for key, action in keys:
                key_frame = tk.Frame(group_frame, bg='#2d2d2d')
                key_frame.pack(side=tk.LEFT, padx=5)
                tk.Label(
                    key_frame, text=f"[{key}]", font=('Consolas', 10, 'bold'),
                    bg='#2d2d2d', fg=color
                ).pack(side=tk.LEFT)
                tk.Label(
                    key_frame, text=f" {action}", font=('Consolas', 10),
                    bg='#2d2d2d', fg='#cccccc'
                ).pack(side=tk.LEFT)

        # Recent dates display
        self.dates_frame = tk.Frame(self.main_frame, bg='#2d2d2d', height=30)
        self.dates_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.dates_frame.pack_propagate(False)

        self.dates_label = tk.Label(
            self.dates_frame,
            text="",
            font=('Consolas', 10),
            bg='#2d2d2d',
            fg='#4fc3f7'
        )
        self.dates_label.pack(pady=5)

        # Bind keys
        self.root.bind('<Key>', self.on_key)
        self.root.bind('<Configure>', self.on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_quit)

        # Load first image
        self.load_image()

    def load_image(self):
        """Load the current image and reset state."""
        if not self.images:
            return

        path = self.images[self.current_index]
        self.current_image = Image.open(path)
        # Apply EXIF orientation so image displays correctly
        # (scanners/cameras may store rotated images with an orientation tag)
        self.current_image = ImageOps.exif_transpose(self.current_image)
        self.original_image = self.current_image.copy()
        self.has_changes = False

        # Reset crop state
        self.crop_left = 0
        self.crop_top = 0
        self.crop_right = 0
        self.crop_bottom = 0

        # Try to read existing date from EXIF
        self.original_date = self.read_exif_date(path)
        self.current_date = self.original_date

        # Add existing EXIF date to recent dates for quick reuse
        if self.original_date:
            self.add_recent_date(self.original_date)

        self.update_display()

    def read_exif_date(self, path: Path) -> str | None:
        """Read DateTimeOriginal from EXIF if present."""
        try:
            exif_dict = piexif.load(str(path))
            if piexif.ExifIFD.DateTimeOriginal in exif_dict.get('Exif', {}):
                date_bytes = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal]
                date_str = date_bytes.decode('utf-8') if isinstance(date_bytes, bytes) else date_bytes
                # Convert from EXIF format (YYYY:MM:DD HH:MM:SS) to display format
                return date_str[:10].replace(':', '-')
        except Exception:
            pass
        return None

    def update_display(self):
        """Update the entire display with current state."""
        if not self.current_image:
            return

        # Update filename and counter
        path = self.images[self.current_index]
        self.filename_label.config(text=path.name)
        self.counter_label.config(text=f"({self.current_index + 1}/{len(self.images)})")

        # Update date display (status bar and info panel)
        if self.current_date:
            if self.original_date and self.current_date == self.original_date:
                # Date from EXIF, unchanged
                self.date_label.config(text=f"Date: {self.current_date} (from EXIF)", fg='#81c784')
                self.info_date_label.config(text=self.current_date, fg='#81c784')
                self.info_date_status.config(text="from EXIF")
            elif self.original_date and self.current_date != self.original_date:
                # Date changed from original EXIF
                self.date_label.config(text=f"Date: {self.current_date} (was: {self.original_date})", fg='#ffb74d')
                self.info_date_label.config(text=self.current_date, fg='#ffb74d')
                self.info_date_status.config(text=f"was: {self.original_date}")
            else:
                # New date, no original
                self.date_label.config(text=f"Date: {self.current_date} (new)", fg='#4fc3f7')
                self.info_date_label.config(text=self.current_date, fg='#4fc3f7')
                self.info_date_status.config(text="newly added")
        else:
            if self.original_date:
                # Had a date but cleared it (shouldn't normally happen)
                self.date_label.config(text=f"Date: (none, was: {self.original_date})", fg='#ff8a65')
                self.info_date_label.config(text="(none)", fg='#ff8a65')
                self.info_date_status.config(text=f"was: {self.original_date}")
            else:
                self.date_label.config(text="Date: (none)", fg='#888888')
                self.info_date_label.config(text="(none)", fg='#888888')
                self.info_date_status.config(text="no date set")

        # Update image dimensions in info panel
        if self.current_image:
            w, h = self.current_image.size
            has_crop = self.crop_left > 0 or self.crop_top > 0 or self.crop_right > 0 or self.crop_bottom > 0
            if has_crop:
                cropped_w = w - self.crop_left - self.crop_right
                cropped_h = h - self.crop_top - self.crop_bottom
                self.info_dimensions_label.config(text=f"{cropped_w} × {cropped_h}\n(was {w} × {h})", fg='#ff6b6b')
            else:
                self.info_dimensions_label.config(text=f"{w} × {h}", fg='#aaaaaa')

        # Update modified indicator
        if self.has_changes:
            self.modified_label.config(text="[MODIFIED]")
        else:
            self.modified_label.config(text="")

        # Update recent dates display
        if self.recent_dates:
            dates_text = "  ".join([f"{i+1}:{d}" for i, d in enumerate(self.recent_dates[:9])])
            self.dates_label.config(text=f"Recent dates: {dates_text}")
        else:
            self.dates_label.config(text="No recent dates (press D to add)")

        # Display the image
        self.display_image()

    def display_image(self):
        """Fit and display the current image on the canvas."""
        if not self.current_image:
            return

        self.canvas.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            # Canvas not ready yet, schedule retry
            self.root.after(100, self.display_image)
            return

        # Calculate scaling to fit image in canvas
        img_width, img_height = self.current_image.size
        scale = min(canvas_width / img_width, canvas_height / img_height, 1.0)

        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        # Store display metrics for crop interaction
        self.display_scale = scale
        self.display_width = new_width
        self.display_height = new_height
        self.image_display_x = (canvas_width - new_width) // 2
        self.image_display_y = (canvas_height - new_height) // 2

        # Resize for display (don't modify original)
        display_image = self.current_image.copy()
        display_image = display_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(display_image)

        # Center on canvas
        x = canvas_width // 2
        y = canvas_height // 2

        self.canvas.delete("all")
        self.canvas.create_image(x, y, image=self.photo, anchor=tk.CENTER)

        # Draw crop overlays and handles
        self.draw_crop_overlay()

    def on_resize(self, event):
        """Handle window resize."""
        if event.widget == self.root:
            self.display_image()

    def draw_crop_overlay(self):
        """Draw crop handles and darkened overlay areas."""
        if not self.current_image:
            return

        # Calculate crop positions in display coordinates
        left_x = self.image_display_x + int(self.crop_left * self.display_scale)
        top_y = self.image_display_y + int(self.crop_top * self.display_scale)
        right_x = self.image_display_x + self.display_width - int(self.crop_right * self.display_scale)
        bottom_y = self.image_display_y + self.display_height - int(self.crop_bottom * self.display_scale)

        img_left = self.image_display_x
        img_top = self.image_display_y
        img_right = self.image_display_x + self.display_width
        img_bottom = self.image_display_y + self.display_height

        # Only draw overlays if there's any crop
        has_crop = self.crop_left > 0 or self.crop_top > 0 or self.crop_right > 0 or self.crop_bottom > 0

        if has_crop:
            # Draw semi-transparent overlays on cropped areas
            overlay_color = '#000000'
            stipple = 'gray50'

            # Left overlay
            if self.crop_left > 0:
                self.canvas.create_rectangle(
                    img_left, img_top, left_x, img_bottom,
                    fill=overlay_color, stipple=stipple, outline=''
                )

            # Right overlay
            if self.crop_right > 0:
                self.canvas.create_rectangle(
                    right_x, img_top, img_right, img_bottom,
                    fill=overlay_color, stipple=stipple, outline=''
                )

            # Top overlay (between left and right crop lines)
            if self.crop_top > 0:
                self.canvas.create_rectangle(
                    left_x, img_top, right_x, top_y,
                    fill=overlay_color, stipple=stipple, outline=''
                )

            # Bottom overlay (between left and right crop lines)
            if self.crop_bottom > 0:
                self.canvas.create_rectangle(
                    left_x, bottom_y, right_x, img_bottom,
                    fill=overlay_color, stipple=stipple, outline=''
                )

            # Draw crop boundary lines
            line_color = '#ff6b6b'
            line_width = 2

            if self.crop_left > 0:
                self.canvas.create_line(left_x, img_top, left_x, img_bottom,
                                       fill=line_color, width=line_width)
            if self.crop_right > 0:
                self.canvas.create_line(right_x, img_top, right_x, img_bottom,
                                       fill=line_color, width=line_width)
            if self.crop_top > 0:
                self.canvas.create_line(img_left, top_y, img_right, top_y,
                                       fill=line_color, width=line_width)
            if self.crop_bottom > 0:
                self.canvas.create_line(img_left, bottom_y, img_right, bottom_y,
                                       fill=line_color, width=line_width)

        # Draw edge handles (always visible for grabbing)
        handle_color = '#4fc3f7'
        handle_length = 40
        handle_width = 4

        # Left edge handle (center of left edge)
        center_y = (img_top + img_bottom) // 2
        self.canvas.create_line(left_x, center_y - handle_length, left_x, center_y + handle_length,
                               fill=handle_color, width=handle_width, tags='handle_left')

        # Right edge handle
        self.canvas.create_line(right_x, center_y - handle_length, right_x, center_y + handle_length,
                               fill=handle_color, width=handle_width, tags='handle_right')

        # Top edge handle
        center_x = (img_left + img_right) // 2
        self.canvas.create_line(center_x - handle_length, top_y, center_x + handle_length, top_y,
                               fill=handle_color, width=handle_width, tags='handle_top')

        # Bottom edge handle
        self.canvas.create_line(center_x - handle_length, bottom_y, center_x + handle_length, bottom_y,
                               fill=handle_color, width=handle_width, tags='handle_bottom')

    def get_edge_at_position(self, x: int, y: int) -> str | None:
        """Determine which crop edge (if any) is at the given position."""
        if not self.current_image:
            return None

        # Calculate current crop positions in display coordinates
        left_x = self.image_display_x + int(self.crop_left * self.display_scale)
        top_y = self.image_display_y + int(self.crop_top * self.display_scale)
        right_x = self.image_display_x + self.display_width - int(self.crop_right * self.display_scale)
        bottom_y = self.image_display_y + self.display_height - int(self.crop_bottom * self.display_scale)

        img_top = self.image_display_y
        img_bottom = self.image_display_y + self.display_height
        img_left = self.image_display_x
        img_right = self.image_display_x + self.display_width

        edge_threshold = 15  # Pixels from edge to trigger grab

        # Check if within image vertical bounds for left/right edges
        if img_top <= y <= img_bottom:
            if abs(x - left_x) < edge_threshold:
                return 'left'
            if abs(x - right_x) < edge_threshold:
                return 'right'

        # Check if within image horizontal bounds for top/bottom edges
        if img_left <= x <= img_right:
            if abs(y - top_y) < edge_threshold:
                return 'top'
            if abs(y - bottom_y) < edge_threshold:
                return 'bottom'

        return None

    def on_mouse_move(self, event):
        """Handle mouse movement for cursor changes."""
        edge = self.get_edge_at_position(event.x, event.y)

        if edge in ('left', 'right'):
            self.canvas.config(cursor='sb_h_double_arrow')
        elif edge in ('top', 'bottom'):
            self.canvas.config(cursor='sb_v_double_arrow')
        else:
            self.canvas.config(cursor='')

    def on_mouse_down(self, event):
        """Handle mouse button press to start dragging."""
        edge = self.get_edge_at_position(event.x, event.y)

        if edge:
            self.dragging_edge = edge
            if edge in ('left', 'right'):
                self.drag_start_pos = event.x
            else:
                self.drag_start_pos = event.y

            # Store starting crop value
            if edge == 'left':
                self.drag_start_crop = self.crop_left
            elif edge == 'right':
                self.drag_start_crop = self.crop_right
            elif edge == 'top':
                self.drag_start_crop = self.crop_top
            elif edge == 'bottom':
                self.drag_start_crop = self.crop_bottom

    def on_mouse_drag(self, event):
        """Handle mouse drag to adjust crop."""
        if not self.dragging_edge or not self.current_image:
            return

        img_width, img_height = self.current_image.size

        if self.dragging_edge in ('left', 'right'):
            delta_display = event.x - self.drag_start_pos
            delta_image = int(delta_display / self.display_scale)

            if self.dragging_edge == 'left':
                # Dragging left edge: moving right increases crop
                new_crop = self.drag_start_crop + delta_image
                # Clamp to valid range (0 to image_width - right_crop - min_size)
                min_remaining = 50  # Minimum image size to keep
                max_crop = img_width - self.crop_right - min_remaining
                self.crop_left = max(0, min(new_crop, max_crop))
            else:  # right
                # Dragging right edge: moving left increases crop
                new_crop = self.drag_start_crop - delta_image
                max_crop = img_width - self.crop_left - 50
                self.crop_right = max(0, min(new_crop, max_crop))
        else:
            delta_display = event.y - self.drag_start_pos
            delta_image = int(delta_display / self.display_scale)

            if self.dragging_edge == 'top':
                # Dragging top edge: moving down increases crop
                new_crop = self.drag_start_crop + delta_image
                max_crop = img_height - self.crop_bottom - 50
                self.crop_top = max(0, min(new_crop, max_crop))
            else:  # bottom
                # Dragging bottom edge: moving up increases crop
                new_crop = self.drag_start_crop - delta_image
                max_crop = img_height - self.crop_top - 50
                self.crop_bottom = max(0, min(new_crop, max_crop))

        # Mark as changed if any crop is active
        if self.crop_left > 0 or self.crop_top > 0 or self.crop_right > 0 or self.crop_bottom > 0:
            self.has_changes = True

        self.update_display()

    def on_mouse_up(self, event):
        """Handle mouse button release to stop dragging."""
        self.dragging_edge = None
        self.canvas.config(cursor='')

    def on_key(self, event):
        """Handle keyboard input."""
        key = event.keysym.lower()

        if key == 'm':
            self.mirror_image()
        elif key == 'r':
            if event.state & 0x1:  # Shift held
                self.rotate_image(counterclockwise=True)
            else:
                self.rotate_image(counterclockwise=False)
        elif key == 'd':
            self.enter_date()
        elif key in '123456789':
            self.quick_select_date(int(key))
        elif key in ('right', 'n'):
            self.next_image()
        elif key in ('left', 'p'):
            self.prev_image()
        elif key == 's':
            self.save_image()
        elif key == 'u':
            self.undo_changes()
        elif key == 'c':
            self.reset_crop()
        elif key in ('q', 'escape'):
            self.on_quit()

    def mirror_image(self):
        """Mirror the image horizontally."""
        if self.current_image:
            self.current_image = self.current_image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            self.has_changes = True
            self.update_display()

    def rotate_image(self, counterclockwise: bool = False):
        """Rotate the image 90 degrees."""
        if self.current_image:
            if counterclockwise:
                self.current_image = self.current_image.transpose(Image.Transpose.ROTATE_90)
            else:
                self.current_image = self.current_image.transpose(Image.Transpose.ROTATE_270)
            self.has_changes = True
            self.update_display()

    def enter_date(self):
        """Prompt user to enter a date."""
        current = self.current_date or ""
        date_str = simpledialog.askstring(
            "Enter Date",
            "Enter date (YYYY-MM-DD or MM-DD-YYYY or any format):",
            initialvalue=current,
            parent=self.root
        )

        if date_str:
            normalized = self.normalize_date(date_str)
            if normalized:
                self.current_date = normalized
                self.has_changes = True
                self.add_recent_date(normalized)
                self.update_display()
            else:
                messagebox.showerror("Invalid Date", f"Could not parse date: {date_str}")

    def normalize_date(self, date_str: str) -> str | None:
        """Try to parse various date formats and return YYYY-MM-DD."""
        date_str = date_str.strip()

        # Common formats to try
        formats = [
            '%Y-%m-%d',      # 2024-01-15
            '%Y/%m/%d',      # 2024/01/15
            '%m-%d-%Y',      # 01-15-2024
            '%m/%d/%Y',      # 01/15/2024
            '%d-%m-%Y',      # 15-01-2024
            '%d/%m/%Y',      # 15/01/2024
            '%Y%m%d',        # 20240115
            '%m%d%Y',        # 01152024
            '%B %d, %Y',     # January 15, 2024
            '%b %d, %Y',     # Jan 15, 2024
            '%d %B %Y',      # 15 January 2024
            '%d %b %Y',      # 15 Jan 2024
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        # Try extracting numbers if nothing else works
        numbers = re.findall(r'\d+', date_str)
        if len(numbers) == 3:
            # Guess format based on values
            a, b, c = map(int, numbers)
            if a > 31:  # Likely YYYY-MM-DD (4-digit year first)
                return f"{a:04d}-{b:02d}-{c:02d}"
            elif c >= 100:  # Likely MM-DD-YYYY or DD-MM-YYYY (4-digit year)
                if a > 12:  # DD-MM-YYYY
                    return f"{c:04d}-{b:02d}-{a:02d}"
                else:  # MM-DD-YYYY (assume US format)
                    return f"{c:04d}-{a:02d}-{b:02d}"
            else:  # 2-digit year (c < 100, like 96 or 01)
                # Assume MM-DD-YY format
                year = 1900 + c if c > 50 else 2000 + c
                return f"{year:04d}-{a:02d}-{b:02d}"

        # Handle compact formats with 2-digit year: mmddyy, mdyy, mddyy, etc.
        digits_only = re.sub(r'\D', '', date_str)
        if 4 <= len(digits_only) <= 6:
            # Last 2 digits are year
            yy = int(digits_only[-2:])
            year = 1900 + yy if yy > 50 else 2000 + yy
            rest = digits_only[:-2]  # mm/dd part

            if len(rest) == 4:  # mmdd
                mm, dd = int(rest[:2]), int(rest[2:])
            elif len(rest) == 3:  # mdd or mmd - assume m/dd
                mm, dd = int(rest[0]), int(rest[1:])
            elif len(rest) == 2:  # md
                mm, dd = int(rest[0]), int(rest[1])
            else:
                return None

            if 1 <= mm <= 12 and 1 <= dd <= 31:
                return f"{year:04d}-{mm:02d}-{dd:02d}"

        return None

    def add_recent_date(self, date_str: str):
        """Add a date to the recent dates list."""
        if date_str in self.recent_dates:
            self.recent_dates.remove(date_str)
        self.recent_dates.insert(0, date_str)
        self.recent_dates = self.recent_dates[:9]  # Keep only 9 most recent

    def quick_select_date(self, num: int):
        """Select a date from the recent dates list."""
        idx = num - 1
        if idx < len(self.recent_dates):
            self.current_date = self.recent_dates[idx]
            self.has_changes = True
            self.add_recent_date(self.current_date)  # Move to top
            self.update_display()

    def generate_new_filename(self, original_path: Path) -> Path:
        """Generate a new filename based on date and folder name.

        If date exists: "YYYY-MM-DD (folder_name) 1.ext", "YYYY-MM-DD (folder_name) 2.ext", etc.
        If no date: "folder_name 1.ext", "folder_name 2.ext", etc.
        """
        folder_name = self.folder.name
        extension = original_path.suffix.lower()

        if self.current_date:
            # Format: "YYYY-MM-DD (folder_name) N.ext"
            # Find the highest existing number for this date pattern
            pattern = re.compile(
                rf'^{re.escape(self.current_date)}\s+\({re.escape(folder_name)}\)\s+(\d+){re.escape(extension)}$',
                re.IGNORECASE
            )

            existing_numbers = []
            for f in self.folder.iterdir():
                if f.is_file():
                    match = pattern.match(f.name)
                    if match and f != original_path:
                        existing_numbers.append(int(match.group(1)))

            # Start at 1 if no existing files, otherwise use next available
            next_num = max(existing_numbers, default=0) + 1
            new_path = self.folder / f"{self.current_date} ({folder_name}) {next_num}{extension}"

            # Make sure we don't collide with an existing file
            while new_path.exists() and new_path != original_path:
                next_num += 1
                new_path = self.folder / f"{self.current_date} ({folder_name}) {next_num}{extension}"
        else:
            # No date - use "folder_name N.ext" format
            # Find the highest existing number for this pattern
            pattern = re.compile(rf'^{re.escape(folder_name)}\s+(\d+){re.escape(extension)}$', re.IGNORECASE)

            existing_numbers = []
            for f in self.folder.iterdir():
                if f.is_file():
                    match = pattern.match(f.name)
                    if match:
                        existing_numbers.append(int(match.group(1)))

            # Start at 1 if no existing files, otherwise use next available
            next_num = max(existing_numbers, default=0) + 1
            new_path = self.folder / f"{folder_name} {next_num}{extension}"

            # Make sure we don't collide with an existing file
            while new_path.exists() and new_path != original_path:
                next_num += 1
                new_path = self.folder / f"{folder_name} {next_num}{extension}"

        return new_path

    def save_image(self):
        """Save the current image with modifications and EXIF date."""
        path = self.images[self.current_index]
        new_path = self.generate_new_filename(path)
        needs_rename = new_path != path

        if not self.has_changes and not needs_rename:
            messagebox.showinfo("No Changes", "No changes to save.")
            return

        try:
            # Apply crop if any
            image_to_save = self.current_image
            if self.crop_left > 0 or self.crop_top > 0 or self.crop_right > 0 or self.crop_bottom > 0:
                img_width, img_height = self.current_image.size
                left = self.crop_left
                top = self.crop_top
                right = img_width - self.crop_right
                bottom = img_height - self.crop_bottom
                image_to_save = self.current_image.crop((left, top, right, bottom))

            # Prepare EXIF data
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

            # Try to preserve existing EXIF
            try:
                existing_exif = piexif.load(str(path))
                exif_dict.update(existing_exif)
            except Exception:
                pass

            # Clear orientation tag - we've already applied it to the pixel data
            # Setting to 1 means "normal" (no rotation needed)
            if '0th' not in exif_dict:
                exif_dict['0th'] = {}
            exif_dict['0th'][piexif.ImageIFD.Orientation] = 1

            # Set date if we have one
            if self.current_date:
                # EXIF format: YYYY:MM:DD HH:MM:SS
                exif_date = self.current_date.replace('-', ':') + " 12:00:00"
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = exif_date.encode('utf-8')
                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = exif_date.encode('utf-8')
                exif_dict['0th'][piexif.ImageIFD.DateTime] = exif_date.encode('utf-8')

            # Remove thumbnail to avoid issues
            exif_dict['thumbnail'] = None
            exif_dict['1st'] = {}

            exif_bytes = piexif.dump(exif_dict)

            # Save with EXIF to new path
            image_to_save.save(str(new_path), "JPEG", exif=exif_bytes, quality=95)

            # Delete the original file if we renamed it
            if needs_rename and path.exists():
                path.unlink()
                # Update the images list with the new path
                self.images[self.current_index] = new_path

            self.original_image = self.current_image.copy()
            self.has_changes = False

            # Advance to next image if available, otherwise show saved feedback
            if self.current_index < len(self.images) - 1:
                self.current_index += 1
                self.load_image()
            else:
                self.update_display()
                self.modified_label.config(text="[SAVED - LAST IMAGE]", fg='#4caf50')
                self.root.after(1500, lambda: self.modified_label.config(text="", fg='#ff9800'))

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")

    def undo_changes(self):
        """Revert to the original loaded image."""
        if self.original_image:
            self.current_image = self.original_image.copy()
            self.current_date = self.original_date
            self.crop_left = 0
            self.crop_top = 0
            self.crop_right = 0
            self.crop_bottom = 0
            self.has_changes = False
            self.update_display()

    def reset_crop(self):
        """Reset crop to no crop (show full image)."""
        if self.crop_left > 0 or self.crop_top > 0 or self.crop_right > 0 or self.crop_bottom > 0:
            self.crop_left = 0
            self.crop_top = 0
            self.crop_right = 0
            self.crop_bottom = 0
            # Note: has_changes may already be True from other edits, don't change it
            self.update_display()

    def save_current_without_advancing(self):
        """Save the current image without advancing to next."""
        path = self.images[self.current_index]
        new_path = self.generate_new_filename(path)
        needs_rename = new_path != path

        if not self.has_changes and not needs_rename:
            return

        try:
            # Apply crop if any
            image_to_save = self.current_image
            if self.crop_left > 0 or self.crop_top > 0 or self.crop_right > 0 or self.crop_bottom > 0:
                img_width, img_height = self.current_image.size
                left = self.crop_left
                top = self.crop_top
                right = img_width - self.crop_right
                bottom = img_height - self.crop_bottom
                image_to_save = self.current_image.crop((left, top, right, bottom))

            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

            try:
                existing_exif = piexif.load(str(path))
                exif_dict.update(existing_exif)
            except Exception:
                pass

            if '0th' not in exif_dict:
                exif_dict['0th'] = {}
            exif_dict['0th'][piexif.ImageIFD.Orientation] = 1

            if self.current_date:
                exif_date = self.current_date.replace('-', ':') + " 12:00:00"
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = exif_date.encode('utf-8')
                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = exif_date.encode('utf-8')
                exif_dict['0th'][piexif.ImageIFD.DateTime] = exif_date.encode('utf-8')

            exif_dict['thumbnail'] = None
            exif_dict['1st'] = {}

            exif_bytes = piexif.dump(exif_dict)

            # Save with EXIF to new path
            image_to_save.save(str(new_path), "JPEG", exif=exif_bytes, quality=95)

            # Delete the original file if we renamed it
            if needs_rename and path.exists():
                path.unlink()
                # Update the images list with the new path
                self.images[self.current_index] = new_path

            self.original_image = self.current_image.copy()
            self.original_date = self.current_date
            self.has_changes = False

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")

    def next_image(self):
        """Move to the next image, auto-saving any changes."""
        if self.has_changes:
            self.save_image()
            return  # save_image already advances to next

        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self.load_image()

    def prev_image(self):
        """Move to the previous image, auto-saving any changes."""
        if self.has_changes:
            self.save_current_without_advancing()

        if self.current_index > 0:
            self.current_index -= 1
            self.load_image()
        else:
            messagebox.showinfo("Start", "This is the first image.")

    def confirm_discard(self) -> bool:
        """Ask user to confirm discarding unsaved changes."""
        result = messagebox.askyesnocancel(
            "Unsaved Changes",
            "You have unsaved changes. Save before continuing?",
            default=messagebox.YES
        )
        if result is True:  # Yes - save
            self.save_image()
            return True
        elif result is False:  # No - discard
            return True
        else:  # Cancel
            return False

    def on_quit(self):
        """Handle quit request."""
        if self.has_changes:
            if not self.confirm_discard():
                return
        self.root.destroy()

    def run(self):
        """Start the application."""
        print(f"Loaded {len(self.images)} images from {self.folder}")
        print("Starting photo editor...")
        self.root.mainloop()


def main():
    if len(sys.argv) < 2:
        # Default to test_images in same directory as script
        script_dir = Path(__file__).parent
        folder = script_dir / "test_images"
        if not folder.exists():
            print("Usage: python photo_editor.py <folder_path>")
            print("Or place images in a 'test_images' folder next to the script.")
            sys.exit(1)
    else:
        folder = Path(sys.argv[1])

    if not folder.is_dir():
        print(f"Error: {folder} is not a valid directory")
        sys.exit(1)

    editor = PhotoEditor(str(folder))
    editor.run()


if __name__ == "__main__":
    main()
