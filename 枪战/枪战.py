import math
import random
import sys

import pygame


WIDTH, HEIGHT = 960, 540
FPS = 60

PLAYER_SIZE = 32
PLAYER_SPEED = 320  # px/s
PLAYER_MAX_HP = 5

BULLET_RADIUS = 4
BULLET_SPEED = 760  # px/s
FIRE_COOLDOWN = 0.12  # s

ENEMY_RADIUS = 16
ENEMY_BASE_SPEED = 110  # px/s
SPAWN_BASE_INTERVAL = 1.0  # s


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def vec_length(x, y):
    return math.hypot(x, y)


def normalize(x, y):
    l = vec_length(x, y)
    if l == 0:
        return 0.0, 0.0
    return x / l, y / l


def circle_hit(cx, cy, cr, rx, ry, rr):
    dx = cx - rx
    dy = cy - ry
    return dx * dx + dy * dy <= (cr + rr) ** 2


class Player:
    def __init__(self):
        self.x = WIDTH / 2
        self.y = HEIGHT / 2
        self.hp = PLAYER_MAX_HP
        self.invuln = 0.0  # s

    @property
    def rect(self):
        return pygame.Rect(int(self.x - PLAYER_SIZE / 2), int(self.y - PLAYER_SIZE / 2), PLAYER_SIZE, PLAYER_SIZE)

    def update(self, dt, keys):
        vx = (1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)
        vy = (1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0)
        vx, vy = normalize(vx, vy)
        self.x += vx * PLAYER_SPEED * dt
        self.y += vy * PLAYER_SPEED * dt
        self.x = clamp(self.x, PLAYER_SIZE / 2, WIDTH - PLAYER_SIZE / 2)
        self.y = clamp(self.y, PLAYER_SIZE / 2, HEIGHT - PLAYER_SIZE / 2)

        if self.invuln > 0:
            self.invuln = max(0.0, self.invuln - dt)

    def damage(self, amount=1):
        if self.invuln > 0:
            return False
        self.hp -= amount
        self.invuln = 0.6
        return True


class Bullet:
    def __init__(self, x, y, dx, dy):
        self.x = x
        self.y = y
        self.dx, self.dy = normalize(dx, dy)

    def update(self, dt):
        self.x += self.dx * BULLET_SPEED * dt
        self.y += self.dy * BULLET_SPEED * dt

    def offscreen(self):
        return self.x < -50 or self.x > WIDTH + 50 or self.y < -50 or self.y > HEIGHT + 50


class Enemy:
    def __init__(self, x, y, speed):
        self.x = x
        self.y = y
        self.speed = speed

    def update(self, dt, player_x, player_y):
        dx = player_x - self.x
        dy = player_y - self.y
        nx, ny = normalize(dx, dy)
        self.x += nx * self.speed * dt
        self.y += ny * self.speed * dt


def spawn_enemy(difficulty):
    # 从屏幕四周随机生成
    side = random.choice(["top", "bottom", "left", "right"])
    if side == "top":
        x, y = random.uniform(0, WIDTH), -ENEMY_RADIUS * 2
    elif side == "bottom":
        x, y = random.uniform(0, WIDTH), HEIGHT + ENEMY_RADIUS * 2
    elif side == "left":
        x, y = -ENEMY_RADIUS * 2, random.uniform(0, HEIGHT)
    else:
        x, y = WIDTH + ENEMY_RADIUS * 2, random.uniform(0, HEIGHT)

    speed = ENEMY_BASE_SPEED + difficulty * 10
    return Enemy(x, y, speed)


def draw_text(screen, font, text, x, y, color=(240, 240, 240), center=False):
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(surf, rect)


def main():
    pygame.init()
    pygame.display.set_caption("Python 枪战小游戏（Pygame）")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.Font("simhei.ttf", 22)
    big_font = pygame.font.Font("simhei.ttf", 48)

    def reset():
        return {
            "player": Player(),
            "bullets": [],
            "enemies": [],
            "score": 0,
            "time": 0.0,
            "fire_cd": 0.0,
            "spawn_cd": SPAWN_BASE_INTERVAL,
            "spawn_timer": 0.0,
            "game_over": False,
        }

    state = reset()

    while True:
        dt = clock.tick(FPS) / 1000.0
        state["time"] += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit(0)
                if state["game_over"] and event.key == pygame.K_r:
                    state = reset()

        keys = pygame.key.get_pressed()
        mouse_pressed = pygame.mouse.get_pressed(num_buttons=3)[0]
        mx, my = pygame.mouse.get_pos()

        if not state["game_over"]:
            # 难度随时间上升
            difficulty = state["time"] / 10.0
            state["spawn_cd"] = max(0.25, SPAWN_BASE_INTERVAL - difficulty * 0.03)

            # 玩家移动
            player = state["player"]
            player.update(dt, keys)

            # 开火
            state["fire_cd"] = max(0.0, state["fire_cd"] - dt)
            if mouse_pressed and state["fire_cd"] <= 0.0:
                dx, dy = mx - player.x, my - player.y
                if vec_length(dx, dy) > 0:
                    state["bullets"].append(Bullet(player.x, player.y, dx, dy))
                    state["fire_cd"] = FIRE_COOLDOWN

            # 子弹更新
            bullets = state["bullets"]
            for b in bullets:
                b.update(dt)
            state["bullets"] = [b for b in bullets if not b.offscreen()]

            # 刷新敌人
            state["spawn_timer"] += dt
            while state["spawn_timer"] >= state["spawn_cd"]:
                state["spawn_timer"] -= state["spawn_cd"]
                state["enemies"].append(spawn_enemy(difficulty))

            # 敌人更新
            for e in state["enemies"]:
                e.update(dt, player.x, player.y)

            # 碰撞：子弹 vs 敌人
            new_enemies = []
            for e in state["enemies"]:
                hit = False
                for b in state["bullets"]:
                    if circle_hit(e.x, e.y, ENEMY_RADIUS, b.x, b.y, BULLET_RADIUS):
                        b.x, b.y = -9999, -9999  # 标记移除
                        hit = True
                        state["score"] += 10
                        break
                if not hit:
                    new_enemies.append(e)
            state["enemies"] = new_enemies
            state["bullets"] = [b for b in state["bullets"] if b.x > -1000]

            # 碰撞：敌人 vs 玩家
            still_enemies = []
            for e in state["enemies"]:
                if circle_hit(e.x, e.y, ENEMY_RADIUS, player.x, player.y, PLAYER_SIZE / 2):
                    if player.damage(1):
                        # 受到伤害时移除该敌人，避免瞬间连扣血
                        pass
                    else:
                        still_enemies.append(e)
                else:
                    still_enemies.append(e)
            state["enemies"] = still_enemies

            if player.hp <= 0:
                state["game_over"] = True

        # 绘制
        screen.fill((18, 18, 22))

        # 敌人
        for e in state["enemies"]:
            pygame.draw.circle(screen, (220, 70, 70), (int(e.x), int(e.y)), ENEMY_RADIUS)

        # 子弹
        for b in state["bullets"]:
            pygame.draw.circle(screen, (240, 220, 90), (int(b.x), int(b.y)), BULLET_RADIUS)

        # 玩家（无敌时闪烁）
        player = state["player"]
        if player.invuln > 0 and int(player.invuln * 10) % 2 == 0:
            color = (120, 200, 255)
        else:
            color = (70, 170, 255)
        pygame.draw.rect(screen, color, player.rect, border_radius=6)

        # UI
        draw_text(screen, font, f"分数：{state['score']}", 16, 14)
        draw_text(screen, font, f"生命：{'♥' * max(0, player.hp)}", 16, 42, color=(255, 120, 120))
        draw_text(screen, font, "WASD 移动｜鼠标左键射击｜ESC 退出", 16, HEIGHT - 34, color=(180, 180, 190))

        if state["game_over"]:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))
            draw_text(screen, big_font, "游戏结束", WIDTH / 2, HEIGHT / 2 - 40, center=True)
            draw_text(screen, font, f"最终分数：{state['score']}", WIDTH / 2, HEIGHT / 2 + 20, center=True)
            draw_text(screen, font, "按 R 重新开始｜按 ESC 退出", WIDTH / 2, HEIGHT / 2 + 56, center=True)

        pygame.display.flip()


if __name__ == "__main__":
    main()

