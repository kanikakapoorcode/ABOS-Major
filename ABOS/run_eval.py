import sys  
import os  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  
from evaluation.run_evaluation import main  
import asyncio  
if __name__ == '__main__': asyncio.run(main()) 
