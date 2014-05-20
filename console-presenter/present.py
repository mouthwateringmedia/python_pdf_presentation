#!/usr/bin/python

import curses
import errno
from fcntl import ioctl
import os
from termios import TIOCGWINSZ
import random
import termios
import time
import struct
import textwrap
import re
import codecs
import sys

from fancy_termios import tcgetattr, tcsetattr

delayprog = re.compile("\\$<([0-9]+)((?:/|\\*){0,2})>")


def getheightwidth():
    height, width = struct.unpack(
        "hhhh", ioctl(0, TIOCGWINSZ, "\000" * 8))[0:2]
    if not height:
        return 25, 80
    return height, width

curses.setupterm()
civis = curses.tigetstr('civis')
cnorm = curses.tigetstr('cnorm')
bold = curses.tigetstr('bold')
sgr0 = curses.tigetstr('sgr0')


class Screen(object):
    """Base class for text and code screens."""

    def __init__(self, text):
        self.text = text


class TextScreen(Screen):
    """Text that is centered on the screen."""

    def get_lines(self, width):
        """Center the lines of text on the screen in the specified width."""
        lines = []
        for line in self.text.splitlines():
            if not line.strip():
                lines.append(width * ' ')
            else:
                if line.startswith('*'):
                    subsequent_indent = '  '
                else:
                    subsequent_indent = ''
                wrapped = textwrap.wrap(
                    line, width - 4, subsequent_indent=subsequent_indent)
                for l in wrapped:
                    lines.append(l.center(width))
        return lines


class CodeScreen(Screen):
    """Text that is grouped then centered on the screen."""

    def get_lines(self, width):
        """Center the lines of text on the screen in the specified width."""
        lines = self.text.splitlines()
        longest = max([len(line) for line in lines])
        if longest > width:
            lines = [line[:width] for line in lines]
            longest = width
        result = [
            line.ljust(longest).center(width)
            for line in lines]
        return result


def split_text(text):
    return text.strip().split('\n#####\n')


def split_code(text):
    return [text.strip('\n')]


def load_screens(filename):
    screens = []
    content = codecs.open(filename, encoding='utf-8').read()
    screen_class = TextScreen
    break_text = split_text
    for part in re.split('({{{|}}})', content):
        stripped = part.strip()
        if stripped == '{{{':
            screen_class = CodeScreen
            break_text = split_code
        elif stripped == '}}}':
            screen_class = TextScreen
            break_text = split_text
        else:
            for text in break_text(part):
                screens.append(screen_class(text))

    return screens

screens = load_screens(sys.argv[1])

if len(sys.argv) > 2:
    i = int(sys.argv[2]) - 1
else:
    i = 0


def _my_getstr(cap, optional=0):
    r = curses.tigetstr(cap)
    if not optional and r is None:
        raise RuntimeError("terminal doesn't have the required '%s' capability" % cap)
    return r


class Presentation:
    def __init__(self, screens):
        self.screens = screens

    def make_screen(self, screen_i):
        r = []
        screen = self.screens[screen_i]
        h, w = getheightwidth()
        o = screen.get_lines(w)
        start_pad = (h - len(o)) // 2
        for i in range(start_pad):
            r.append(' ' * w)
        for p in o:
            r.append(p)
        for i in range(h - start_pad - len(o) - 1):
            r.append(' ' * w)
        l = (' %d / %d ' % (screen_i + 1, len(self.screens))).ljust(w)
        r.append(l)
        return r

presentation = Presentation(screens)

import unix_eventqueue


class C(object):

    def __init__(self):
        self.input_fd = 0
        self.partial_char = ''
        self.event_queue = unix_eventqueue.EventQueue(self.input_fd)
        self.encoding = 'utf-8'

        self._bel = _my_getstr("bel")
        self._civis = _my_getstr("civis", optional=1)
        self._clear = _my_getstr("clear")
        self._cnorm = _my_getstr("cnorm", optional=1)
        self._cub = _my_getstr("cub", optional=1)
        self._cub1 = _my_getstr("cub1", 1)
        self._cud = _my_getstr("cud", 1)
        self._cud1 = _my_getstr("cud1", 1)
        self._cuf = _my_getstr("cuf", 1)
        self._cuf1 = _my_getstr("cuf1", 1)
        self._cup = _my_getstr("cup")
        self._cuu = _my_getstr("cuu", 1)
        self._cuu1 = _my_getstr("cuu1", 1)
        self._dch1 = _my_getstr("dch1", 1)
        self._dch = _my_getstr("dch", 1)
        self._el = _my_getstr("el")
        self._hpa = _my_getstr("hpa", 1)
        self._ich = _my_getstr("ich", 1)
        self._ich1 = _my_getstr("ich1", 1)
        self._ind = _my_getstr("ind", 1)
        self._pad = _my_getstr("pad", 1)
        self._ri = _my_getstr("ri", 1)
        self._rmkx = _my_getstr("rmkx", 1)
        self._smkx = _my_getstr("smkx", 1)
        self._setaf = _my_getstr("setaf", 1)

    def __write_code(self, fmt, *args):
        os.write(0, curses.tparm(fmt, *args))

    def prepare(self):
        # per-readline preparations:
        self.__svtermstate = tcgetattr(self.input_fd)
        raw = self.__svtermstate.copy()
        raw.iflag &= ~ (termios.BRKINT | termios.INPCK |
                        termios.ISTRIP | termios.IXON)
        raw.oflag &= ~ (termios.OPOST)
        raw.cflag &= ~ (termios.CSIZE | termios.PARENB)
        raw.cflag |= (termios.CS8)
        raw.lflag &= ~ (termios.ICANON | termios.ECHO |
                        termios.IEXTEN | (termios.ISIG * 1))
        raw.cc[termios.VMIN] = 1
        raw.cc[termios.VTIME] = 0
        tcsetattr(self.input_fd, termios.TCSADRAIN, raw)

        self.screen = []
        self.height, self.width = getheightwidth()

        self.__buffer = []

        self.__write_code(self._smkx)

    def restore(self):
        self.__write_code(self._rmkx)
        tcsetattr(self.input_fd, termios.TCSADRAIN, self.__svtermstate)

    def push_char(self, char):
        self.partial_char += char
        try:
            c = unicode(self.partial_char, self.encoding)
        except UnicodeError, e:
            if len(e.args) > 4 and \
                e.args[4] == 'unexpected end of data':
                pass
            else:
                raise
        else:
            self.partial_char = ''
            self.event_queue.push(c)

    def get_event(self, block=1):
        while self.event_queue.empty():
            while 1:  # All hail Unix!
                try:
                    self.push_char(os.read(self.input_fd, 1))
                except (IOError, OSError), err:
                    if err.errno == errno.EINTR:
                        if not self.event_queue.empty():
                            return self.event_queue.get()
                        else:
                            continue
                    else:
                        raise
                else:
                    break
            if not block:
                break
        return self.event_queue.get()

c = C()


def sigwinch(*args):
    global cur_screen
    cur_screen = presentation.make_screen(i)
    os.system('clear')
    for line in cur_screen:
        os.write(0, '\r\n' + line.encode('utf-8'))

import signal
signal.signal(signal.SIGWINCH, sigwinch)

try:
    os.write(0, civis)
    c.prepare()
    old_screen = None
    old_f = None
    while i < len(screens):
        # Reload the screens every time we go bback or forward.
        screens[:] = load_screens(sys.argv[1])
        cur_screen = presentation.make_screen(i)
        f = {}
        b = 0
        star_count = ''.join(cur_screen).count('*')
        for yy in range(len(cur_screen)):
            for xx in range(len(cur_screen[yy])):
                old_b = b
                if cur_screen[yy][xx] == '*':
                    b ^= 1
                f[xx, yy] = b | old_b
                if f[xx, yy] and star_count % 2 == 0:
                    f[xx, yy] = bold
                else:
                    f[xx, yy] = sgr0
        if old_screen is None or len(old_screen) != len(cur_screen) or \
               len(old_screen[0]) != len(cur_screen[0]):
            c._C__write_code(c._cup, 0, 0)
            os.system('clear')
            for line in cur_screen:
                #if line == cur_screen[-1]:
                #    c._C__write_code(c._setaf, 7)
                os.write(0, '\r\n'+line.encode('utf-8'))
            c._C__write_code(c._setaf, 0)
        else:
            diffs = set()
            b = 0
            for y, (old, new) in enumerate(zip(old_screen, cur_screen)):
                for x, (o, n) in enumerate(zip(old, new)):
                    if o != n or f[x, y] != old_f[x, y]:
                        diffs.add((x, y, o, n))
            col = curses.tparm(c._setaf, random.choice(range(1, 8)))
            s = ''
            for (x, y, o, n) in diffs:
                s += (
                    curses.tparm(c._cup, y, x)
                    + old_f[x, y]
                    + col
                    + o.encode('utf-8')
                )
            os.write(0, s)
            d = 0.03
            l = len(diffs)
            chunk_size = l / 13 + 1
            c._C__write_code(c._setaf, 1)
            while diffs:
                s = ''
                for _ in range(chunk_size):
                    if not diffs:
                        break
                    x, y, o, n = diffs.pop()
                    s += f[x, y] + curses.tparm(c._cup, y, x)
                    color = (i % 7) + 1
                    if y == len(cur_screen) - 1:
                        s += curses.tparm(c._setaf, color)
                    else:
                        s += curses.tparm(c._setaf, color)
                    s += n.encode('utf-8')
                    os.write(0, s)
                time.sleep(d)
        old_screen = cur_screen
        old_f = f
        e = c.get_event()
        termios.tcflush(0, termios.TCIFLUSH)
        if e.data == '\x03' or e.data == 'q':
            break
        elif e.data == 'left' or e.data == 'page up' or e.data == 'up':
            i -= 1
            if i < 0:
                i = 0
        else:
            i += 1
            if i >= len(screens):
                i = len(screens) - 1
finally:
    c.restore()
    os.write(0, cnorm)
