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
    # Simplified anatomy figure: head, torso with open chest cavity showing lungs
    # Vitruvian Man: circle, square and a figure with two arm and two leg poses
    "anatomy_body": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.2' stroke-linecap='round' stroke-linejoin='round'>"
        "<circle cx='12' cy='12' r='10.6'/>"
        "<circle cx='12' cy='6.6' r='1.1' fill='black'/>"
        "<path d='M12 7.8V13.2M5 9.8H19M6.4 6L12 8.6L17.6 6M12 13.2L8.2 19.6M12 13.2L15.8 19.6'/></svg>"
    ),
    # Ringed planet with an orbiting body
    "orbit_planet": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.7' stroke-linecap='round'><circle cx='12' cy='11.5' r='7'/>"
        "<ellipse cx='12' cy='13' rx='10.5' ry='3' transform='rotate(-20 12 13)'/>"
        "<circle cx='15.5' cy='14.8' r='2.1' fill='black' stroke='none'/></svg>"
    ),
    # Globe with rising bar chart and trend arrow
    "macro_globe": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'>"
        "<circle cx='8.2' cy='11.8' r='6.8'/><ellipse cx='8.2' cy='11.8' rx='3' ry='6.8'/>"
        "<path d='M1.4 11.8H15M8.2 5V18.6'/>"
        "<path d='M21.2 15C21.2 13.6 16.2 13.4 16.2 15.6C16.2 17.8 21.2 17.2 21.2 19.4C21.2 21.4 16.2 21.2 16.2 19.8M18.7 12.6V22'/>"
        "<path d='M11.5 11.2L15.6 8L17.2 9.6L21.6 5.6M19 5.4H22V8.4'/></svg>"
    ),
    # Beam steam engine: flywheel, pillar and rocking beam, cylinder, base
    "steam_engine": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'>"
        "<circle cx='7' cy='14.2' r='5.6'/><circle cx='7' cy='14.2' r='1' fill='black'/>"
        "<path d='M7 8.6V19.8M2.2 11.4L11.8 17M2.2 17L11.8 11.4'/>"
        "<path d='M2 21.8H22M13.2 21.8V6.5M4.6 3.8L19.4 5.2M4.6 3.8V8.6'/>"
        "<rect x='16.4' y='11' width='4' height='8.4'/><path d='M18.4 5.4V11'/></svg>"
    ),
    # Supply and demand curves crossing on price/quantity axes
    "supply_demand": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M3.5 2.5V20.5H21.5'/><path d='M7 5.5L19 17M7 17L19 6.5'/></svg>"
    ),
    # Venturi tube: pipe narrowing in the middle, pressure tap and flow arrow
    "venturi": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M2 6.5H7C9.2 6.5 9.6 9.3 12 9.3S14.8 6.5 17 6.5H22M2 17.5H7C9.2 17.5 9.6 14.7 12 14.7S14.8 17.5 17 17.5H22'/>"
        "<path d='M12 9.3V2.5M4.5 12H19.5M16.8 10L19.5 12L16.8 14'/></svg>"
    ),
    # Airfoil with lift arrow and streamline over the top
    "airfoil_lift": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M2.5 17.2C2.5 14.8 5.5 14 9.5 14.4C14 14.9 18.2 17 21.5 19.4C16 19.4 8 20.2 3.6 18.8C2.9 18.5 2.5 18 2.5 17.2Z' "
        "fill='black'/><path d='M9.4 13V3M7.2 5.2L9.4 3L11.6 5.2'/>"
        "<path d='M1.5 11.2C5 10 9.5 9.8 14 11C18 12 20 13.4 22.5 14.2'/></svg>"
    ),
    # Three wavy rising arrows (heat transfer)
    "heat_arrows": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'><path d='M5 21C2.5 18 7.5 15 5 12S2.5 7 5 4M2.8 6.4L5 3.6L7.2 6.4M12 21C9.5 18 14.5 15 12 12S9.5 7 12 4M9.8 6.4L12 3.6L14.2 6.4M19 21C16.5 18 21.5 15 19 12S16.5 7 19 4M16.8 6.4L19 3.6L21.2 6.4'/></svg>"
    ),
    # Atom: three tilted orbits, nucleus and electrons
    "atom": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.2'><ellipse cx='12' cy='12' rx='3.4' ry='10.4'/>"
        "<ellipse cx='12' cy='12' rx='3.4' ry='10.4' transform='rotate(60 12 12)'/>"
        "<ellipse cx='12' cy='12' rx='3.4' ry='10.4' transform='rotate(-60 12 12)'/>"
        "<circle cx='12' cy='12' r='1.9' fill='black'/>"
        "<circle cx='21' cy='6.8' r='1.2' fill='black'/><circle cx='3' cy='6.8' r='1.2' fill='black'/>"
        "<circle cx='12' cy='22.4' r='1.2' fill='black'/></svg>"
    ),
    # Cart on a rail: overhead rail, hanger with spring, wheeled platform, ground line
    "rail_cart": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M2 4.5H19M13 4.5V7.5L11.2 8.7L14.8 10.3L11.2 11.9L13 12.8'/>"
        "<path d='M7 13.2H19'/><circle cx='9.4' cy='15.6' r='1.5'/><circle cx='16.6' cy='15.6' r='1.5'/>"
        "<path d='M2 20.5H22'/></svg>"
    ),
    # Cantilever beam fixed to a hatched wall
    "cantilever": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.4' stroke-linecap='round'><rect x='2' y='9.8' width='17' height='4.4' fill='black'/>"
        "<path d='M19 3V21M19 7L22.4 4M19 11L22.4 8M19 15L22.4 12M19 19L22.4 16M19 22.5L22.4 19.5'/></svg>"
    ),
    # Wavy heat lines rising above a heated surface
    "heat_surface": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M6.5 2.5C9.3 5 3.7 7.5 6.5 10S9.3 13.5 6.5 15.5M12 2.5C14.8 5 9.2 7.5 12 10S14.8 13.5 12 15.5M17.5 2.5C20.3 5 14.7 7.5 17.5 10S20.3 13.5 17.5 15.5M3.5 20.5H20.5'/></svg>"
    ),
    # Turbofan engine (side view): nacelle, fan, compressor/turbine stages, spinner and exhaust cone
    "turbofan": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.3' stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M2.5 4.2C7 4.2 8.5 7.4 12 7.4S17 6.6 21.8 3.6M2.5 19.8C7 19.8 8.5 16.6 12 16.6S17 17.4 21.8 20.4'/>"
        "<path d='M5 4.2V19.8' stroke-width='2.2'/><path d='M2 12L5 9.6V14.4Z' fill='black'/><path d='M17.4 10.2L21 12L17.4 13.8Z' fill='black'/>"
        "<path d='M5 12H17.5M8 9.6V14.4M10.4 9.2V14.8M13.4 9.4V14.6M15.6 9.8V14.2'/></svg>"
    ),
    # Rocket engine: turbopumps and feed lines, combustion chamber, bell nozzle with exhaust arrows
    "rocket_engine": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'>"
        "<circle cx='5' cy='4.2' r='2.7'/><circle cx='19' cy='4.2' r='2.7'/>"
        "<circle cx='5' cy='10' r='0.9' stroke-width='1'/><circle cx='19' cy='10' r='0.9' stroke-width='1'/>"
        "<path d='M5 6.9V9.1M5 10.9V12.2H9.4V9.6M19 6.9V9.1M19 10.9V12.2H14.6V9.6'/>"
        "<path d='M8.6 9.6H15.4M8.6 9.6V13C8.6 14.4 10.6 14.6 10.6 16C10.6 19 7.7 19.4 7.6 22.4'/>"
        "<path d='M15.4 9.6V13C15.4 14.4 13.4 14.6 13.4 16C13.4 19 16.3 19.4 16.4 22.4'/></svg>"
    ),
    # Control-system summing junction: circled X with input, feedback (-) and output
    "summing_junction": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'>"
        "<circle cx='12' cy='10.5' r='4.6'/><path d='M8.8 7.3L15.2 13.7M15.2 7.3L8.8 13.7'/>"
        "<path d='M1.5 10.5H7.4M5.7 8.9L7.4 10.5L5.7 12.1M16.6 10.5H22.5M20.8 8.9L22.5 10.5L20.8 12.1'/>"
        "<path d='M12 22.5V15.4M10.4 17.1L12 15.4L13.6 17.1'/>"
        "</svg>"
    ),
    # Flame silhouette with an inner flame cut out
    "flame": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='270 50 640 880'>"
        "<path fill-rule='evenodd' d='M611 65C480 110 470 230 475 262C482 345 460 420 420 459C395 405 360 380 327 378C345 405 340 440 328 470C312 512 296 550 291 600C284 650 290 690 291 695C305 790 370 870 493 915L692 909C900 850 930 640 835 413C830 480 805 525 780 532C775 440 735 370 705 330C690 310 678 298 665 288C600 235 590 140 611 65ZM602 421C520 450 518 530 520 540C525 600 505 640 488 657C470 622 448 610 432 608C445 630 440 650 430 670C415 710 405 760 410 795C418 855 450 890 493 915L692 909C790 850 780 700 737 630C733 665 720 695 703 700C700 650 680 600 655 568C646 558 640 555 633 552C590 515 590 460 602 421Z'/></svg>"
    ),
    # Viscous boundary layer: velocity profile (arrows grow away from the wall) over a hatched plate
    "boundary_layer": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.3' stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M4 5V20M4 17H9.0M7.3 15.8L9.0 17L7.3 18.2M4 13.5H14.0M12.3 12.3L14.0 13.5L12.3 14.7M4 10H18.0M16.3 8.8L18.0 10L16.3 11.2M4 6.5H20.5M18.8 5.3L20.5 6.5L18.8 7.7'/><path d='M4 20C7.5 19 10 15.5 14 13.5C17 11.8 19.5 9 20.5 6.5' stroke-width='1'/><path d='M2 21.2H22M4 21.2L2.6 22.8M8 21.2L6.6 22.8M12 21.2L10.6 22.8M16 21.2L14.6 22.8M20 21.2L18.6 22.8'/></svg>"
    ),
    # Mathematics course icons: function graph, series (sigma), vector field, matrix
    "function_curve": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'><path d='M3.5 3.5V20.5H21'/><path d='M5.5 16.5C9 16.5 9.5 6.5 13 6.5S17.5 13 20.5 8'/><circle cx='13' cy='6.5' r='1.1' fill='black' stroke='none'/></svg>"
    ),
    "sigma_series": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.9' stroke-linecap='round' stroke-linejoin='round'><path d='M17.5 4.5H6.5L12.5 12L6.5 19.5H17.5'/></svg>"
    ),
    "vector_field": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'><path d='M3.4 7.6L7.6 3.4M5.6 3.9L7.6 3.4L7.1 5.4M9.0 5.5L15.0 5.5M13.2 4.5L15.0 5.5L13.2 6.5M16.4 3.4L20.6 7.6M20.1 5.6L20.6 7.6L18.6 7.1M5.5 15.0L5.5 9.0M4.5 10.8L5.5 9.0L6.5 10.8M18.5 9.0L18.5 15.0M19.6 13.2L18.5 15.0L17.4 13.2M7.6 20.6L3.4 16.4M3.9 18.4L3.4 16.4L5.4 16.9M15.0 18.5L9.0 18.5M10.8 19.6L9.0 18.5L10.8 17.4M20.6 16.4L16.4 20.6M18.4 20.1L16.4 20.6L16.9 18.6'/></svg>"
    ),
    "matrix_brackets": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'><path d='M8 4H5V20H8M16 4H19V20H16'/><circle cx='9.6' cy='8.5' r='1' fill='black' stroke='none'/><circle cx='12' cy='8.5' r='1' fill='black' stroke='none'/><circle cx='14.4' cy='8.5' r='1' fill='black' stroke='none'/><circle cx='9.6' cy='12' r='1' fill='black' stroke='none'/><circle cx='12' cy='12' r='1' fill='black' stroke='none'/><circle cx='14.4' cy='12' r='1' fill='black' stroke='none'/><circle cx='9.6' cy='15.5' r='1' fill='black' stroke='none'/><circle cx='12' cy='15.5' r='1' fill='black' stroke='none'/><circle cx='14.4' cy='15.5' r='1' fill='black' stroke='none'/></svg>"
    ),
    # Ordinary differential equations: slope field with a solution curve
    "slope_field": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-linecap='round' stroke-linejoin='round'>"
        "<path stroke-width='1.1' d='M4.2 3.5L5.8 6.5M8.6 3.7L10.8 6.3M12.8 4.1L15.8 5.9M17.3 5.0L20.7 5.0M3.9 8.4L6.1 11.0M8.2 8.8L11.2 10.6M12.6 9.7L16.0 9.7M17.5 10.6L20.5 8.8M3.5 13.4L6.5 15.2M8.0 14.3L11.4 14.3M12.8 15.2L15.8 13.4M17.9 15.6L20.1 13.0M3.3 19.0L6.7 19.0M8.2 19.9L11.2 18.1M13.2 20.3L15.4 17.7M18.2 20.5L19.8 17.5'/><path stroke-width='2' d='M3 5C5.5 14 9 16.5 12.5 13.5S19 6.5 21.5 4.5'/></svg>"
    ),
    # Partial differential equations: the partial-derivative sign
    "partial_derivative": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M8 5.5C9.6 3.6 14.2 3.4 15.8 7.6C17.4 11.8 16.4 17.2 12.2 19.7C8.6 21.7 6.4 17.8 8.4 14.8C10 12.4 13.4 12 15.8 13.2'/></svg>"
    ),
    # Multivariable calculus: a potato-chip (saddle) surface with a tilted normal vector
    "surface_normal": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M2.6 14.6Q5 8 12 6.6Q15.2 11.2 21.4 12.2Q20.4 19 12.8 20.2Q8.4 15.2 2.6 14.6Z'/><path stroke-width='1' d='M6.2 11.2Q11.5 15.2 17.2 15.6'/><path d='M12.4 12.8L19.8 3.4M17.1 4.6L19.8 3.4L19.3 6.4'/><circle cx='12.4' cy='12.8' r='1.1' fill='black' stroke='none'/></svg>"
    ),
    # Courses menu icon: graduation cap
    "course_cap": (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
        "stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M12 4L22 9L12 14L2 9Z'/><path d='M6 11.4V16C6 17.8 8.7 19.5 12 19.5S18 17.8 18 16V11.4'/>"
        "<path d='M22 9V15'/><circle cx='22' cy='16.2' r='1' fill='black' stroke='none'/></svg>"
    ),
}


def is_custom(icon):
    return bool(icon) and icon.startswith("svg:")


def mask_url(icon):
    """CSS url() of the custom icon's SVG (for use with mask-image), or '' if unknown."""
    svg = _SVG.get((icon or "")[4:])
    return f"url('data:image/svg+xml,{quote(svg)}')" if svg else ""


def css_for_course(course_id, icon):
    svg = _SVG.get(icon[4:])
    if not svg:
        return ""
    url = f'url("data:image/svg+xml,{quote(svg)}")'
    return (f'.st-key-nav_course_{course_id} span[data-testid="stIconMaterial"] {{'
            f'color: transparent !important; width: 1.5rem; height: 1.5rem; display: inline-block; flex: none; '
            f'background: #d5d7dd; -webkit-mask: {url} center/contain no-repeat; '
            f'mask: {url} center/contain no-repeat;}}')


def css_for_nav(key, icon):
    """Draw a custom SVG as the icon of the sidebar button whose widget key is `key` (e.g. "nav_Courses")."""
    svg = _SVG.get(icon[4:])
    if not svg:
        return ""
    url = f"url('data:image/svg+xml,{quote(svg)}')"
    return (f'.st-key-{key} span[data-testid="stIconMaterial"] {{color: transparent !important; width: 1.5rem; '
            f'height: 1.5rem; display: inline-block; flex: none; background: #d5d7dd; '
            f'-webkit-mask: {url} center/contain no-repeat; mask: {url} center/contain no-repeat;}}'
            f'.st-key-{key} button[data-testid="stBaseButton-primary"] span[data-testid="stIconMaterial"] '
            f'{{background: #fff;}}')
