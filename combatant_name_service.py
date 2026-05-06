import re
from typing import Iterable, Set

class CombatantNameService:
    """Service for managing unambiguous combatant names."""

    @staticmethod
    def get_next_available_name(base_name: str, existing_names: Iterable[str]) -> str:
        """Find the next available numeric suffix for a base name.
        
        Rules:
        - If 'Monster' is requested and no 'Monster' or 'Monster N' exists, returns 'Monster 1'.
        - If 'Monster' (unsuffixed) exists, it counts as 'Monster 1' or just takes the base slot.
        - Returns 'Monster N' where N is the smallest integer >= 1 such that 
          'Monster N' does not exist in existing_names.
        """
        base_name = base_name.strip()
        if not base_name:
            return "Unknown 1"

        # Normalize existing names for faster lookup
        # We also need to identify which numbers are already taken for this base name.
        taken_numbers: Set[int] = set()
        
        # Pattern to match "Base Name" or "Base Name N"
        # We need to be careful with regex escaping of the base name.
        escaped_base = re.escape(base_name)
        # Match "Base Name" exactly or "Base Name <space> <digits>"
        pattern = re.compile(rf"^{escaped_base}(?:\s+(\d+))?$", re.IGNORECASE)

        for name in existing_names:
            match = pattern.match(name.strip())
            if match:
                suffix = match.group(1)
                if suffix:
                    taken_numbers.add(int(suffix))
                else:
                    # The unsuffixed base name exists. 
                    # We treat this as taking a slot. Historically, we might want to 
                    # treat "Monster" as "Monster 1" if we are transitioning to 
                    # mandatory numbering.
                    # For now, let's just mark '1' as taken if it's the base name,
                    # or if we want to be more flexible, we just note that the 
                    # base name is present.
                    taken_numbers.add(1)

        # Find the first available number starting from 1
        candidate = 1
        while candidate in taken_numbers:
            candidate += 1
            
        return f"{base_name} {candidate}"
