import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Reshape
from tensorflow.keras.preprocessing.image import array_to_img
from PIL import Image
import string
import random

characters = string.ascii_uppercase + string.digits
img_width, img_height = 100, 40
text_length = 5

# Modelo gerador simples (rede neural feed-forward)
def build_generator():
    model = Sequential([
        Dense(256, input_dim=text_length*len(characters), activation='relu'),
        Dense(img_width*img_height, activation='sigmoid'),
        Reshape((img_height, img_width))
    ])
    return model

generator = build_generator()

# Função para codificar texto em vetor one-hot
def text_to_vector(text):
    vec = np.zeros((text_length, len(characters)))
    for i, c in enumerate(text):
        idx = characters.index(c)
        vec[i, idx] = 1
    return vec.flatten()

# Gerar captcha com deep learning
def generate_captcha():
    captcha_text = ''.join(random.choices(characters, k=text_length))
    vec = text_to_vector(captcha_text)
    img_array = generator.predict(np.array([vec]))[0]  # saída da rede
    img_array = (img_array*255).astype(np.uint8)
    img = Image.fromarray(img_array)
    return captcha_text, img