import sys
from pathlib import Path

# check_notices.py는 레포 루트에 있는 단일 스크립트(패키지 아님)라 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
