# photo-scrub
Clean up filenames, crop factor, mirroring and other issues with scanned film photos.

<img width="1801" height="1149" alt="image" src="https://github.com/user-attachments/assets/54747f50-213c-44f9-8e41-4967f40042e2" />

## Photo Editor for Scanned Film Photos

A simple GUI tool for reviewing and correcting scanned photos:
- Mirror/rotate images to fix scanning errors
- Crop edges by dragging handles inward (for removing white bars from scans)
- Add date metadata to EXIF
- Quick date selection from recently used dates

### Keyboard shortcuts:
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

### Crop feature:
    - Drag the blue handles on any edge inward to crop
    - Cropped areas appear darkened with red boundary lines
    - Crop is applied when saving the image
    - Press C to reset crop, or U to undo all changes

## Why?

I had a big mess of scanned film negatives that were completely unorganized. Some were scanned backwards and looked mirrored, some the orientation was wrong, and all of them were missing the date from EXIF data which made them hard to upload anywhere. This tool lets you pass it a directory, and then go through and quickly fix the issues. The main manual step is typing in the dates burned into the image, but there are quick shortcuts saved from recent photos to speed this up. I tried using OCR to pull out the date from images, but when they can be mirrored, rotated, or on an over exposed background it was less fuss to just make it quick to fix manually. Files are renamed to the date followed by folder name so they self organize by date and are easy to work with. The date is saved to exif data so photo backup services will put them on the timeline correctly, and rotation exif data is reset and cleaned up.
