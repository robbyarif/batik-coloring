# Batik Coloring

A static coloring page for batik patterns. No server needed: open `index.html` in a browser.

## Modes

- **Basic** – starts from the black-and-white contour. Brush or "Fill section" uncovers the original colours underneath. "Show all colours" reveals everything; "Reset" hides them again.
- **Free coloring** – pick a colour from the palette (or a custom one), then fill a section or paint freely. Painting stays inside the lines because the contour is drawn on top.

Both modes support Undo (button or Ctrl+Z) and "Download PNG" to save the result to your device.

## Files

| Path | Purpose |
| --- | --- |
| `index.html`, `styles.css`, `app.js` | The app |
| `patterns/<id>.js` | One file per pattern: line art + original colours (embedded, so it works from `file://`) |
| `tools/make_pattern.py` | Generates a pattern file from a scan/photo |
| `parang.jpg` | Source image for the Parang pattern |

## Adding a pattern

1. Install the tool's dependencies once: `pip install numpy pillow scipy`
2. Generate the file:

   ```
   python tools/make_pattern.py kawung.jpg --id kawung --name "Kawung"
   ```

   Add `--preview preview.png` to check the contour before using it.
3. Add a script tag in `index.html`, next to the existing one:

   ```html
   <script src="patterns/kawung.js"></script>
   ```

The pattern appears in the Pattern dropdown automatically.

### Tuning the contour

If a new pattern gives too many or too few lines, adjust these options:

- `--clusters N` – number of colour groups (default 4). Fewer groups means fewer lines.
- `--smooth S` – smoothing of region borders (default 3). Higher means smoother, simpler lines.
- `--min-region PX` – smallest fillable area in pixels (default 150). Smaller specks become black lines.
- `--thicken N` – line thickness in pixels (default 1).
