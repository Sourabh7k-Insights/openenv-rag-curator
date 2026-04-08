"""Quick test to verify graders return scores in (0, 1)"""
from graders import grade_task_0, grade_task_1, grade_task_2
from database import get_fresh_database

# Test with empty database (worst case)
empty_db = {}
score0, msg0 = grade_task_0(empty_db)
score1, msg1 = grade_task_1(empty_db)
score2, msg2 = grade_task_2(empty_db)

print("Empty DB Test:")
print(f"  Task 0: {score0} (should be in (0, 1)) - {msg0}")
print(f"  Task 1: {score1} (should be in (0, 1)) - {msg1}")
print(f"  Task 2: {score2} (should be in (0, 1)) - {msg2}")

# Test with full database (best case)
full_db = get_fresh_database()
score0_full, msg0_full = grade_task_0(full_db)
score1_full, msg1_full = grade_task_1(full_db)
score2_full, msg2_full = grade_task_2(full_db)

print("\nFull DB Test:")
print(f"  Task 0: {score0_full} (should be in (0, 1)) - {msg0_full}")
print(f"  Task 1: {score1_full} (should be in (0, 1)) - {msg1_full}")
print(f"  Task 2: {score2_full} (should be in (0, 1)) - {msg2_full}")

# Verify all scores are in range
all_scores = [score0, score1, score2, score0_full, score1_full, score2_full]
all_valid = all(0 < s < 1 for s in all_scores)

print(f"\n{'✓' if all_valid else '✗'} All scores in range (0, 1): {all_valid}")
if not all_valid:
    print("  Invalid scores:", [s for s in all_scores if not (0 < s < 1)])
