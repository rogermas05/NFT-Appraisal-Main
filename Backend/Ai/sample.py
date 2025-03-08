import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from Backend.Data import main

sample_data = main.main("0xe785e82358879f061bc3dcac6f0444462d4b5330", "4267")
print(sample_data)