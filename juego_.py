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

# Configuración general
TAMAÑO_CELDA = 40
FPS = 60

# Configuración de niveles 
config_niveles = {
    1: {"columnas": 13, "filas": 11, "enemigos": 3},
    2: {"columnas": 15, "filas": 13, "enemigos": 5},
    3: {"columnas": 17, "filas": 15, "enemigos": 7}
}

# Tipos de celda
VACIO = 0
PARED = 1       # no se rompe 
BLOQUE = 2     

# Colores
COLOR_BG = (20, 20, 20)
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
TIEMPO_EXPLOSION = 400          # ms que dura visible la explosión
VELOCIDAD_JUGADOR_MS = 130      # ms entre movimientos del jugador
VELOCIDAD_ENEMIGAS_MS = 400     # ms entre movimientos del enemigo


# Utilidades de mapa
def generar_mapa(columnas, filas):
    """Genera el mapa del nivel: bordes indestructibles, pilares fijos
    y bloques destructibles aleatorios, dejando libre la zona de spawn."""
    mapa = [[VACIO for _ in range(columnas)] for _ in range(filas)]

    for x in range(columnas):
        for y in range(filas):
            if x == 0 or y == 0 or x == columnas - 1 or y == filas - 1:
                mapa[y][x] = PARED
            elif x % 2 == 0 and y % 2 == 0:
                mapa[y][x] = PARED

    # Zonas de spawn libres
    zonas_libres = {
        (1, 1), (1, 2), (2, 1),
        (columnas - 2, filas - 2), (columnas - 3, filas - 2), (columnas - 2, filas - 3),
        (columnas - 2, 1), (columnas - 3, 1), (columnas - 2, 2),
        (1, filas - 2), (1, filas - 3), (2, filas - 2)
    }

    for y in range(1, filas - 1):
        for x in range(1, columnas - 1):
            if mapa[y][x] == VACIO and (x, y) not in zonas_libres:
                if random.random() < 0.6:
                    mapa[y][x] = BLOQUE

    return mapa


def es_transitable(mapa, x, y, columnas, filas):
    if 0 <= x < columnas and 0 <= y < filas:
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
        self.nivel_actual = 3
        self.cargar_nivel(self.nivel_actual)
        pygame.display.set_caption("Bomberman - Python")
        self.reloj = pygame.time.Clock()
        self.fuente = pygame.font.SysFont("arial", 24)
        self.fuente_grande = pygame.font.SysFont("arial", 48, bold=True)

    def cargar_nivel(self, num_nivel):
        self.nivel_actual = num_nivel
        cfg = config_niveles[num_nivel]
        self.columnas = cfg["columnas"]
        self.filas = cfg["filas"]
        self.cant_enemigos = cfg["enemigos"]
        
        self.ancho_pantalla = self.columnas * TAMAÑO_CELDA
        self.alto_pantalla = (self.filas * TAMAÑO_CELDA) + 60
        self.pantalla = pygame.display.set_mode((self.ancho_pantalla, self.alto_pantalla))
        self.reiniciar()

    def reiniciar(self):
        self.mapa = generar_mapa(self.columnas, self.filas)
        self.jugador = Jugador(1, 1)
        
        # Generar posiciones esquinas para enemigos
        esquinas = [
            (self.columnas - 2, self.filas - 2),
            (self.columnas - 2, 1),
            (1, self.filas - 2)
        ]
        self.enemigos = [Enemigo(x, y) for x, y in esquinas[:self.cant_enemigos]]
        
        self.bombas = []
        self.explosiones = []
        self.powerups = {}
        self.juego_terminado = False
        self.gano = False

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

        celdas_afectadas = [(bomba.x, bomba.y)]
        direcciones = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        for dx, dy in direcciones:
            for paso in range(1, bomba.alcance + 1):
                nx, ny = bomba.x + dx * paso, bomba.y + dy * paso
                if not (0 <= nx < self.columnas and 0 <= ny < self.filas):
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

        for otra in list(self.bombas):
            if (otra.x, otra.y) in celdas_afectadas and not otra.explotada:
                self.explotar_bomba(otra)

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

    def mover_jugador(self, dx, dy):
        ahora = pygame.time.get_ticks()
        if ahora - self.jugador.ultimo_movimiento < VELOCIDAD_JUGADOR_MS:
            return
        nx, ny = self.jugador.x + dx, self.jugador.y + dy
        bomba_en_camino = any(b.x == nx and b.y == ny for b in self.bombas)
        if es_transitable(self.mapa, nx, ny, self.columnas, self.filas) and not bomba_en_camino:
            self.jugador.x, self.jugador.y = nx, ny
            self.jugador.ultimo_movimiento = ahora
            self.recoger_powerup(nx, ny)

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

            if not es_transitable(self.mapa, nx, ny, self.columnas, self.filas) or bomba_en_camino:
                opciones = [(1, 0), (-1, 0), (0, 1), (0, -1)]
                random.shuffle(opciones)
                movido = False
                for ndx, ndy in opciones:
                    tx, ty = enemigo.x + ndx, enemigo.y + ndy
                    ocupado = any(b.x == tx and b.y == ty for b in self.bombas)
                    if es_transitable(self.mapa, tx, ty, self.columnas, self.filas) and not ocupado:
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

    def verificar_estado(self):
        if not self.jugador.vivo:
            self.juego_terminado = True
            self.gano = False
        elif all(not e.vivo for e in self.enemigos):
            self.juego_terminado = True
            self.gano = True

    def dibujar(self):
        self.pantalla.fill(COLOR_BG)
        peligro = self.celdas_peligrosas()

        for y in range(self.filas):
            for x in range(self.columnas):
                rect = pygame.Rect(x * TAMAÑO_CELDA, y * TAMAÑO_CELDA, TAMAÑO_CELDA, TAMAÑO_CELDA)
                celda = self.mapa[y][x]
                if celda == PARED:
                    pygame.draw.rect(self.pantalla, COLOR_PARED, rect)
                elif celda == BLOQUE:
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

        # Dibujar bombas (Círculo negro)
        for bomba in self.bombas:
            centro = (bomba.x * TAMAÑO_CELDA + TAMAÑO_CELDA // 2, bomba.y * TAMAÑO_CELDA + TAMAÑO_CELDA // 2)
            pygame.draw.circle(self.pantalla, COLOR_BOMBA, centro, TAMAÑO_CELDA // 3)

        # Dibujar enemigos (Cuadrado rojo redondeado)
        for enemigo in self.enemigos:
            if enemigo.vivo:
                px = enemigo.x * TAMAÑO_CELDA + 4
                py = enemigo.y * TAMAÑO_CELDA + 4
                rect = pygame.Rect(px, py, TAMAÑO_CELDA - 8, TAMAÑO_CELDA - 8)
                pygame.draw.rect(self.pantalla, COLOR_ENEMIGO, rect, border_radius=6)

        # Dibujar jugador (Cuadrado azul redondeado)
        if self.jugador.vivo:
            px = self.jugador.x * TAMAÑO_CELDA + 4
            py = self.jugador.y * TAMAÑO_CELDA + 4
            rect = pygame.Rect(px, py, TAMAÑO_CELDA - 8, TAMAÑO_CELDA - 8)
            pygame.draw.rect(self.pantalla, COLOR_JUGADOR, rect, border_radius=6)

        # HUD
        hud_y = self.filas * TAMAÑO_CELDA
        pygame.draw.rect(self.pantalla, COLOR_HUD, (0, hud_y, self.ancho_pantalla, 60))
        texto = self.fuente.render(
            f"Bombas: {self.jugador.max_bombas}   Alcance: {self.jugador.alcance}   "
            f"Enemigos: {sum(1 for e in self.enemigos if e.vivo)}",
            True, COLOR_TEXTO)
        self.pantalla.blit(texto, (10, hud_y + 18))

        if self.juego_terminado:
            mensaje = "¡GANASTE!" if self.gano else "GAME OVER"
            color = (80, 220, 80) if self.gano else (220, 60, 60)
            texto_final = self.fuente_grande.render(mensaje, True, color)
            sombra = self.fuente_grande.render(mensaje, True, (0, 0, 0))
            x = self.ancho_pantalla // 2 - texto_final.get_width() // 2
            y = (self.filas * TAMAÑO_CELDA) // 2 - texto_final.get_height() // 2
            self.pantalla.blit(sombra, (x + 3, y + 3))
            self.pantalla.blit(texto_final, (x, y))
            sub = self.fuente.render("Presiona R para reiniciar", True, COLOR_TEXTO)
            self.pantalla.blit(sub, (self.ancho_pantalla // 2 - sub.get_width() // 2, y + 60))

        pygame.display.flip()

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