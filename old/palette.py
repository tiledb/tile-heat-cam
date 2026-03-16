def color_map(value, vmin, vmax):

    ratio = (value - vmin) / (vmax - vmin)

    if ratio < 0:
        ratio = 0
    if ratio > 1:
        ratio = 1

    r = int(255 * ratio)
    g = int(255 * (1 - abs(ratio - 0.5)*2))
    b = int(255 * (1 - ratio))

    return r, g, b