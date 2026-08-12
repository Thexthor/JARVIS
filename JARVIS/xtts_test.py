from TTS.api import TTS

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

tts.tts_to_file(
    text="Hola Gabo. Sistema Jarvis iniciado correctamente.",
    speaker_wav=r"C:\Users\Gabo\Desktop\JARVIS\voices\voz.wav",
    language="es",
    file_path=r"C:\Users\Gabo\Desktop\JARVIS\output.wav"
)

print("Audio generado.")