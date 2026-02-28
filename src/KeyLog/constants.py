import os

from dataclasses import dataclass

""" Constant to the path for the directory of the program"""
BASE_DIR = os.path.dirname(os.path.realpath(__file__))

@dataclass(frozen=True)
class Theme:
    highlight = "bold #32CD32"
    header = "bold #ffffff"
    count = "#aaaaaa"
    border = "#444444"
