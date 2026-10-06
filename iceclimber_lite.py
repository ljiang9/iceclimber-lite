#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iceclimber-lite —— 极简登冰山街机小游戏（纯标准库）。

玩法：沿 1 格宽的冰缝向上攀爬，用锤子敲碎挡路的冰塞子，
小心在冰缝里上下巡逻的 Topi，到达山顶（y<=3）获胜。
小巧思：在冰缝里两侧都是冰壁时会「攀附」住不下坠（chimneying）。
计分：敲冰 +100，拍 Topi +500，登顶 +1000。3 条命。
"""

import argparse
import random
import sys

W, H = 9, 25
AIR, SOLID = ".", "#"
SUMMIT_Y = 3          # y <= 3 即登顶
JUMP_H = 2            # 跳跃高度（格）
START_LIVES = 3


class Game:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.grid = [[AIR] * W for _ in range(H)]
        self._gen()
        self.px, self.py = self.start
        self.lives = START_LIVES
        self.score = 0
        self.blocks = 0
        self.kills = 0
        self.ticks = 0
        self.over = False
        self.win = False
        self.max_y = self.py  # 到达过的最小 y（越高越小）
        self.enemies = []     # (x, y, vdir)，在冰缝里垂直巡逻的 Topi
        self._spawn_enemies()

    # ---------- 关卡生成 ----------
    def _gen(self):
        for y in range(5, H - 1):
            for x in range(W):
                self.grid[y][x] = SOLID
        self.grid[H - 1] = [SOLID] * W  # 基岩，不可敲碎
        # 3 条竖井：互不相邻（保证每条都是 1 格宽、两侧有冰壁可攀附），
        # 也不贴边（边界外不算冰壁）
        cols = list(range(1, W - 1))
        self.rng.shuffle(cols)
        shafts = []
        for c in cols:
            if all(abs(c - s) >= 2 for s in shafts):
                shafts.append(c)
            if len(shafts) == 3:
                break
        self.shafts = sorted(shafts)
        for c in shafts:
            for y in range(5, H - 1):
                self.grid[y][c] = AIR
            # 每条竖井留 2~4 个冰塞子，必须敲碎才能过
            for py in self.rng.sample(range(6, H - 2), self.rng.randint(2, 4)):
                self.grid[py][c] = SOLID
        c0 = shafts[0]
        self.start = (c0, H - 2)

    def _spawn_enemies(self):
        for c in self.shafts:
            cands = [y for y in range(8, H - 6)
                     if self.grid[y][c] == AIR
                     and abs(y - self.start[1]) > 4]
            if cands and self.rng.random() < 0.8:
                y = self.rng.choice(cands)
                self.enemies.append((c, y, self.rng.choice((-1, 1))))

    # ---------- 基础判定 ----------
    def solid(self, x, y):
        if x < 0 or x >= W or y < 0 or y >= H:
            return True
        return self.grid[y][x] == SOLID

    def air(self, x, y):
        return not self.solid(x, y)

    def chimney(self, x, y):
        """攀附：左右两侧都是真冰壁（地图边界外不算）→ 不下坠。"""
        if not (0 <= x < W and 0 <= y < H):
            return False
        left = x - 1 >= 0 and self.grid[y][x - 1] == SOLID
        right = x + 1 < W and self.grid[y][x + 1] == SOLID
        return left and right

    def _enemy_at(self, x, y):
        return any(e[0] == x and e[1] == y for e in self.enemies)

    def _kill_enemy_idx(self, idxs):
        for i in sorted(idxs, reverse=True):
            del self.enemies[i]
            self.kills += 1
            self.score += 500

    def _die(self):
        """玩家死亡。返回 True 表示本 tick 应停止后续处理。"""
        self.lives -= 1
        if self.lives <= 0:
            self.over = True
        else:
            self.px, self.py = self.start
        return True

    # ---------- 玩家动作 ----------
    def _move(self, dx):
        nx = self.px + dx
        if 0 <= nx < W and self.air(nx, self.py):
            self.px = nx
            if self._enemy_at(self.px, self.py):
                return self._die()
        return False

    def _jump(self):
        for _ in range(JUMP_H):
            ny = self.py - 1
            if self.solid(self.px, ny):
                break
            self.py = ny
            if self._enemy_at(self.px, self.py):
                return self._die()
        return False

    def _hammer_up(self):
        # 拍头顶贴脸的 Topi
        idxs = [i for i, e in enumerate(self.enemies)
                if e[0] == self.px and e[1] == self.py - 1]
        if idxs:
            self._kill_enemy_idx(idxs)
            return "bonk"
        tx, ty = self.px, self.py - 1
        if ty >= 0 and self.grid[ty][tx] == SOLID:
            self.grid[ty][tx] = AIR
            self.blocks += 1
            self.score += 100
            return "break"
        return "miss"

    def _hammer_down(self):
        # 拍脚下贴脸的 Topi
        idxs = [i for i, e in enumerate(self.enemies)
                if e[0] == self.px and e[1] == self.py + 1]
        if idxs:
            self._kill_enemy_idx(idxs)
            return "bonk"
        tx, ty = self.px, self.py + 1
        if ty < H - 1 and self.grid[ty][tx] == SOLID:
            self.grid[ty][tx] = AIR
            self.blocks += 1
            self.score += 100
            return "break"
        return "miss"

    # ---------- 世界推进 ----------
    def _gravity(self):
        """下坠（攀附住则不掉）；返回 True 表示中途死亡。"""
        while self.air(self.px, self.py + 1) and not self.chimney(self.px, self.py):
            self.py += 1
            if self._enemy_at(self.px, self.py):
                return self._die()
        return False

    def _enemy_tick(self):
        for i, (ex, ey, vd) in enumerate(self.enemies):
            if self.ticks % 2 == 0:  # Topi 比玩家慢半拍
                ny = ey + vd
                if ny < 5 or ny > H - 2 or self.solid(ex, ny):
                    vd = -vd
                else:
                    ey = ny
            self.enemies[i] = (ex, ey, vd)
            if ex == self.px and ey == self.py:
                return self._die()
        return False

    def step(self, action):
        if self.over:
            return
        self.ticks += 1
        dead = False
        if action == "left":
            dead = self._move(-1)
        elif action == "right":
            dead = self._move(1)
        elif action == "jump":
            dead = self._jump()
        elif action == "hammer_up":
            self._hammer_up()
        elif action == "hammer_down":
            self._hammer_down()
        self.max_y = min(self.max_y, self.py)
        if not self.over and self.py <= SUMMIT_Y:
            # 登顶瞬间即获胜（不等重力把人拽回去）
            self.win = True
            self.over = True
            self.score += 1000
            return
        if not dead and not self.over:
            dead = self._gravity()
        if not dead and not self.over:
            dead = self._enemy_tick()

    # ---------- 渲染 ----------
    def render(self):
        rows = []
        for y in range(H):
            row = []
            for x in range(W):
                c = self.grid[y][x]
                if x == self.px and y == self.py:
                    c = "P"
                elif self._enemy_at(x, y):
                    c = "T"
                row.append(c)
            rows.append("".join(row))
        head = f"命:{self.lives} 分:{self.score} 高度:{H - 1 - self.max_y} tick:{self.ticks}"
        return head + "\n" + "\n".join(rows)


# ---------- 自动演示 AI ----------
def ai_action(g):
    px, py = g.px, g.py
    foes = [(e[0], e[1]) for e in g.enemies]
    # 1. 贴脸的 Topi → 拍
    if any(fx == px and fy == py - 1 for fx, fy in foes):
        return "hammer_up"
    if any(fx == px and fy == py + 1 for fx, fy in foes):
        return "hammer_down"
    # 2. 头顶是冰塞子 → 敲
    if g.solid(px, py - 1):
        return "hammer_up"
    # 3. 头顶 4 格内有 Topi → 等它下来（玩家先手，贴脸必拍中）
    if any(fx == px and py - 4 <= fy <= py - 2 for fx, fy in foes):
        return "wait"
    # 4. 往上跳（允许只跳 1 格：先贴到冰塞子底下，下回合再敲）
    if g.air(px, py - 1):
        return "jump"
    return "wait"


def auto_play(seed=0, ticks=1500, verbose=False):
    g = Game(seed)
    while not g.over and g.ticks < ticks:
        g.step(ai_action(g))
        if verbose and g.ticks % 300 == 0:
            print(g.render())
            print()
    status = "登顶成功" if g.win else ("阵亡" if g.lives <= 0 else "未登顶")
    print(f"自动演示结束：{status}，得分 {g.score}，最高高度 {H - 1 - g.max_y}，"
          f"敲冰 {g.blocks}，拍敌 {g.kills}，剩余命 {g.lives}，tick {g.ticks}")
    return g


def interactive():
    if not sys.stdin.isatty():
        print("交互模式需要终端，请用 --auto 运行无头演示。", file=sys.stderr)
        sys.exit(2)
    g = Game()
    print("操作：w跳 u敲上 j敲下 q退出（冰缝里左右走不动，靠攀附上升）")
    while not g.over:
        print(g.render())
        try:
            cmd = input("> ").strip().lower()
        except EOFError:
            break
        act = {"w": "jump", "u": "hammer_up", "j": "hammer_down"}.get(cmd)
        if cmd == "q":
            break
        if act:
            g.step(act)
    print("登顶成功！" if g.win else "游戏结束。", f"得分 {g.score}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="iceclimber-lite：敲冰登顶小游戏")
    ap.add_argument("--auto", action="store_true", help="无头自动演示")
    ap.add_argument("--ticks", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    if args.auto:
        auto_play(args.seed, args.ticks, args.verbose)
    else:
        interactive()


if __name__ == "__main__":
    main()
