INITIAL = [
    {"id": "a", "rev": 1, "lab": "L1", "device": "D1", "units": 2, "start": 0, "end": 10},
    {"id": "b", "rev": 1, "lab": "L1", "device": "D2", "units": 3, "start": 0, "end": 10},
    {"id": "c", "rev": 1, "lab": "L2", "device": "D1", "units": 5, "start": 0, "end": 10},
    {"id": "d", "rev": 1, "lab": "L2", "device": "D2", "units": 7, "start": 0, "end": 10},
    {"id": "extra", "rev": 1, "lab": "L1", "device": "D1", "units": 1, "start": 5, "end": 10}
]
CORRECTION = [
    {"id": "extra", "rev": 2, "lab": "L1", "device": "D1", "units": 0, "start": 5, "end": 10},
    {"id": "d", "rev": 2, "lab": "L3", "device": "D2", "units": 7, "start": 0, "end": 10}
]
INITIAL_RESULT = {"total": 2625, "labs": {"L1": 2625, "L2": 2625}}
FINAL_RESULT = {"total": 0, "labs": {"L1": 0, "L2": 0, "L3": 0}}
DELTA = {"total": -2625, "labs": {"L1": -2625, "L2": -2625}}
