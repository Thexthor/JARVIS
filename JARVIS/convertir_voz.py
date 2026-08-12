from pydub import AudioSegment

entrada = r"C:\Users\Gabo\Desktop\JARVIS\voices\voz.mp3"
salida = r"C:\Users\Gabo\Desktop\JARVIS\voices\voz.wav"

audio = AudioSegment.from_file(entrada)
audio = audio.set_channels(1)
audio = audio.set_frame_rate(22050)
audio.export(salida, format="wav")

print("Convertido a voz.wav")