"""
Bomberman en Python
====================================

Cómo jugar:
- Flechas del teclado: mover al jugador
- Barra espaciadora: colocar una bomba
- Objetivo: destruye todos los bloques débiles o elimina a los enemigos
  sin que una explosión te alcance.

Instalación:
    pip install pygame

Ejecución:
    python bomberman.py
"""

import pygame
import random
import sys
import os

# Configuración general
TAMAÑO_CELDA = 40
COLUMNAS = 15
FILAS = 13
ANCHO = COLUMNAS * TAMAÑO_CELDA
ALTO = FILAS * TAMAÑO_CELDA + 60  # espacio extra para el HUD
FPS = 60

# Tipos de celda
VACIO = 0
PARED = 1       # indestructible
BLOQUE = 2      # destructible

# Colores
COLOR_BG = (20, 20, 20)
COLOR_FONDO = (30, 30, 30)
COLOR_VACIO = (60, 160, 60)
COLOR_PARED = (90, 90, 90)
COLOR_BLOQUE = (150, 100, 60)
COLOR_JUGADOR = (60, 120, 220)
COLOR_ENEMIGO = (200, 50, 50)
COLOR_BOMBA = (20, 20, 20)
COLOR_EXPLOSION = (255, 140, 0)
COLOR_TEXTO = (255, 255, 255)
COLOR_POTENCIACION = (255, 215, 0)
COLOR_HUD = (100, 100, 100)

TEMPORIZADOR_BOMBA = 2000       # ms hasta que explota la bomba
TIEMPO_EXPLOSION = 400        # ms que dura visible la explosión
VELOCIDAD_JUGADOR_MS = 130  # ms entre movimientos del jugador (grid-based)
VELOCIDAD_ENEMIGAS_MS = 400    # ms entre movimientos del enemigo

# Cargar y escalar imágenes
def cargar_imagen(nombre_archivo, ancho, alto):
    path = os.path.join("images", nombre_archivo)
    if os.path.exists(path):
        imagen = pygame.image.load(path).convert_alpha()
        return pygame.transform.scale(imagen, (ancho, alto))
    else:
        print(f"Advertencia: No se encontró la imagen en '{path}'. Se usará el dibujo predeterminado o color de respaldo.")
        return None

# Utilidades de mapa
def generar_mapa():
    """Genera el mapa del nivel: bordes indestructibles, pilares fijos
    y bloques destructibles aleatorios, dejando libre la zona de spawn."""
    mapa = [[VACIO for _ in range(COLUMNAS)] for _ in range(FILAS)]

    for x in range(COLUMNAS):
        for y in range(FILAS):
            if x == 0 or y == 0 or x == COLUMNAS - 1 or y == FILAS - 1:
                mapa[y][x] = PARED
            elif x % 2 == 0 and y % 2 == 0:
                mapa[y][x] = PARED

    # zonas de spawn libres (jugador arriba-izquierda, enemigos en otras esquinas)
    zonas_libres = {(1, 1), (1, 2), (2, 1),
                    (COLUMNAS - 2, FILAS - 2), (COLUMNAS - 3, FILAS - 2), (COLUMNAS - 2, FILAS - 3),
                    (COLUMNAS - 2, 1), (COLUMNAS - 3, 1), (COLUMNAS - 2, 2),
                    (1, FILAS - 2), (1, FILAS - 3), (2, FILAS - 2)}

    for y in range(1, FILAS - 1):
        for x in range(1, COLUMNAS - 1):
            if mapa[y][x] == VACIO and (x, y) not in zonas_libres:
                if random.random() < 0.6:
                    mapa[y][x] = BLOQUE

    return mapa

def es_transitable(mapa, x, y):
    if 0 <= x < COLUMNAS and 0 <= y < FILAS:
        return mapa[y][x] == VACIO
    return False

# Clases del juego
class Bomba:
    def __init__(self, x, y, alcance, dueño):
        self.x = x
        self.y = y
        self.alcance = alcance
        self.dueño = dueño
        self.tiempo_colocada = pygame.time.get_ticks()
        self.explotada = False

    def debe_explotar(self):
        return pygame.time.get_ticks() - self.tiempo_colocada >= TEMPORIZADOR_BOMBA

class Explosion:
    def __init__(self, celdas):
        self.celdas = celdas  # lista de (x, y) afectadas
        self.tiempo_inicio = pygame.time.get_ticks()

    def sigue_activa(self):
        return pygame.time.get_ticks() - self.tiempo_inicio < TIEMPO_EXPLOSION

class Entidad:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vivo = True

class Jugador(Entidad):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.max_bombas = 1
        self.bombas_activas = 0
        self.alcance = 2
        self.ultimo_movimiento = 0

class Enemigo(Entidad):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.ultimo_movimiento = 0
        self.direccion = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])

# Juego principal
class Juego:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()  # Inicializar el mezclador de audio
        self.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        pygame.display.set_caption("Bomberman - Python")
        self.reloj = pygame.time.Clock()
        self.fuente = pygame.font.SysFont("arial", 24)
        self.fuente_grande = pygame.font.SysFont("arial", 48, bold=True)
        
        # imagenes de objetos y personajes
        self.player_img = cargar_imagen("astro.png", TAMAÑO_CELDA - 8, TAMAÑO_CELDA - 8)
        self.enemy_img = cargar_imagen("marciano.png", TAMAÑO_CELDA - 8, TAMAÑO_CELDA - 8)
        self.bomb_img = cargar_imagen("bonba.png", TAMAÑO_CELDA - 6, TAMAÑO_CELDA - 6)
        self.block_img = cargar_imagen("blok_rompe.png", TAMAÑO_CELDA, TAMAÑO_CELDA)
        self.pared_img = cargar_imagen("pared.png", TAMAÑO_CELDA, TAMAÑO_CELDA)

        # ---------------- CARGAR SONIDOS ---------------- #
        
        # 1. Música de fondo
        self.ruta_musica = None
        for ext in [".mp3", ".wav", ".ogg"]:
            posible_ruta = os.path.join("sonidos", f"fondo{ext}")
            if os.path.exists(posible_ruta):
                self.ruta_musica = posible_ruta
                break

        if self.ruta_musica:
            pygame.mixer.music.load(self.ruta_musica)
        else:
            print("Advertencia: No se encontró el archivo de audio 'fondo' en la carpeta 'sonidos/'.")

        # 2. Efecto de sonido de movimiento
        self.sonido_movimiento = None
        for ext in [".wav", ".mp3", ".ogg"]:
            posible_ruta = os.path.join("sonidos", f"mobimiento{ext}")
            if os.path.exists(posible_ruta):
                self.sonido_movimiento = pygame.mixer.Sound(posible_ruta)
                break
                
        if not self.sonido_movimiento:
            print("Advertencia: No se encontró el archivo de audio 'mobimiento' en la carpeta 'sonidos/'.")

        # 3. Efecto de sonido de explosión
        self.sonido_explosion = None
        for ext in [".wav", ".mp3", ".ogg"]:
            posible_ruta = os.path.join("sonidos", f"explosion{ext}")
            if os.path.exists(posible_ruta):
                self.sonido_explosion = pygame.mixer.Sound(posible_ruta)
                break

        if not self.sonido_explosion:
            print("Advertencia: No se encontró el archivo de audio 'explosion' en la carpeta 'sonidos/'.")

        # ------------------------------------------------ #

        self.reiniciar()

    def reiniciar(self):
        self.mapa = generar_mapa()
        self.jugador = Jugador(1, 1)
        self.enemigos = [
            Enemigo(COLUMNAS - 2, FILAS - 2),
            Enemigo(COLUMNAS - 2, 1),
            Enemigo(1, FILAS - 2),
        ]
        self.bombas = []
        self.explosiones = []
        self.powerups = {}  # (x, y) -> tipo
        self.juego_terminado = False
        self.gano = False

        # Iniciar reproducción de la música en bucle infinito (-1)
        if self.ruta_musica:
            pygame.mixer.music.play(-1)

    # Lógica de bombas y explosiones
    def colocar_bomba(self, entidad):
        if isinstance(entidad, Jugador):
            if entidad.bombas_activas >= entidad.max_bombas:
                return
            entidad.bombas_activas += 1
        pos_ocupada = any(b.x == entidad.x and b.y == entidad.y for b in self.bombas)
        if not pos_ocupada:
            alcance = entidad.alcance if isinstance(entidad, Jugador) else 1
            self.bombas.append(Bomba(entidad.x, entidad.y, alcance, entidad))

    def procesar_bombas(self):
        for bomba in list(self.bombas):
            if bomba.debe_explotar() and not bomba.explotada:
                self.explotar_bomba(bomba)

    def explotar_bomba(self, bomba):
        bomba.explotada = True
        self.bombas.remove(bomba)
        if isinstance(bomba.dueño, Jugador):
            bomba.dueño.bombas_activas = max(0, bomba.dueño.bombas_activas - 1)

        # REPRODUCIR SONIDO DE EXPLOSIÓN
        if self.sonido_explosion:
            self.sonido_explosion.play()

        celdas_afectadas = [(bomba.x, bomba.y)]
        direcciones = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        for dx, dy in direcciones:
            for paso in range(1, bomba.alcance + 1):
                nx, ny = bomba.x + dx * paso, bomba.y + dy * paso
                if not (0 <= nx < COLUMNAS and 0 <= ny < FILAS):
                    break
                celda = self.mapa[ny][nx]
                if celda == PARED:
                    break
                celdas_afectadas.append((nx, ny))
                if celda == BLOQUE:
                    self.mapa[ny][nx] = VACIO
                    if random.random() < 0.25:
                        self.powerups[(nx, ny)] = "bomba_extra" if random.random() < 0.5 else "alcance"
                    break

        self.explosiones.append(Explosion(celdas_afectadas))

        # reacción en cadena con otras bombas
        for otra in list(self.bombas):
            if (otra.x, otra.y) in celdas_afectadas and not otra.explotada:
                self.explotar_bomba(otra)

        # daño a entidades
        if (self.jugador.x, self.jugador.y) in celdas_afectadas:
            self.jugador.vivo = False

        for enemigo in self.enemigos:
            if enemigo.vivo and (enemigo.x, enemigo.y) in celdas_afectadas:
                enemigo.vivo = False

    def limpiar_explosiones(self):
        self.explosiones = [e for e in self.explosiones if e.sigue_activa()]

    def celdas_peligrosas(self):
        peligro = set()
        for exp in self.explosiones:
            peligro.update(exp.celdas)
        return peligro

    # Movimiento
    def mover_jugador(self, dx, dy):
        ahora = pygame.time.get_ticks()
        if ahora - self.jugador.ultimo_movimiento < VELOCIDAD_JUGADOR_MS:
            return
        nx, ny = self.jugador.x + dx, self.jugador.y + dy
        bomba_en_camino = any(b.x == nx and b.y == ny for b in self.bombas)
        
        # Si la casilla es válida y se puede mover
        if es_transitable(self.mapa, nx, ny) and not bomba_en_camino:
            self.jugador.x, self.jugador.y = nx, ny
            self.jugador.ultimo_movimiento = ahora
            self.recoger_powerup(nx, ny)
            
            # REPRODUCIR SONIDO DE MOVIMIENTO
            if self.sonido_movimiento:
                self.sonido_movimiento.play()

    def recoger_powerup(self, x, y):
        tipo = self.powerups.pop((x, y), None)
        if tipo == "bomba_extra":
            self.jugador.max_bombas += 1
        elif tipo == "alcance":
            self.jugador.alcance += 1

    def mover_enemigos(self):
        ahora = pygame.time.get_ticks()
        for enemigo in self.enemigos:
            if not enemigo.vivo:
                continue
            if ahora - enemigo.ultimo_movimiento < VELOCIDAD_ENEMIGAS_MS:
                continue
            enemigo.ultimo_movimiento = ahora

            dx, dy = enemigo.direccion
            nx, ny = enemigo.x + dx, enemigo.y + dy
            bomba_en_camino = any(b.x == nx and b.y == ny for b in self.bombas)

            if not es_transitable(self.mapa, nx, ny) or bomba_en_camino:
                opciones = [(1, 0), (-1, 0), (0, 1), (0, -1)]
                random.shuffle(opciones)
                movido = False
                for ndx, ndy in opciones:
                    tx, ty = enemigo.x + ndx, enemigo.y + ndy
                    ocupado = any(b.x == tx and b.y == ty for b in self.bombas)
                    if es_transitable(self.mapa, tx, ty) and not ocupado:
                        enemigo.direccion = (ndx, ndy)
                        enemigo.x, enemigo.y = tx, ty
                        movido = True
                        break
                if not movido:
                    continue
            else:
                enemigo.x, enemigo.y = nx, ny

            if enemigo.x == self.jugador.x and enemigo.y == self.jugador.y:
                self.jugador.vivo = False

    # Condiciones de fin de partida
    def verificar_estado(self):
        if not self.jugador.vivo:
            self.juego_terminado = True
            self.gano = False
            pygame.mixer.music.stop()  # Detener la música al perder
        elif all(not e.vivo for e in self.enemigos):
            self.juego_terminado = True
            self.gano = True
            pygame.mixer.music.stop()  # Detener la música al ganar

    # Dibujado
    def dibujar(self):
        self.pantalla.fill(COLOR_BG)
        peligro = self.celdas_peligrosas()

        for y in range(FILAS):
            for x in range(COLUMNAS):
                rect = pygame.Rect(x * TAMAÑO_CELDA, y * TAMAÑO_CELDA, TAMAÑO_CELDA, TAMAÑO_CELDA)
                celda = self.mapa[y][x]
                if celda == PARED:
                    pygame.draw.rect(self.pantalla, COLOR_PARED, rect)
                elif celda == BLOQUE: 
                    if self.block_img:
                        self.pantalla.blit(self.block_img, (x * TAMAÑO_CELDA, y * TAMAÑO_CELDA))
                    else:
                        pygame.draw.rect(self.pantalla, COLOR_BLOQUE, rect)
                else:
                    pygame.draw.rect(self.pantalla, COLOR_VACIO, rect)
                pygame.draw.rect(self.pantalla, COLOR_BG, rect, 1)

                if (x, y) in self.powerups:
                    centro = rect.center
                    pygame.draw.circle(self.pantalla, COLOR_POTENCIACION, centro, TAMAÑO_CELDA // 4)

                if (x, y) in peligro:
                    s = pygame.Surface((TAMAÑO_CELDA, TAMAÑO_CELDA))
                    s.set_alpha(180)
                    s.fill(COLOR_EXPLOSION)
                    self.pantalla.blit(s, rect.topleft)

        # Dibujar Bombas
        for bomba in self.bombas:
            px = bomba.x * TAMAÑO_CELDA + 3
            py = bomba.y * TAMAÑO_CELDA + 3
            if self.bomb_img:
                self.pantalla.blit(self.bomb_img, (px, py))
            else:
                centro = (bomba.x * TAMAÑO_CELDA + TAMAÑO_CELDA // 2, bomba.y * TAMAÑO_CELDA + TAMAÑO_CELDA // 2)
                pygame.draw.circle(self.pantalla, COLOR_BOMBA, centro, TAMAÑO_CELDA // 3)

        # Dibujar Enemigos
        for enemigo in self.enemigos:
            if enemigo.vivo:
                px = enemigo.x * TAMAÑO_CELDA + 4
                py = enemigo.y * TAMAÑO_CELDA + 4
                if self.enemy_img:
                    self.pantalla.blit(self.enemy_img, (px, py))
                else:
                    rect = pygame.Rect(px, py, TAMAÑO_CELDA - 8, TAMAÑO_CELDA - 8)
                    pygame.draw.rect(self.pantalla, COLOR_ENEMIGO, rect, border_radius=6)

        # Dibujar Jugador
        if self.jugador.vivo:
            px = self.jugador.x * TAMAÑO_CELDA + 4
            py = self.jugador.y * TAMAÑO_CELDA + 4
            if self.player_img:
                self.pantalla.blit(self.player_img, (px, py))
            else:
                rect = pygame.Rect(px, py, TAMAÑO_CELDA - 8, TAMAÑO_CELDA - 8)
                pygame.draw.rect(self.pantalla, COLOR_JUGADOR, rect, border_radius=6)

        # HUD
        hud_y = FILAS * TAMAÑO_CELDA
        pygame.draw.rect(self.pantalla, COLOR_HUD, (0, hud_y, ANCHO, 60))
        texto = self.fuente.render(
            f"Bombas: {self.jugador.max_bombas}   Alcance: {self.jugador.alcance}   "
            f"Enemigos vivos: {sum(1 for e in self.enemigos if e.vivo)}",
            True, COLOR_TEXTO)
        self.pantalla.blit(texto, (10, hud_y + 18))

        if self.juego_terminado:
            mensaje = "¡GANASTE!" if self.gano else "GAME OVER"
            color = (80, 220, 80) if self.gano else (220, 60, 60)
            texto_final = self.fuente_grande.render(mensaje, True, color)
            sombra = self.fuente_grande.render(mensaje, True, (0, 0, 0))
            x = ANCHO // 2 - texto_final.get_width() // 2
            y = ALTO // 2 - texto_final.get_height() // 2
            self.pantalla.blit(sombra, (x + 3, y + 3))
            self.pantalla.blit(texto_final, (x, y))
            sub = self.fuente.render("Presiona R para reiniciar", True, COLOR_TEXTO)
            self.pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, y + 60))

        pygame.display.flip()

    # Bucle principal
    def ejecutar(self):
        while True:
            for evento in pygame.event.get():
                if evento.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if evento.type == pygame.KEYDOWN:
                    if evento.key == pygame.K_r and self.juego_terminado:
                        self.reiniciar()
                    if not self.juego_terminado:
                        if evento.key == pygame.K_SPACE:
                            self.colocar_bomba(self.jugador)

            if not self.juego_terminado:
                teclas = pygame.key.get_pressed()
                if teclas[pygame.K_UP]:
                    self.mover_jugador(0, -1)
                elif teclas[pygame.K_DOWN]:
                    self.mover_jugador(0, 1)
                elif teclas[pygame.K_LEFT]:
                    self.mover_jugador(-1, 0)
                elif teclas[pygame.K_RIGHT]:
                    self.mover_jugador(1, 0)

                self.mover_enemigos()
                self.procesar_bombas()
                self.limpiar_explosiones()
                self.verificar_estado()

            self.dibujar()
            self.reloj.tick(FPS)


if __name__ == "__main__":
    Juego().ejecutar()
