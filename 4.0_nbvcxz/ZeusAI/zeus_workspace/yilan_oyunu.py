import pygame
import sys
import time
import random

pygame.init()

width = 800
height = 600
background_color = (0, 0, 0)
snake_color = (0, 255, 0)
food_color = (255, 0, 0)

screen = pygame.display.set_mode((width, height))
pygame.display.set_caption('Yılan Oyunu')

clock = pygame.time.Clock()

snake = [(200, 200), (220, 200), (240, 200)]
food = (400, 300)
direction = 'RIGHT'

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP and direction != 'DOWN':
                direction = 'UP'
            elif event.key == pygame.K_DOWN and direction != 'UP':
                direction = 'DOWN'
            elif event.key == pygame.K_LEFT and direction != 'RIGHT':
                direction = 'LEFT'
            elif event.key == pygame.K_RIGHT and direction != 'LEFT':
                direction = 'RIGHT'

    screen.fill(background_color)

    for pos in snake:
        pygame.draw.rect(screen, snake_color, pygame.Rect(pos[0], pos[1], 20, 20))

    pygame.draw.rect(screen, food_color, pygame.Rect(food[0], food[1], 20, 20))

    if direction == 'UP':
        new_head = (snake[-1][0], snake[-1][1] - 20)
    elif direction == 'DOWN':
        new_head = (snake[-1][0], snake[-1][1] + 20)
    elif direction == 'LEFT':
        new_head = (snake[-1][0] - 20, snake[-1][1])
    elif direction == 'RIGHT':
        new_head = (snake[-1][0] + 20, snake[-1][1])

    snake.append(new_head)

    if snake[-1] == food:
        food = (random.randint(0, width - 20) // 20 * 20, random.randint(0, height - 20) // 20 * 20)
    else:
        snake.pop(0)

    if (snake[-1][0] < 0 or snake[-1][0] >= width or
        snake[-1][1] < 0 or snake[-1][1] >= height or
        snake[-1] in snake[:-1]):
        pygame.quit()
        sys.exit()

    pygame.display.flip()
    clock.tick(10)