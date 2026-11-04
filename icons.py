"""Custom monochrome sidebar icons (drawn as SVG masks, tinted with the text color)."""
from urllib.parse import quote

_SVG = {
    # Uniform flow around a cylinder
    "flow_cylinder": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.6' stroke-linecap='round'><circle cx='12' cy='12' r='4'/>"
        "<path d='M2 8C7 8 8 3.5 12 3.5S17 8 22 8M2 16C7 16 8 20.5 12 20.5S17 16 22 16M2 12H6.5M17.5 12H22'/></svg>"
    ),
    # Concentric glowing rings around a bright core (ion thruster plume)
    "ion_rings": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.6'><circle cx='12' cy='12' r='1.3' fill='black' stroke='none'/>"
        "<circle cx='12' cy='12' r='3.9'/><circle cx='12' cy='12' r='7'/><circle cx='12' cy='12' r='10'/></svg>"
    ),
    # Electron: sphere with spin axis arrow and rotation ring
    "spin_electron": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='5.2'/>"
        "<ellipse cx='12' cy='13' rx='9.6' ry='2.8'/><path d='M12 1V6.8M9.8 3.4L12 1L14.2 3.4M12 18V23'/>"
        "<path d='M18.6 9.2L21 11.2L17.8 11.7'/></svg>"
    ),
}


def is_custom(icon):
    return bool(icon) and icon.startswith("svg:")


def css_for_course(course_id, icon):
    svg = _SVG.get(icon[4:])
    if not svg:
        return ""
    url = f'url("data:image/svg+xml,{quote(svg)}")'
    return (f'.st-key-nav_course_{course_id} span[data-testid="stIconMaterial"] {{'
            f'color: transparent !important; width: 1.5rem; height: 1.5rem; display: inline-block; flex: none; '
            f'background: #d5d7dd; -webkit-mask: {url} center/contain no-repeat; '
            f'mask: {url} center/contain no-repeat;}}')
