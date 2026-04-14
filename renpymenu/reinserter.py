"""
Reinsertor: reemplaza solo los segmentos traducidos, preserva todo lo demás.
"""

import os
import re
import shutil
from typing import List, Dict
from .parser import Segment


def _escape(text: str, q: str) -> str:
    return text.replace('\\', '\\\\').replace(q, '\\' + q)


def apply(
    segments: List[Segment],
    translations: Dict[int, str],   # line_no -> texto traducido
    source_dir: str,
    output_dir: str,
    log=None,
) -> int:
    _log = log or (lambda m: None)

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    shutil.copytree(source_dir, output_dir)

    # Agrupar por archivo
    by_file: Dict[str, List[Segment]] = {}
    for seg in segments:
        by_file.setdefault(seg.file, []).append(seg)

    modified = 0

    for filepath, segs in by_file.items():
        # Construir mapa línea -> (nuevo texto, quote_char)
        line_map = {}
        for seg in segs:
            if seg.line in translations and translations[seg.line]:
                line_map[seg.line] = (translations[seg.line], seg.quote_char)

        if not line_map:
            continue

        rel = os.path.relpath(filepath, source_dir)
        out_path = os.path.join(output_dir, rel)

        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except Exception as e:
            _log(f"Error leyendo {filepath}: {e}")
            continue

        new_lines = list(lines)
        for line_no, (new_text, q) in line_map.items():
            idx = line_no - 1
            if idx < 0 or idx >= len(lines):
                continue
            original = lines[idx].rstrip('\n')
            escaped = _escape(new_text, q)
            # Reemplaza la primera ocurrencia de una cadena entre comillas
            rebuilt = re.sub(
                q + r'(?:[^' + q + r'\\]|\\.)*' + q,
                q + escaped + q,
                original,
                count=1,
            )
            new_lines[idx] = rebuilt + '\n'
            modified += 1

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    _log(f"Modificadas {modified} líneas en {len(by_file)} archivos.")
    return modified
