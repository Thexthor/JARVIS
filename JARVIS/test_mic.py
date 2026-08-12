import sounddevice as sd
from scipy.io.wavfile import write

duracion = 5
frecuencia = 16000

print("Grabando 5 segundos...")
audio = sd.rec(
    int(duracion * frecuencia),
    samplerate=frecuencia,
    channels=1,
    dtype="int16"
)

sd.wait()

write("test_audio.wav", frecuencia, audio)

print("Grabación guardada como test_audio.wav")