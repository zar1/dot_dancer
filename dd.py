#!/usr/bin/env python

import signal
import time
import sys
import tty
import termios
from random import random
import abc

DOT_SPEED = 4
PLAYER_SPEED = 2
EFFECT_SPEED = 8
DOT_PROB = .02

char = ''

class Game(object):
    __metaclass__ = abc.ABCMeta

    def draw(self):
        sys.stdout.write('\r{}'.format(''.join(self.get_board())))

    @abc.abstractmethod
    def get_board(self):
        return [' '] * 80

    @abc.abstractmethod
    def move_left(self):
        pass

    @abc.abstractmethod
    def move_right(self):
        pass

    @abc.abstractmethod
    def tick(self):
        pass

    @abc.abstractmethod
    def quit(self):
        pass

class Dot(object):
    def __init__(self, momentum, pos, sink, speed, dots, dots_by_pos, 
                 report_loss):
        self.momentum = momentum
        self.pos = pos
        self.dots = dots
        self.sink = sink
        self.speed = speed
        self.dots.append(self)
        self.dots_by_pos = dots_by_pos
        self.dots_by_pos[self.pos].append(self)
        self.turns_to_move = speed
        self.report_loss = report_loss

    def update(self):
        if self.turns_to_move > 0:
            self.turns_to_move -= 1
            return
        self.dots_by_pos[self.pos].remove(self)
        self.pos += self.momentum
        self.dots_by_pos[self.pos].append(self)
        if self.pos == self.sink:
            self.report_loss()
            self.die()
            return
        self.turns_to_move = self.speed

    def die(self):
        self.dots.remove(self)
        self.dots_by_pos[self.pos] = []

class DotDancer(Game):
    def __init__(self):
        self.pos = 39
        self.dots = []
        self.dots_by_pos = [[] for _ in xrange(80)]
        self.gear = 0
        self.reset_to_neutral = 0
        self.hit = 0
        self.miss = 0
        self.reset_to_no_effect = 0
        self.times_hit = 0
        self.times_missed = 0
        self.dots_generated = 0
        self.dots_lost = 0
    def get_board(self):
        board = [' '] * 80
        board[self.pos] = '@'
        if self.gear == 1:
            board[self.pos + 1] = '>'
        elif self.gear == -1:
            board[self.pos - 1] = '<'
        if self.hit == 1:
            board[self.pos + 1] = '+'
        if self.hit == -1:
            board[self.pos - 1] = '+'
        if self.miss == 1:
            board[self.pos + 1] = '-'
        if self.miss == -1:
            board[self.pos - 1] = '-'
        for dot in self.dots:
            board[dot.pos] = '.' 
        return board
    def move_left(self):
        self.gear = -1
        self.reset_to_neutral = PLAYER_SPEED
    def move_right(self):
        self.gear = 1
        self.reset_to_neutral = PLAYER_SPEED
    def __report_loss(self):
        self.dots_lost += 1
    def tick(self):
        # hit right
        if self.gear == 1 and self.dots_by_pos[self.pos + 1]:
            self.hit = 1
            self.times_hit += 1
            self.reset_to_no_effect = EFFECT_SPEED
            for dot in self.dots_by_pos[self.pos + 1]:
                dot.die()
            self.gear = 0
            self.reset_to_neutral = 0
        # hit left
        elif self.gear == -1 and self.dots_by_pos[self.pos - 1]:
            self.hit = -1
            self.times_hit += 1
            self.reset_to_no_effect = EFFECT_SPEED
            for dot in self.dots_by_pos[self.pos - 1]:
                dot.die()
            self.gear = 0
            self.reset_to_neutral = 0
        # miss right
        elif (self.gear == 1 and self.reset_to_neutral == 1 and 
              not self.dots_by_pos[self.pos + 1]):
            self.miss = 1
            self.times_missed += 1
            self.reset_to_no_effect = EFFECT_SPEED
        # miss left
        elif (self.gear == -1 and self.reset_to_neutral == 1 and 
              not self.dots_by_pos[self.pos - 1]):
            self.miss = -1
            self.times_missed += 1
            self.reset_to_no_effect = EFFECT_SPEED
            self.reset_to_no_effect = EFFECT_SPEED
        if self.reset_to_neutral <= 0:
            self.gear = 0
        else:
            self.reset_to_neutral -= 1   
        if self.reset_to_no_effect <= 0:
            self.hit = 0
            self.miss = 0
        else:
            self.reset_to_no_effect -= 1

        # Move dots
        for dot in self.dots:
            dot.update()

        # Generate new dots
        gen_left = False
        gen_right = False
        if random() < DOT_PROB:
            gen_left = True
        if random() < DOT_PROB:
            gen_right = True
        # Don't generate two dots at once
        if gen_left and gen_right:
            if random() < .50:
                gen_left = False
            else:
                gen_right = False
        if gen_left:
            Dot(1, self.pos-39, self.pos, DOT_SPEED, self.dots, 
                self.dots_by_pos, self.__report_loss)
            self.dots_generated += 1
        elif gen_right:
            Dot(-1, self.pos+39, self.pos, DOT_SPEED, self.dots, 
                self.dots_by_pos, self.__report_loss)
            self.dots_generated += 1

    def quit(self):
        dots_retired = self.times_hit + self.times_missed + self.dots_lost
        if self.times_hit + self.times_missed == 0:
            precision = '?'
        else:
            precision = float(self.times_hit) / (self.times_hit + 
                                                 self.times_missed)
        if dots_retired == 0:
            recall = '?'
        else:
            recall = float(self.times_hit) / dots_retired
        sys.stdout.write(('\ntotal dots retired: {}\n\r'
                          'dots hit: {}\n\r'
                          'dots missed: {}\n\r'
                          'superfluous steps: {}\n\r'
                          'precision: {}\n\r'
                          'recall: {}\n\r').format(
                dots_retired, 
                self.times_hit, 
                self.dots_lost,
                self.times_missed,
                precision,
                recall))

def getch():
    # http://stackoverflow.com/questions/510357/python-read-a-single-character-from-the-user
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

def tick(signum, frame, game):
    global char
    if char == 'q':
        signal.setitimer(signal.ITIMER_REAL, 0, 0)
        game.quit()
        exit(0)
    elif char == 'h':
        game.move_left()
    elif char == 'l':
        game.move_right() 
    char = ''
    game.tick()
    game.draw()

def main_loop(game):
    global char
    signal.signal(
            signal.SIGALRM, 
            lambda signum, frame: tick(signum, frame, game))
    signal.setitimer(signal.ITIMER_REAL, 1.0/30.0, 1.0/30.0)
    while True:
        char = getch()


if __name__ == '__main__':
    game = DotDancer()
    main_loop(game)
