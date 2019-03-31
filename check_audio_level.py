#!/usr/bin/env python3.5
import curses
import alsaaudio as aa
from struct import iter_unpack, unpack
from time import sleep, time
from collections import deque
from argparse import ArgumentParser
from posix_ipc import SharedMemory
from mmap import mmap
import logging


class MemoryState(object):
    MEM_SOUND_LEVEL = '/ash_memory'

    def __init__(self, logger=None):
        if logger is None:
            logger = logging.getLogger('shared_memory.api')
        self.log = logger
        self.log.debug('try to connect to shared memory %s',
                       self.MEM_SOUND_LEVEL)
        self.alsa_mem = SharedMemory(self.MEM_SOUND_LEVEL)
        self.alsa_mem_mmap = mmap(self.alsa_mem.fd, self.alsa_mem.size)
        self.alsa_mem_size = self.alsa_mem.size

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def get_sound_level(self):
        self.alsa_mem_mmap.seek(0)
        return iter_unpack('h', self.alsa_mem_mmap.read(self.alsa_mem_size))

    def __del__(self):
        self.close()

    def close(self):
        self.alsa_mem_mmap.close()
        self.alsa_mem.close_fd()


last_time = time()

def draw(stdscr, graph, options):
    global last_time
    current_time = time()
    if current_time - last_time < 0.04:
        return
    last_time = current_time
    bounds = stdscr.getmaxyx()
    center_y = int(bounds[0] / 2)
    center_x = int(bounds[1] / 2)
    y_k = (bounds[0] - 20) / 32768.0 / 2
    x_k = 1
    stdscr.clear()
    stdscr.addstr(1, 1, 'y_k={}, x_k={}, bounds={}x{}'.format(
        y_k, x_k, bounds[1], bounds[0]))
    if options.memory:
        stdscr.addstr(2, 1, 'source=memory')
    else:
        stdscr.addstr(2, 1, 'source={}, rate={}'.format(
            options.device, options.rate))
    x_position = 10 + x_k
    max_v = 0
    for value in graph:
        if max(max_v, abs(value)) != abs(max_v):
            max_v = value
        v_size = int(value * y_k)
        if v_size < 0:
            v_size = -v_size
            stdscr.vline(center_y, x_position, '#', v_size)
        else:
            stdscr.vline(center_y - v_size, x_position, '#', v_size)
        x_position += x_k
    stdscr.hline(center_y, x_k + 10, '-', bounds[1] - 20)
    stdscr.addstr(3, 1, 'max value {}'.format(max_v))
    stdscr.addstr(4, 1, 'time {}'.format(current_time))
    stdscr.refresh()


parser = ArgumentParser(description='test script to display input audio graph')
parser.add_argument('--memory',
                    action='store_true',
                    help='if you want to check data from videopipeline sound capture service',
                    default=False)
parser.add_argument('--memory-rate',
                    action='store',
                    type=int,
                    help='how often to check data from videopipeline sound capture service',
                    default=50)
parser.add_argument('--device',
                    action='store',
                    help='capture from this alsa device',
                    default='default')
parser.add_argument('--rate',
                    action='store',
                    type=int,
                    help='set rate in Hz, default 16000',
                    default=16000)
options = parser.parse_args()


def main(stdscr):
    global options
    stdscr.clear()
    bounds = stdscr.getmaxyx()
    graph = deque(maxlen=bounds[1] - 20)
    graph += [0 for x in range(0, bounds[1] - 20)]
    count = 0
    if options.memory:
        with MemoryState() as state:
            while True:
                draw(stdscr, graph, options)
                p = state.get_sound_level()
                for v in p:
                    count += 1
                    if count % options.memory_rate == 0:
                        count = 0
                        graph.append(v[0])
                sleep(0.01)
    else:
        # rec = aa.PCM(aa.PCM_CAPTURE, mode=aa.PCM_NONBLOCK)
        rec = aa.PCM(aa.PCM_CAPTURE, device=options.device)
        rec.setrate(options.rate)
        rec.setperiodsize(64)
        while True:
            draw(stdscr, graph, options)
            data = rec.read()
            if data[0] == 0 or data[0] < 0:
                sleep(0.05)
                continue
            for v in iter_unpack('xxh', data[1]):
                count += 1
                if count % 50 == 0:
                    count = 0
                    graph.append(v[0])

curses.wrapper(main)
