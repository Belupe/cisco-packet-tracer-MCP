"""Ventanas de Packet Tracer 6.0.1 en Windows, sin dependencias (ctypes + zlib).

Comprobado el 2026-10-22 en la maquina del usuario (ver NOTAS.md):
- PrintWindow captura las ventanas de PT (Qt 4) bien, aunque esten tapadas; una ventana OCULTA sale negra.
- Los clics enviados con PostMessage a la ventana de nivel superior funcionan en Qt 4 y no mueven el raton.
- UI Automation NO ve nada dentro de PT: por eso se navega por coordenadas.
Las funciones puras (PNG y busqueda de un trozo de imagen) no dependen de Windows y se prueban sin PT.
"""
import ctypes
import struct
import sys
import zlib


class WinUiError(Exception):
    pass


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAIN_TITLE = "Cisco Packet Tracer"


# ---- PNG (puro) --------------------------------------------------------------
def encode_png(width, height, rows):
    """rows = lista de `height` filas RGB (bytes de 3*width)."""
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return (PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def decode_png(data, max_rows=None):
    """PNG de 8 bits RGB o RGBA sin entrelazar -> (ancho, alto, filas RGB). max_rows: parar antes (las filas
    dependen solo de la anterior, asi que se pueden decodificar las primeras sin hacer el resto)."""
    if not data.startswith(PNG_SIGNATURE):
        raise WinUiError("no es un PNG")
    pos, idat, head = 8, [], None
    while pos + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body[:13])
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
        pos += 12 + n
    if not head:
        raise WinUiError("PNG sin cabecera")
    width, height, depth, ctype, _c, _f, interlace = head
    if depth != 8 or ctype not in (2, 6) or interlace:
        raise WinUiError("PNG no soportado (profundidad %d, color %d, entrelazado %d)" % (depth, ctype, interlace))
    bpp = 3 if ctype == 2 else 4
    stride = width * bpp
    raw = zlib.decompress(b"".join(idat))
    count = height if max_rows is None else min(height, max_rows)
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(count):
        ftype = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        if ftype == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 255
        elif ftype == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif ftype == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 255
        elif ftype == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        elif ftype != 0:
            raise WinUiError("filtro PNG desconocido: %d" % ftype)
        prev = line
        if bpp == 4:
            rgb = bytearray(width * 3)
            rgb[0::3], rgb[1::3], rgb[2::3] = line[0::4], line[1::4], line[2::4]
            rows.append(bytes(rgb))
        else:
            rows.append(bytes(line))
    return width, height, rows


def locate(big_rows, small_rows, sx, sy, size=12):
    """Donde aparece en `big_rows` el trozo size x size de `small_rows` que empieza en (sx, sy).
    Devuelve la lista de desfases (dx, dy) tales que big(x + dx, y + dy) == small(x, y). Va fila a fila con
    bytes.find (rapido aunque la imagen sea grande)."""
    patch = [small_rows[sy + k][sx * 3:(sx + size) * 3] for k in range(size)]
    if len(patch[0]) != size * 3 or any(len(p) != size * 3 for p in patch):
        raise WinUiError("el trozo de referencia se sale de la imagen")
    hits = []
    for y in range(len(big_rows) - size + 1):
        row, start = big_rows[y], 0
        while True:
            i = row.find(patch[0], start)
            if i < 0:
                break
            start = i + 1
            if i % 3:
                continue
            if all(big_rows[y + k][i:i + size * 3] == patch[k] for k in range(1, size)):
                hits.append((i // 3 - sx, y - sy))
    return hits


def distinctive(rows, x, y, size=12):
    """True si el trozo tiene variedad suficiente para no confundirse con el fondo (al menos 6 colores)."""
    colors = set()
    for k in range(size):
        line = rows[y + k]
        for j in range(x, x + size):
            colors.add(line[j * 3:j * 3 + 3])
    return len(colors) >= 6


# ---- Win32 (ctypes) -----------------------------------------------------------
def _api():
    if sys.platform != "win32":
        raise WinUiError("las capturas y clics de ventanas solo funcionan en Windows")
    from ctypes import wintypes
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    H = ctypes.c_void_p
    u.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, H, H), H]
    u.GetWindowThreadProcessId.argtypes = [H, ctypes.POINTER(wintypes.DWORD)]
    u.IsWindowVisible.argtypes = [H]
    u.GetWindowTextW.argtypes = [H, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowRect.argtypes = [H, ctypes.POINTER(wintypes.RECT)]
    u.ScreenToClient.argtypes = [H, ctypes.POINTER(wintypes.POINT)]
    u.PrintWindow.argtypes = [H, H, wintypes.UINT]
    u.PostMessageW.argtypes = [H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    g.CreateCompatibleDC.argtypes = [H]
    g.CreateCompatibleDC.restype = H
    g.CreateDIBSection.argtypes = [H, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), H, wintypes.DWORD]
    g.CreateDIBSection.restype = H
    g.SelectObject.argtypes = [H, H]
    g.SelectObject.restype = H
    g.DeleteObject.argtypes = [H]
    g.DeleteDC.argtypes = [H]
    global _DPI_DONE
    if not _DPI_DONE:
        # Sin esto, con la pantalla al 125 % Windows entrega coordenadas y capturas escaladas (borrosas).
        _DPI_DONE = True
        try:
            u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))          # PER_MONITOR_AWARE_V2
        except (AttributeError, OSError):
            pass
    return u, g, wintypes


_DPI_DONE = False


def visible_rect(hwnd):
    """Rectangulo VISIBLE de la ventana. GetWindowRect incluye el borde invisible de Windows 10/11 (7-8 px a los lados y
    abajo, que PrintWindow pinta de negro); DWMWA_EXTENDED_FRAME_BOUNDS da el marco que se ve, como la Herramienta Recortes."""
    u, _g, wt = _api()
    win = wt.RECT()
    if not u.GetWindowRect(hwnd, ctypes.byref(win)):
        raise WinUiError("la ventana ya no existe")
    vis = wt.RECT()
    try:
        ok = ctypes.windll.dwmapi.DwmGetWindowAttribute(ctypes.c_void_p(hwnd), 9, ctypes.byref(vis), ctypes.sizeof(vis)) == 0
    except (AttributeError, OSError):
        ok = False
    if not ok or vis.right <= vis.left:
        vis = win
    return win, vis


def windows():
    """[(hwnd, pid, titulo, visible)] de todas las ventanas de nivel superior con titulo."""
    u, _g, wt = _api()
    out = []

    def cb(h, _l):
        buf = ctypes.create_unicode_buffer(256)
        if u.GetWindowTextW(h, buf, 256):
            pid = wt.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(pid))
            out.append((h, pid.value, buf.value, bool(u.IsWindowVisible(h))))
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(wt.BOOL, ctypes.c_void_p, ctypes.c_void_p)(cb), None)
    return out


def main_window():
    for h, pid, title, visible in windows():
        if visible and title.startswith(MAIN_TITLE):
            return h, pid
    raise WinUiError("no encuentro la ventana principal de Packet Tracer")


def device_window(name):
    """(hwnd, visible) de la ventana de un equipo (se titula como el equipo), o (None, False)."""
    _main, pid = main_window()
    for h, wpid, title, visible in windows():
        if wpid == pid and title == name:
            return h, visible
    return None, False


def capture(hwnd, full=False):
    """Captura con PrintWindow (PW_RENDERFULLCONTENT) -> (ancho, alto, filas RGB), recortada al marco visible (sin el borde
    invisible negro). full=True: la ventana entera tal como la da PrintWindow (para calcular posiciones de clic)."""
    u, g, wt = _api()
    rect, vis = visible_rect(hwnd)
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise WinUiError("la ventana tiene tamano 0 (minimizada?)")
    header = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)   # BITMAPINFOHEADER, filas de arriba abajo
    bits = ctypes.c_void_p()
    dc = g.CreateCompatibleDC(None)
    bmp = g.CreateDIBSection(dc, ctypes.c_char_p(header), 0, ctypes.byref(bits), None, 0)
    try:
        old = g.SelectObject(dc, bmp)
        ok = u.PrintWindow(hwnd, dc, 2)
        raw = ctypes.string_at(bits, w * h * 4)
        g.SelectObject(dc, old)
    finally:
        g.DeleteObject(bmp)
        g.DeleteDC(dc)
    if not ok:
        raise WinUiError("PrintWindow fallo")
    x0, y0, x1, y1 = 0, 0, w, h
    if not full:
        x0, y0 = max(0, vis.left - rect.left), max(0, vis.top - rect.top)
        x1, y1 = min(w, vis.right - rect.left), min(h, vis.bottom - rect.top)
    rows = []
    for y in range(y0, y1):
        line = raw[(y * w + x0) * 4:(y * w + x1) * 4]
        rgb = bytearray((x1 - x0) * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = line[2::4], line[1::4], line[0::4]   # BGRA -> RGB
        rows.append(bytes(rgb))
    if not full:
        rows = trim_black(rows)
    return len(rows[0]) // 3 if rows else 0, len(rows), rows


APP_BAR = b"\x00\x00\xff"          # barra de titulo de una aplicacion abierta en el Desktop de un PC (azul puro)


def desktop_app_close(rows, x=100):
    """Si hay una aplicacion abierta dentro del Desktop (IP Configuration, Command Prompt...), devuelve (x, y) de su boton X
    en la captura ENTERA (coordenadas de ventana); si no, None. Cada aplicacion tiene la barra a una altura y anchura distintas
    (IP Configuration: X en 489,54; Command Prompt: 610,94): se busca la barra azul en la columna `x` y la X va 14 px a la
    derecha del ultimo azul de esa fila."""
    def blues(line):
        return sum(1 for i in range(0, len(line), 3) if line[i:i + 3] == APP_BAR)
    bar = [y for y in range(30, min(len(rows), 220)) if blues(rows[y]) > 150]      # filas de la barra (el texto blanco la corta)
    if not bar:
        return None
    top = bar[0]
    bottom = top
    while bottom + 1 in bar:
        bottom += 1
    mid = (top + bottom) // 2
    # La X es una caja con borde gris d0d0d0 a cada lado y fondo fdfdfd (con la X dibujada en medio), de 20-35 px.
    line = rows[mid]
    width = len(line) // 3
    borders = [i for i in range(width) if line[i * 3:i * 3 + 3] == BOX_BORDER]
    for a, b in zip(borders, borders[1:]):
        if 18 <= b - a <= 35:
            inside = [line[i * 3:i * 3 + 3] for i in range(a + 1, b)]
            if sum(1 for p in inside if p == BOX_FILL) >= 0.6 * len(inside):
                return (a + b) // 2, mid
    return None


BOX_BORDER, BOX_FILL = b"\xd0\xd0\xd0", b"\xfd\xfd\xfd"


def trim_black(rows):
    """Quita filas y columnas de los bordes que son negro puro: PrintWindow pinta el marco 1 px desplazado respecto a lo
    que dice DWM y quedaba una linea negra a la izquierda y abajo (el usuario lo vio comparando con la Herramienta Recortes)."""
    def mostly_black(pixels):
        pixels = list(pixels)
        return pixels and sum(1 for p in pixels if p == b"\x00\x00\x00") >= 0.9 * len(pixels)

    def row_pixels(r):
        return (r[i:i + 3] for i in range(0, len(r), 3))
    rows = list(rows)
    # Se mira con un 90 %: en la columna del borde, la franja del titulo no sale negra.
    while len(rows) > 1 and mostly_black(row_pixels(rows[-1])):
        rows.pop()
    while len(rows) > 1 and mostly_black(row_pixels(rows[0])):
        rows.pop(0)
    if not rows:
        return rows
    width = len(rows[0]) // 3
    left = 0
    while left < width - 1 and mostly_black(r[left * 3:left * 3 + 3] for r in rows):
        left += 1
    right = width
    while right > left + 1 and mostly_black(r[(right - 1) * 3:right * 3] for r in rows):
        right -= 1
    return [r[left * 3:right * 3] for r in rows] if (left or right < width) else rows


def click(hwnd, x, y):
    """Clic izquierdo en (x, y) medidos desde la esquina de la VENTANA (como en una captura), sin mover el raton."""
    u, _g, wt = _api()
    rect = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(rect))
    pt = wt.POINT(rect.left + int(x), rect.top + int(y))
    u.ScreenToClient(hwnd, ctypes.byref(pt))
    lp = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)
    for msg, wp in ((0x0200, 0), (0x0201, 1), (0x0202, 0)):      # MOUSEMOVE, LBUTTONDOWN, LBUTTONUP
        u.PostMessageW(hwnd, msg, wp, lp)


def key(hwnd, vk):
    u, _g, _wt = _api()
    u.PostMessageW(hwnd, 0x0100, vk, 1)                          # WM_KEYDOWN
    u.PostMessageW(hwnd, 0x0101, vk, 0xC0000001)                 # WM_KEYUP


VK_ESCAPE = 0x1B
