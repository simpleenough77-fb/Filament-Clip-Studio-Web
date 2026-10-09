-- Which slicer the project was written for, and whether the printer has a multi-color system.
ALTER TABLE events ADD COLUMN slicer TEXT;                         -- bambu_studio, orca, creality_print, elegoo, anycubic or prusa
ALTER TABLE events ADD COLUMN multicolor INTEGER NOT NULL DEFAULT 0; -- multi-color system selected
