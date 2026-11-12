#!/usr/bin/env python3
"""
The profile's icon set: simple 24×24 line icons, drawn for this README so it
needs no emoji and no icon font.

  python3 scripts/icons.py           writes assets/icons/<name>.svg
  from icons import icon             inline use inside the generated cards

Every icon is stroke-only (2px, round caps and joins) on a 24×24 grid. To add
one, add an entry to ICONS and rerun this file.
"""

import os
import sys

# Mid-tone blue → violet: readable on GitHub's light and dark backgrounds.
GRADIENT = ("#5b8ef0", "#a06cf0")

ICONS = {
    # Sections
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "layers": '<path d="M12 2.5 22 7.5l-10 5-10-5 10-5z"/><path d="m2 12 10 5 10-5"/>'
              '<path d="m2 16.5 10 5 10-5"/>',
    "code": '<path d="m8 7-5 5 5 5"/><path d="m16 7 5 5-5 5"/><path d="m14 4-4 16"/>',
    "chip": '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/>'
            '<path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    "network": '<circle cx="4.5" cy="6.5" r="2.2"/><circle cx="4.5" cy="17.5" r="2.2"/>'
               '<circle cx="12" cy="12" r="2.2"/><circle cx="19.5" cy="6.5" r="2.2"/>'
               '<circle cx="19.5" cy="17.5" r="2.2"/>'
               '<path d="m6.4 7.9 3.8 2.8M6.4 16.1l3.8-2.8M13.8 10.7l3.8-2.8M13.8 13.3l3.8 2.8"/>',
    "gamepad": '<path d="M7 6.5h10a4 4 0 0 1 3.9 3.2l1 5a2.8 2.8 0 0 1-4.8 2.5L15.5 15.5h-7l-1.6 1.7'
               'a2.8 2.8 0 0 1-4.8-2.5l1-5A4 4 0 0 1 7 6.5z"/><path d="M8 9.5v4M6 11.5h4"/>'
               '<circle cx="15.5" cy="10.5" r=".6"/><circle cx="17.5" cy="12.5" r=".6"/>',
    "blocks": '<rect x="8" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/>'
              '<rect x="13" y="13" width="8" height="8" rx="1.5"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "trophy": '<path d="M7 4h10v5a5 5 0 0 1-10 0V4z"/><path d="M7 5.5H4.5v1.5A3 3 0 0 0 7 10"/>'
              '<path d="M17 5.5h2.5v1.5A3 3 0 0 1 17 10"/><path d="M12 14v4M8.5 21h7M9.5 18h5"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
    "chart": '<path d="M4 20h16"/><path d="M7 16v-4M12 16V6M17 16V9"/>',
    # About
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>'
             '<path d="M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
    "server": '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/>'
              '<circle cx="7" cy="7.5" r=".6"/><circle cx="7" cy="16.5" r=".6"/><path d="M11 7.5h6M11 16.5h6"/>',
    "check": '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8 7.5 9.5 4.3-1.5 7.5-4.9 7.5-9.5V6L12 3z"/>'
             '<path d="m8.8 12.2 2.3 2.3 4.3-4.6"/>',
    "phone": '<rect x="6.5" y="2" width="11" height="20" rx="2.5"/><path d="M10.5 18.5h3"/>',
    "cap": '<path d="m2 9 10-5 10 5-10 5L2 9z"/><path d="M6 11v5c0 1.6 2.7 3 6 3s6-1.4 6-3v-5"/>'
           '<path d="M22 9v5"/>',
    "pin": '<path d="M12 21.5s-7-6.1-7-11.7a7 7 0 0 1 14 0c0 5.6-7 11.7-7 11.7z"/><circle cx="12" cy="9.8" r="2.5"/>',
    "flag": '<path d="M5 21.5V4"/><path d="M5 4h12l-2.5 4.5L17 13H5"/>',
    "team": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20.5a6.5 6.5 0 0 1 13 0"/>'
            '<path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M21.5 20.5a6.5 6.5 0 0 0-3.8-5.9"/>',
    # Projects
    "map": '<path d="m3 6.5 6-2.5 6 2.5 6-2.5v13.5l-6 2.5-6-2.5-6 2.5V6.5z"/><path d="M9 4v13.5M15 6.5V20"/>',
    "gate": '<path d="M5 5.5h6a6.5 6.5 0 0 1 0 13H5v-13z"/><path d="M1.5 9H5M1.5 15H5M17.5 12h5"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>'
                '<path d="M7.5 14h.01M12 14h.01M16.5 14h.01M7.5 17.5h.01M12 17.5h.01"/>',
    "moon": '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.8 6.8 0 0 0 10.5 10.5z"/>',
    "bluetooth": '<path d="m7 7 10 10-5 5V2l5 5L7 17"/>',
    "nib": '<path d="M12 2.5c3.2 3 6 5.7 6 9.3l-6 9.7-6-9.7c0-3.6 2.8-6.3 6-9.3z"/><path d="M12 13v8.5"/>'
           '<circle cx="12" cy="10.5" r="1.8"/>',
    "news": '<path d="M4 5h12.5v14a2 2 0 0 0 2 2H6a2 2 0 0 1-2-2V5z"/><path d="M16.5 9H20v10a2 2 0 0 1-2 2"/>'
            '<path d="M7.5 9h5.5M7.5 13h5.5M7.5 17h3.5"/>',
    "spell": '<path d="m3 18 4.5-12L12 18"/><path d="M4.7 13.5h5.6"/><path d="m14 15 2.5 2.5L21.5 12"/>',
    "wand": '<path d="m4 20 11-11"/><path d="m13.5 6.5 4 4"/><path d="M18 2.5v4M16 4.5h4"/>'
            '<path d="M20 11v3M18.5 12.5h3"/><path d="M9 2.5v3M7.5 4h3"/>',
    "grid": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>',
    "pawn": '<circle cx="12" cy="6" r="3"/><path d="M10 10h4l1.5 7h-7L10 10z"/><path d="M6 21h12l-1.2-4H7.2L6 21z"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9.5 3 2.5-3 2.5"/><path d="M12.5 15H17"/>',
    "zap": '<path d="M13.5 2 4.5 13.5H11L10 22l9.5-12H13l.5-8z"/>',
    "fuel": '<path d="M4 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16"/><path d="M2.5 21h13"/><path d="M4 10h10"/>'
            '<path d="M14 8.5h2a2 2 0 0 1 2 2v5a1.5 1.5 0 0 0 3 0V8l-3-3"/>',
    "tetromino": '<rect x="3" y="7" width="6" height="6" rx="1"/><rect x="9" y="7" width="6" height="6" rx="1"/>'
                 '<rect x="15" y="7" width="6" height="6" rx="1"/><rect x="9" y="13" width="6" height="6" rx="1"/>',
    # Links
    "book": '<path d="M2.5 5H8a4 4 0 0 1 4 4v11a3 3 0 0 0-3-3H2.5V5z"/>'
            '<path d="M21.5 5H16a4 4 0 0 0-4 4v11a3 3 0 0 1 3-3h6.5V5z"/>',
    "download": '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>',
    "play": '<path d="M7 4.5v15L19.5 12 7 4.5z"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    # Card stats
    "commit": '<circle cx="12" cy="12" r="3.5"/><path d="M2.5 12h6M15.5 12h6"/>',
    "pull": '<circle cx="6" cy="5.5" r="2.3"/><circle cx="6" cy="18.5" r="2.3"/><circle cx="18" cy="18.5" r="2.3"/>'
            '<path d="M6 7.8v8.4"/><path d="M18 16.2V10a3.5 3.5 0 0 0-3.5-3.5H11"/><path d="m13.5 4-2.5 2.5 2.5 2.5"/>',
    "repo": '<path d="M5 19.5v-15A2.5 2.5 0 0 1 7.5 2H19v15H7.5A2.5 2.5 0 0 0 5 19.5z"/>'
            '<path d="M5 19.5A2.5 2.5 0 0 0 7.5 22H19v-5"/>',
    "star": '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3z"/>',
}


def standalone(name, size=24):
    a, b = GRADIENT
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="url(#g)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'<defs><linearGradient id="g" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs>'
            f'{ICONS[name]}</svg>\n')


def icon(name, x, y, size, color, width=2):
    """An icon placed inside another SVG, as a group."""
    return (f'<g transform="translate({x} {y}) scale({size / 24:.4f})" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g>')


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "icons")
    os.makedirs(out, exist_ok=True)
    for name in ICONS:
        with open(os.path.join(out, f"{name}.svg"), "w") as f:
            f.write(standalone(name))
    print(f"wrote {len(ICONS)} icons to {os.path.normpath(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
