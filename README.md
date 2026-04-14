# Ren'Py Menu & Phone Translator

Traduce SOLO **menus GUI** y **mensajes de telefono** de juegos Ren'Py.
Complemento perfecto para Zenpy (que traduce el resto).

## Que traduce
- Menus: `text "New Game"`, `textbutton "Load"`, `label "Settings"`, etc.
- Mensajes de telefono: `phone.add_message(...)`, `msg_text "..."`, etc.

## Que NO toca
- Dialogos
- Narracion
- Historia

## Uso
```
pip install customtkinter requests google-generativeai
python main.py
```

1. Selecciona el .exe o carpeta del juego
2. Pon tu API key de Gemini en Ajustes (gratis: aistudio.google.com/apikey)
3. Clic en **Traducir y aplicar**

## Build .exe
```
pip install pyinstaller
pyinstaller --onefile --windowed --name RenpyMenuTranslator main.py
```
