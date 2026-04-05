import sys
import time

print("Starting imports...")
print(f"1. Importing warnings... ", end="", flush=True)
import warnings
print("OK")

print(f"2. Importing FastAPI... ", end="", flush=True)
from fastapi import FastAPI
print("OK")

print(f"3. Importing config... ", end="", flush=True)
from config import config
print("OK")

print(f"4. Importing RAGSystem... ", end="", flush=True)
start = time.time()
from rag_system import RAGSystem
print(f"OK ({time.time() - start:.2f}s)")

print(f"5. Initializing RAGSystem... ", end="", flush=True)
start = time.time()
rag_system = RAGSystem(config)
print(f"OK ({time.time() - start:.2f}s)")

print(f"\nAll imports successful!")
