import math
import random
import sys
import pygame

# Initialize Pygame
pygame.init()

# Screen Setup
WIDTH, HEIGHT = 1000, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Modern Golden Constellation Grid")
clock = pygame.time.Clock()

# Colors
WHITE = (255, 255, 255)
GOLD_MAIN = (212, 175, 55)
GOLD_BRIGHT = (255, 215, 0)
GOLD_SOFT = (240, 210, 115)

# ----------------------------------------------------
# Node / Particle Class
# ----------------------------------------------------
class Node:
    def __init__(self):
        self.x = random.uniform(0, WIDTH)
        self.y = random.uniform(0, HEIGHT)
        self.radius = random.uniform(2.5, 4.5)
        self.vx = random.uniform(-0.8, 0.8)
        self.vy = random.uniform(-0.8, 0.8)
        self.base_color = GOLD_MAIN

    def update(self):
        self.x += self.vx
        self.y += self.vy

        # Bounce off edges smoothly
        if self.x <= 0 or self.x >= WIDTH:
            self.vx *= -1
        if self.y <= 0 or self.y >= HEIGHT:
            self.vy *= -1

    def draw(self, surface):
        s = pygame.Surface((int(self.radius * 4), int(self.radius * 4)), pygame.SRCALPHA)
        # Soft outer glow
        pygame.draw.circle(s, (*GOLD_SOFT, 80), (int(self.radius * 2), int(self.radius * 2)), int(self.radius * 2))
        # Solid center core
        pygame.draw.circle(s, (*GOLD_BRIGHT, 230), (int(self.radius * 2), int(self.radius * 2)), int(self.radius))
        surface.blit(s, (self.x - self.radius * 2, self.y - self.radius * 2))

# ----------------------------------------------------
# Click Explosion Spark Particle
# ----------------------------------------------------
class ClickSpark:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(2, 6)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.radius = random.uniform(1.5, 3.0)
        self.alpha = 255
        self.decay = random.uniform(6, 12)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.alpha -= self.decay

    def draw(self, surface):
        if self.alpha > 0:
            s = pygame.Surface((int(self.radius * 2), int(self.radius * 2)), pygame.SRCALPHA)
            pygame.draw.circle(s, (*GOLD_BRIGHT, int(self.alpha)), (int(self.radius), int(self.radius)), int(self.radius))
            surface.blit(s, (self.x - self.radius, self.y - self.radius))

# Setup Particles
nodes = [Node() for _ in range(65)]
sparks = []

# Main Loop
running = True
CONNECT_DISTANCE = 110
MOUSE_CONNECT_DIST = 160

while running:
    clock.tick(60)
    screen.fill(WHITE)

    mouse_x, mouse_y = pygame.mouse.get_pos()

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Generate explosion sparks on click
            for _ in range(25):
                sparks.append(ClickSpark(mouse_x, mouse_y))

    # Update & Draw Nodes
    for i in range(len(nodes)):
        node_a = nodes[i]
        node_a.update()

        # Connect Node with Mouse Cursor
        dist_m = math.hypot(node_a.x - mouse_x, node_a.y - mouse_y)
        if dist_m < MOUSE_CONNECT_DIST:
            alpha = int(255 * (1 - (dist_m / MOUSE_CONNECT_DIST)))
            line_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(line_surface, (*GOLD_BRIGHT, alpha), (node_a.x, node_a.y), (mouse_x, mouse_y), 2)
            screen.blit(line_surface, (0, 0))

        # Connect Nearby Nodes to each other
        for j in range(i + 1, len(nodes)):
            node_b = nodes[j]
            dist = math.hypot(node_a.x - node_b.x, node_a.y - node_b.y)

            if dist < CONNECT_DISTANCE:
                alpha = int(140 * (1 - (dist / CONNECT_DISTANCE)))
                line_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                pygame.draw.line(line_surface, (*GOLD_MAIN, alpha), (node_a.x, node_a.y), (node_b.x, node_b.y), 1)
                screen.blit(line_surface, (0, 0))

        node_a.draw(screen)

    # Update & Draw Click Sparks
    for spark in sparks[:]:
        spark.update()
        if spark.alpha <= 0:
            sparks.remove(spark)
        else:
            spark.draw(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()