"""Largest-Triangle-Three-Buckets (LTTB) downsampling.

Used to reduce high-frequency physiology curves (5000Hz) to ~200 points
for WebSocket transmission to the frontend.
"""
import numpy as np
from numpy.typing import NDArray


def lttb_downsample(
    data: NDArray[np.float64], target_points: int,
) -> NDArray[np.float64]:
    """Downsample 1D array to target_points using LTTB algorithm.
    
    Args:
        data: 1D numpy array of float64 values.
        target_points: Desired number of output points.
    
    Returns:
        Downsampled 1D numpy array. Returns copy of input if
        target_points >= len(data) or target_points < 3.
    """
    n = len(data)
    if target_points >= n or target_points < 3:
        return data.copy()
    
    result = np.empty(target_points, dtype=np.float64)
    result[0] = data[0]
    result[-1] = data[-1]
    
    bucket_size = (n - 2) / (target_points - 2)
    a_index = 0
    
    for i in range(1, target_points - 1):
        # Calculate bucket boundaries
        bucket_start = int((i - 1) * bucket_size) + 1
        bucket_end = int(i * bucket_size) + 1
        next_start = int(i * bucket_size) + 1
        next_end = min(int((i + 1) * bucket_size) + 1, n)
        
        # Average of next bucket (look-ahead)
        avg_y = np.mean(data[next_start:next_end])
        avg_x = (next_start + next_end - 1) / 2
        
        # Find point in current bucket with max triangle area
        max_area = -1.0
        selected = bucket_start
        for j in range(bucket_start, min(bucket_end, n)):
            area = abs(
                (a_index - avg_x) * (data[j] - data[a_index]) -
                (a_index - j) * (avg_y - data[a_index])
            )
            if area > max_area:
                max_area = area
                selected = j
        
        result[i] = data[selected]
        a_index = selected
    
    return result
