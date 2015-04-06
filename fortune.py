import os
import random

g_fortunes = None
def load_fortunes():
    global g_fortunes
    if g_fortunes is None:
        folder = os.path.dirname(__file__)
        fortune_file = os.path.join(folder, "fortunes.txt")
        g_fortunes = open(fortune_file).read().split('%')
    return g_fortunes

def fortune():
    fortunes = load_fortunes()
    return random.choice(fortunes).strip()

if __name__ == "__main__":
    print fortune()

