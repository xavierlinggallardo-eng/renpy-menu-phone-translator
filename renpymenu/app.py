"""
Ren'Py Menu & Phone Translator
GUI simple y directa — traduce SOLO menús y mensajes de teléfono.
Diseño inspirado en Zenpy.
"""

import os, sys, threading, tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, os.path.dirname(_DIR))

from renpymenu.parser import MenuPhoneParser
from renpymenu.reinserter import apply as reinsert
from renpymenu.translator import Cache, make_translator, translate_all
from renpymenu import config as cfg_module
from utils.exe_detector import find_project_from_exe, get_game_name_from_exe

LANGUAGES = [
    "Spanish","French","German","Italian","Portuguese",
    "Russian","Japanese","Chinese","Korean","Arabic",
    "Dutch","Polish","Turkish","Ukrainian","Czech",
    "Swedish","Romanian","Greek","Hungarian","Finnish",
]

VERSION = "1.0.0"


class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"Ren'Py Menu & Phone Translator  v{VERSION}")
        self.geometry("700x560")
        self.resizable(True, True)
        self.minsize(600, 480)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.cfg = cfg_module.load()
        self.cache = Cache()
        self.project_dir = ""
        self.output_dir  = ""
        self.segments    = []
        self.translations = {}
        self._running    = False

        self._build()
        self._log("Listo. Selecciona el .exe o la carpeta del juego.")
        # Verificar motor disponible al arrancar
        from renpymenu.translator import make_translator
        engine, name = make_translator(self.cfg)
        if engine:
            self._log(f"Motor activo: {name} ✓ (sin configuración extra necesaria)")
        else:
            self._log("⚠ Sin motor. Instala: pip install deep_translator")
            self._log("  O añade una API key en ⚙ Ajustes.")

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        # Título
        title_bar = ctk.CTkFrame(self, height=44, corner_radius=0)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        ctk.CTkLabel(title_bar,
                     text="🎮  Ren'Py Menu & Phone Translator",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(title_bar, text="⚙", width=36, height=28,
                      command=self._open_settings).pack(side="right", padx=10, pady=8)

        # Sección 1: Selección de proyecto
        self._frame_label("📁  Proyecto")
        proj_row = ctk.CTkFrame(self, fg_color="transparent")
        proj_row.pack(fill="x", padx=16, pady=(0,4))

        ctk.CTkButton(proj_row, text="🎮  .exe del juego", width=160, height=34,
                      command=self._pick_exe).pack(side="left", padx=(0,6))
        ctk.CTkButton(proj_row, text="📂  Carpeta", width=120, height=34,
                      command=self._pick_folder).pack(side="left", padx=(0,6))

        self.proj_var = tk.StringVar(value="Ningún proyecto seleccionado")
        ctk.CTkLabel(self, textvariable=self.proj_var,
                     font=ctk.CTkFont(size=11), text_color="#78909c").pack(anchor="w", padx=16)

        # Sección 2: Salida
        self._frame_label("💾  Salida")
        out_row = ctk.CTkFrame(self, fg_color="transparent")
        out_row.pack(fill="x", padx=16, pady=(0,4))
        ctk.CTkButton(out_row, text="📂  Carpeta de salida", width=160, height=30,
                      command=self._pick_output).pack(side="left", padx=(0,6))
        self.out_var = tk.StringVar(value="Automática")
        ctk.CTkLabel(self, textvariable=self.out_var,
                     font=ctk.CTkFont(size=11), text_color="#78909c").pack(anchor="w", padx=16)

        # Sección 3: Configuración
        self._frame_label("🌐  Traducción")
        settings_row = ctk.CTkFrame(self, fg_color="transparent")
        settings_row.pack(fill="x", padx=16, pady=(0,6))

        ctk.CTkLabel(settings_row, text="Idioma:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0,6))
        self.lang_var = ctk.StringVar(value=self.cfg.get("target_lang","Spanish"))
        ctk.CTkOptionMenu(settings_row, variable=self.lang_var,
                          values=LANGUAGES, width=140).pack(side="left", padx=(0,16))

        # Qué traducir
        ctk.CTkLabel(settings_row, text="Traducir:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0,6))
        self.do_gui_var   = ctk.BooleanVar(value=True)
        self.do_phone_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(settings_row, text="Menús GUI",
                        variable=self.do_gui_var, width=110).pack(side="left", padx=(0,4))
        ctk.CTkCheckBox(settings_row, text="Mensajes Phone",
                        variable=self.do_phone_var, width=140).pack(side="left")

        # Sección 4: Botones de acción
        self._frame_label("🎬  Acción")
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0,6))

        ctk.CTkButton(btn_row, text="🔍  Detectar texto",
                      width=150, height=36, command=self._run_detect).pack(side="left", padx=(0,6))

        ctk.CTkButton(btn_row,
                      text="⚡  Traducir y aplicar",
                      width=180, height=36,
                      fg_color="#1b5e20", hover_color="#2e7d32",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._run_full).pack(side="left", padx=(0,6))

        self.cancel_btn = ctk.CTkButton(btn_row, text="⏹", width=40, height=36,
                                         fg_color="#7a1c1c", command=self._cancel,
                                         state="disabled")
        self.cancel_btn.pack(side="left")

        # Stats
        stats_row = ctk.CTkFrame(self, fg_color="transparent")
        stats_row.pack(fill="x", padx=16, pady=(0,2))
        self.stat_var = tk.StringVar(value="")
        ctk.CTkLabel(stats_row, textvariable=self.stat_var,
                     font=ctk.CTkFont(size=11), text_color="#4fc3f7").pack(side="left")

        # Progress
        self.prog_var = tk.StringVar(value="")
        ctk.CTkLabel(self, textvariable=self.prog_var,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16)
        self.progress = ctk.CTkProgressBar(self)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0,6))

        # Log
        self._frame_label("📋  Log")
        self.log_box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Courier New", size=11))
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0,10))
        self.log_box.configure(state="disabled")

    def _frame_label(self, text):
        ctk.CTkLabel(self, text=text,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=16, pady=(10,3))

    # ── Selección ─────────────────────────────────────────────────────────────

    def _pick_exe(self):
        path = filedialog.askopenfilename(
            title="Selecciona el .exe del juego",
            filetypes=[("Ejecutable","*.exe *.sh"),("Todos","*.*")])
        if not path: return
        _, script_dir, rpy_files = find_project_from_exe(path, log=self._log)
        if not rpy_files:
            messagebox.showwarning("Sin .rpy",
                "No se encontraron archivos .rpy.\n"
                "El juego distribuido solo tiene .rpyc (compilado).")
            return
        self.project_dir = script_dir
        name = get_game_name_from_exe(path)
        self.proj_var.set(f"🎮 {name}  ({len(rpy_files)} archivos .rpy)")
        self._auto_output(path)
        self._log(f"Proyecto: {name} — {len(rpy_files)} archivos .rpy")

    def _pick_folder(self):
        path = filedialog.askdirectory(title="Carpeta del proyecto Ren'Py")
        if not path: return
        self.project_dir = path
        import glob
        count = len(list(glob.glob(os.path.join(path, "**/*.rpy"), recursive=True)))
        self.proj_var.set(f"📂 {os.path.basename(path)}  ({count} archivos .rpy)")
        self._auto_output(path)
        self._log(f"Proyecto: {path} — {count} archivos .rpy")

    def _pick_output(self):
        path = filedialog.askdirectory(title="Carpeta de salida")
        if path:
            self.output_dir = path
            self.out_var.set(path)

    def _auto_output(self, src):
        parent = os.path.dirname(src)
        name   = os.path.splitext(os.path.basename(src))[0]
        self.output_dir = os.path.join(parent, name + "_menu_traducido")
        self.out_var.set(self.output_dir)

    # ── Ajustes ───────────────────────────────────────────────────────────────

    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("⚙  API Keys")
        win.geometry("460x340")
        win.resizable(False, False)
        win.grab_set()

        pad = {"padx":20,"pady":5}
        ctk.CTkLabel(win, text="Introduce al menos una API key para traducir.",
                     font=ctk.CTkFont(size=12)).pack(**pad)

        fields = [
            ("Google Gemini (GRATIS — aistudio.google.com/apikey):", "gemini_api_key"),
            ("DeepL API Key:", "deepl_api_key"),
            ("LibreTranslate URL:", "libre_url"),
        ]
        vars_ = {}
        for label, key in fields:
            ctk.CTkLabel(win, text=label, anchor="w").pack(**pad, fill="x")
            show = "*" if "key" in key.lower() else ""
            v = ctk.StringVar(value=self.cfg.get(key,""))
            ctk.CTkEntry(win, textvariable=v, width=400, show=show).pack(**pad)
            vars_[key] = v

        def save():
            for key, v in vars_.items():
                self.cfg[key] = v.get().strip()
            self.cfg["target_lang"] = self.lang_var.get()
            cfg_module.save(self.cfg)
            self._log("[Config] Guardado.")
            win.destroy()

        ctk.CTkButton(win, text="💾  Guardar", width=160, command=save).pack(pady=16)

    # ── Workers ───────────────────────────────────────────────────────────────

    def _run_detect(self):
        if not self.project_dir:
            messagebox.showwarning("Sin proyecto","Selecciona primero el juego.")
            return
        self._start(self._do_detect)

    def _run_full(self):
        if not self.project_dir:
            messagebox.showwarning("Sin proyecto","Selecciona primero el juego.")
            return
        self._start(self._do_full)

    def _cancel(self):
        self._cancelled = True
        self._log("[Cancel] Cancelando...")

    def _start(self, fn):
        if self._running:
            messagebox.showwarning("Ocupado","Hay una tarea en curso.")
            return
        self._running = True
        self._cancelled = False
        self.after(0, lambda: self.cancel_btn.configure(state="normal"))
        threading.Thread(target=fn, daemon=True).start()

    def _finish(self):
        self._running = False
        self.after(0, lambda: self.cancel_btn.configure(state="disabled"))

    def _do_detect(self):
        try:
            self._set_prog(0,"Escaneando...")
            self._log("Buscando menús GUI y mensajes de teléfono...")
            parser = MenuPhoneParser(log=self._log)
            all_segs = parser.parse_project(self.project_dir)

            # Filtrar según checkboxes
            self.segments = []
            do_gui   = self.do_gui_var.get()
            do_phone = self.do_phone_var.get()
            for seg in all_segs:
                if seg.seg_type == "gui"   and do_gui:   self.segments.append(seg)
                if seg.seg_type == "phone" and do_phone: self.segments.append(seg)

            gui_n   = sum(1 for s in self.segments if s.seg_type=="gui")
            phone_n = sum(1 for s in self.segments if s.seg_type=="phone")
            self.stat_var.set(f"Menús GUI: {gui_n}   |   Phone: {phone_n}   |   Total: {len(self.segments)}")
            self._log(f"✓ Detectados: {gui_n} menús GUI + {phone_n} mensajes phone = {len(self.segments)} total")
            self._set_prog(1.0,"✓ Listo")
            self._set_status(f"Detectados {len(self.segments)} segmentos.")
        except Exception as e:
            self._log(f"Error: {e}")
        finally:
            self._finish()

    def _do_full(self):
        try:
            # 1. Detectar
            self._log("1/3 Detectando texto...")
            self._set_prog(0.05,"Detectando...")
            parser = MenuPhoneParser(log=self._log)
            all_segs = parser.parse_project(self.project_dir)
            do_gui   = self.do_gui_var.get()
            do_phone = self.do_phone_var.get()
            self.segments = []
            for seg in all_segs:
                if seg.seg_type == "gui"   and do_gui:   self.segments.append(seg)
                if seg.seg_type == "phone" and do_phone: self.segments.append(seg)

            gui_n   = sum(1 for s in self.segments if s.seg_type=="gui")
            phone_n = sum(1 for s in self.segments if s.seg_type=="phone")
            self.stat_var.set(f"Menús GUI: {gui_n}   |   Phone: {phone_n}   |   Total: {len(self.segments)}")
            self._log(f"✓ {gui_n} GUI + {phone_n} Phone = {len(self.segments)} segmentos")

            if not self.segments:
                self._log("⚠ No se encontró texto de menú ni phone.")
                self._log("  • Verifica que el juego tenga screens.rpy / gui.rpy")
                self._log("  • Para phone: necesita tener sistema de mensajes en los .rpy")
                messagebox.showwarning("Sin texto","No se encontró texto de menú o phone.\n\nVerifica que sea un proyecto Ren'Py con código fuente .rpy")
                return

            # 2. Traducir
            lang = self.lang_var.get()
            self._log(f"2/3 Traduciendo al {lang}...")
            engine, engine_name = make_translator(self.cfg)
            if engine is None:
                messagebox.showerror(
                    "Sin motor de traducción",
                    "No hay ningún motor configurado.\n\n"
                    "Abre ⚙ y añade tu API key.\n\n"
                    "Google Gemini es GRATIS:\n"
                    "aistudio.google.com/apikey"
                )
                return

            self._log(f"Motor: {engine_name} ✓")
            self.translations = translate_all(
                self.segments, engine, engine_name, lang, self.cache,
                log=self._log,
                progress=lambda c,t: self._set_prog(0.1+c/t*0.7, f"{c}/{t}"),
            )

            translated_n = len([v for v in self.translations.values() if v])
            if translated_n == 0:
                self._log("⚠ No se produjo ninguna traducción. Verifica tu API key.")
                messagebox.showwarning("Sin traducciones",
                    "No se tradujo ningún texto.\n\nVerifica tu API key en ⚙ Ajustes.")
                return

            self._log(f"✓ {translated_n}/{len(self.segments)} traducidos")

            # 3. Aplicar
            self._log("3/3 Aplicando traducciones...")
            self._set_prog(0.85,"Aplicando...")
            count = reinsert(
                self.segments, self.translations,
                self.project_dir, self.output_dir,
                log=self._log,
            )

            self._set_prog(1.0,"✓ Completo")
            self._log(f"✓ {count} líneas modificadas → {self.output_dir}")
            self._set_status(f"✓ Completo")
            self.stat_var.set(f"Menús GUI: {gui_n}   |   Phone: {phone_n}   |   Caché: {self.cache.size()}")
            self.after(0, lambda: messagebox.showinfo(
                "¡Listo!",
                f"✅ Traducción completada\n\n"
                f"Menús GUI: {gui_n}\n"
                f"Mensajes Phone: {phone_n}\n"
                f"Líneas modificadas: {count}\n\n"
                f"Salida:\n{self.output_dir}"
            ))
        except Exception as e:
            import traceback
            self._log(f"Error: {e}\n{traceback.format_exc()}")
        finally:
            self._finish()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log(self, msg):
        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _do)

    def _set_prog(self, v, label=""):
        self.after(0, lambda: self.progress.set(min(max(v,0),1)))
        if label:
            self.after(0, lambda: self.prog_var.set(f"  {label}"))

    def _set_status(self, text):
        pass  # status en log es suficiente


def main():
    try:
        import customtkinter  # noqa
    except ImportError:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("Dependencia","Instala customtkinter:\npip install customtkinter")
        return
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
