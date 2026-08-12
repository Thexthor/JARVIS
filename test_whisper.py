from faster_whisper import WhisperModel

modelo = WhisperModel("base")

segmentos, info = modelo.transcribe("test_audio.wav")

print("Idioma detectado:", info.language)

print("\nTexto detectado:\n")

for segmento in segmentos:
    print(segmento.text)