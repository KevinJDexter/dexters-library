"""
Tests for the video_games package.

The __init__.py matters: without it pytest imports test modules by bare
basename, so a second package's test_models.py would collide with this one's.
That becomes a real problem the moment board_games/tests/ exists.

Shared fixtures live in backend/conftest.py — pytest finds conftest files
hierarchically, so everything defined at the root is available here with no
import.
"""
