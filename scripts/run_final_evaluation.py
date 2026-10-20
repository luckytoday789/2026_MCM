"""Fixed authenticated refit/final entry; importing this file performs no work."""
from pathlib import Path
import sys

if __name__=='__main__':
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
    from safeinvest.final_execution import main
    main()
