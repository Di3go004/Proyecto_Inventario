"""
Generación de contraseñas fuertes.

Vive aparte porque lo usan dos caminos distintos: la pantalla de usuarios
(que la muestra una vez al crear a alguien) y el comando `cambiar_clave`
(para rotarla desde la terminal si nadie puede entrar al sistema).
"""

import secrets

# Sin caracteres que se confunden al dictarlos o copiarlos a mano (l/1/I,
# O/0) y sin comillas, que rompen al pegarlos en una terminal.
ALFABETO = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789@#%*-_+='

LARGO_POR_DEFECTO = 16


def generar_clave(largo=LARGO_POR_DEFECTO):
    return ''.join(secrets.choice(ALFABETO) for _ in range(largo))
