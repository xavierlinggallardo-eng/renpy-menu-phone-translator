"""
Parser especializado: extrae SOLO menús GUI y mensajes de teléfono.
No toca diálogos, narración ni historia.
"""

import re
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Segment:
    text: str
    file: str
    line: int
    seg_type: str   # "gui" | "phone"
    raw_line: str
    indent: str
    quote_char: str
    context: str = ""  # descripción de contexto para el traductor


# ── Patrones GUI ──────────────────────────────────────────────────────────────
# text "New Game", textbutton "Load", label "Settings", etc.
# Solo en archivos de screen/gui

GUI_KW = re.compile(
    r'^(?P<indent>\s*)(?P<kw>text|textbutton|label|button_text|alt)\s+'
    r'(?P<q>["\'])(?P<text>(?:[^"\'\\]|\\.)*)(?P=q)'
    r'(?P<rest>.*)$'
)

# Strings de GUI hardcodeadas en define/default
GUI_DEFINE = re.compile(
    r'^(?P<indent>\s*)(?:define|default)\s+\S+\s*=\s*'
    r'(?P<q>["\'])(?P<text>[^"\']{2,60})(?P=q)\s*$'
)

# ── Patrones PHONE ─────────────────────────────────────────────────────────────
# Captura todos los patrones conocidos de sistemas de teléfono en AVNs

PHONE_PATTERNS = [
    # Being a DIK / patrones directos de función
    re.compile(
        r'^(?P<indent>\s*)'
        r'\$?\s*(?:phone\.)?(?:add_message|send_message|receive_message|'
        r'msg|text_message|sms|phone_msg|add_msg|new_message|queue_message)\s*\('
        r'[^"\']*'           # argumentos previos (sender, etc.)
        r'(?P<q>["\'])(?P<text>(?:[^"\'\\]|\\.)*)(?P=q)'
        r'.*\)\s*$'
    ),
    # m_text "texto" / p_text "texto" — variantes comunes
    re.compile(
        r'^(?P<indent>\s*)'
        r'(?P<kw>[a-z_]+_text|m_text|p_text|phone_text|sms_text)\s+'
        r'(?P<q>["\'])(?P<text>(?:[^"\'\\]|\\.)*)(?P=q)\s*$'
    ),
    # $ messages.append("texto") / $ inbox.append(...)
    re.compile(
        r'^(?P<indent>\s*)'
        r'\$\s*\S+\.append\s*\(\s*'
        r'(?P<q>["\'])(?P<text>(?:[^"\'\\]|\\.)*)(?P=q)'
        r'\s*\)\s*$'
    ),
    # Dentro de screens de teléfono: text "mensaje" (capturado por contexto)
    # Se activa solo cuando estamos dentro de screen phone/sms/messages
]

# Nombres de screen que indican contexto telefónico
PHONE_SCREEN_NAMES = re.compile(
    r'screen\s+(?P<name>\w*(?:phone|sms|message|msg|text|inbox|chat|contact)\w*)\s*',
    re.IGNORECASE
)

# Archivos GUI/opciones
GUI_FILES = {'screens.rpy', 'gui.rpy', 'options.rpy', 'menu.rpy',
             'interface.rpy', 'menus.rpy', 'ui.rpy', 'main_menu.rpy'}


class MenuPhoneParser:

    def __init__(self, log=None):
        self.log = log or (lambda m: None)

    def parse_project(self, project_dir: str) -> List[Segment]:
        segments = []
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fname in sorted(files):
                if not fname.endswith('.rpy'):
                    continue
                fpath = os.path.join(root, fname)
                segs = self.parse_file(fpath)
                if segs:
                    self.log(f"  {fname}: {len(segs)} segmentos")
                segments.extend(segs)
        return segments

    def parse_file(self, filepath: str) -> List[Segment]:
        fname = os.path.basename(filepath).lower()
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except Exception as e:
            self.log(f"Error leyendo {filepath}: {e}")
            return []

        segments = []
        in_phone_screen = False
        phone_screen_indent = 0
        in_gui_screen = False
        gui_screen_indent = 0

        for i, raw in enumerate(lines):
            stripped = raw.rstrip('\n')
            content = stripped.lstrip()
            line_no = i + 1
            indent_n = len(stripped) - len(content)

            if not content or content.startswith('#'):
                continue

            # ── Detectar inicio de screen ─────────────────────────────────────
            if content.startswith('screen '):
                sm = PHONE_SCREEN_NAMES.match(content)
                if sm:
                    in_phone_screen = True
                    phone_screen_indent = indent_n
                    self.log(f"  [Phone screen] {sm.group('name')} en línea {line_no}")
                else:
                    # Screen GUI genérica
                    in_gui_screen = True
                    gui_screen_indent = indent_n
                continue

            # ── Salida de screen ──────────────────────────────────────────────
            if in_phone_screen and content and indent_n <= phone_screen_indent and not content.startswith('screen'):
                in_phone_screen = False
            if in_gui_screen and content and indent_n <= gui_screen_indent and not content.startswith('screen'):
                in_gui_screen = False

            # ── Patrones de teléfono ──────────────────────────────────────────
            phone_seg = self._try_phone(stripped, filepath, line_no)
            if phone_seg:
                segments.append(phone_seg)
                continue

            # text/textbutton dentro de screen de teléfono → también es phone
            if in_phone_screen:
                m = GUI_KW.match(stripped)
                if m and m.group('text').strip() and len(m.group('text')) > 1:
                    segments.append(Segment(
                        text=m.group('text'), file=filepath, line=line_no,
                        seg_type='phone', raw_line=stripped,
                        indent=m.group('indent'), quote_char=m.group('q'),
                        context=f"phone_screen:{m.group('kw')}",
                    ))
                continue

            # ── Patrones GUI ──────────────────────────────────────────────────
            is_gui_file = fname in GUI_FILES
            if is_gui_file or in_gui_screen:
                m = GUI_KW.match(stripped)
                if m and self._is_gui_text(m.group('text')):
                    segments.append(Segment(
                        text=m.group('text'), file=filepath, line=line_no,
                        seg_type='gui', raw_line=stripped,
                        indent=m.group('indent'), quote_char=m.group('q'),
                        context=m.group('kw'),
                    ))
                    continue

        return segments

    def _try_phone(self, line: str, filepath: str, line_no: int) -> Optional[Segment]:
        for pattern in PHONE_PATTERNS:
            m = pattern.match(line)
            if m and m.group('text').strip() and len(m.group('text').strip()) > 1:
                return Segment(
                    text=m.group('text'), file=filepath, line=line_no,
                    seg_type='phone', raw_line=line,
                    indent=m.group('indent'), quote_char=m.group('q'),
                    context='phone_message',
                )
        return None

    def _is_gui_text(self, text: str) -> bool:
        """Filtra textos que son claramente GUI (no código, no una sola letra)."""
        text = text.strip()
        if not text or len(text) < 2:
            return False
        # Ignorar si parece código Python/Ren'Py
        if text.startswith('[') or text.startswith('{'):
            return False
        # Ignorar si son solo números
        if text.isdigit():
            return False
        # Ignorar rutas de imagen/archivo
        if '/' in text or '\\' in text or text.endswith('.png') or text.endswith('.jpg'):
            return False
        return True
