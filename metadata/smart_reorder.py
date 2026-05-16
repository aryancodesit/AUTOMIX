from typing import List, Dict

def get_camelot_distance(cam1: str, cam2: str) -> float:
    """Calculates the harmonic transition cost between two Camelot keys."""
    if not cam1 or not cam2 or cam1 == "Unknown" or cam2 == "Unknown":
        return 10.0 # High penalty for unknown keys
        
    if cam1 == cam2:
        return 0.0 # Perfect match
        
    num1, letter1 = int(cam1[:-1]), cam1[-1]
    num2, letter2 = int(cam2[:-1]), cam2[-1]
    
    # Distance around the circle (1-12)
    num_diff = min(abs(num1 - num2), 12 - abs(num1 - num2))
    
    # Letter change penalty (A to B)
    letter_diff = 0 if letter1 == letter2 else 1
    
    # Perfect transitions (distance = 1 step on wheel)
    if num_diff == 0 and letter_diff == 1:
        return 1.0 # e.g., 8A -> 8B
    if num_diff == 1 and letter_diff == 0:
        return 1.0 # e.g., 8A -> 9A
        
    # Energy boost transition (+2 semitones = +2 on wheel)
    if num_diff == 2 and letter_diff == 0:
        return 2.0
        
    return float(num_diff + letter_diff * 2)

class SmartReorder:
    def calculate_cost(self, track1: Dict, track2: Dict) -> float:
        """Calculates the transition cost between two tracks (lower is better)."""
        # BPM difference penalty (high penalty if > 10% difference)
        bpm1 = track1.get("bpm") or 120.0
        bpm2 = track2.get("bpm") or 120.0
        
        bpm_diff = abs(bpm1 - bpm2)
        bpm_penalty = (bpm_diff / bpm1) * 100
        
        # Harmonic mixing penalty
        cam_penalty = get_camelot_distance(track1.get("camelot"), track2.get("camelot"))
        
        # Energy flow (prefer slight increases or steady energy)
        e1 = track1.get("energy") or 0.5
        e2 = track2.get("energy") or 0.5
        energy_diff = e2 - e1
        
        # Slight penalty for massive energy drops, reward for slight increases
        if energy_diff < -0.2:
            energy_penalty = 5.0
        else:
            energy_penalty = abs(energy_diff) * 2.0
            
        return bpm_penalty + (cam_penalty * 2.0) + energy_penalty

    def sort_playlist(self, tracks: List[Dict], start_idx: int = 0) -> List[Dict]:
        """Uses a greedy approach to build the best flowing playlist."""
        if not tracks:
            return []
            
        unplayed = tracks.copy()
        
        # Start with the selected track
        start_track = unplayed.pop(start_idx)
        ordered_playlist = [start_track]
        
        current_track = start_track
        
        while unplayed:
            best_idx = 0
            best_cost = float('inf')
            
            for i, candidate in enumerate(unplayed):
                cost = self.calculate_cost(current_track, candidate)
                if cost < best_cost:
                    best_cost = cost
                    best_idx = i
                    
            next_track = unplayed.pop(best_idx)
            ordered_playlist.append(next_track)
            current_track = next_track
            
        return ordered_playlist
