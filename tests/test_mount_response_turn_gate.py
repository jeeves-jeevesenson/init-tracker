import unittest
from unittest.mock import MagicMock, patch
from dnd_initative_tracker import InitiativeTracker

class TestMountResponseTurnGate(unittest.TestCase):
    def setUp(self):
        self.tracker = InitiativeTracker()
        self.tracker.in_combat = True
        
        # Add combatants
        self.rider_cid = 1
        self.mount_cid = 2
        self.other_cid = 3
        
        self.rider = MagicMock()
        self.rider.cid = self.rider_cid
        self.rider.name = "Rider"
        self.rider.is_pc = True
        
        self.mount = MagicMock()
        self.mount.cid = self.mount_cid
        self.mount.name = "Mount"
        self.mount.is_pc = True
        
        self.other = MagicMock()
        self.other.cid = self.other_cid
        self.other.name = "Other"
        self.other.is_pc = True
        
        self.tracker.combatants = {
            self.rider_cid: self.rider,
            self.mount_cid: self.mount,
            self.other_cid: self.other
        }
        
        # Set turn to rider
        self.tracker.current_cid = self.rider_cid
        
        # Setup LAN mock
        self.tracker._lan = MagicMock()
        
    def test_mount_response_off_turn_allowed(self):
        """Intended mount can accept off-turn."""
        request_id = "mount:123:1:2"
        self.tracker._pending_mount_requests = {
            request_id: {
                "rider_cid": self.rider_cid,
                "mount_cid": self.mount_cid,
                "requester_ws": 99
            }
        }
        
        msg = {
            "type": "mount_response",
            "request_id": request_id,
            "accept": True,
            "cid": self.mount_cid,
            "_claimed_cid": self.mount_cid,
            "_ws_id": 100
        }
        
        with patch.object(self.tracker, '_accept_mount') as mock_accept:
            with patch.object(self.tracker._lan, 'toast') as mock_toast:
                self.tracker._lan_apply_action(msg)
                
                # Expecting it to NOT be blocked by turn gate
                self.assertNotIn(request_id, self.tracker._pending_mount_requests)
                mock_accept.assert_called_once_with(self.rider_cid, self.mount_cid, 99, auto=False)
                
                # Ensure no "Not yer turn" toast
                for call in mock_toast.call_args_list:
                    self.assertNotEqual(call[0][1], "Not yer turn yet, matey.")

    def test_mount_response_reject_off_turn_allowed(self):
        """Intended mount can reject off-turn."""
        request_id = "mount:123:1:2"
        self.tracker._pending_mount_requests = {
            request_id: {
                "rider_cid": self.rider_cid,
                "mount_cid": self.mount_cid,
                "requester_ws": 99
            }
        }
        
        msg = {
            "type": "mount_response",
            "request_id": request_id,
            "accept": False,
            "cid": self.mount_cid,
            "_claimed_cid": self.mount_cid,
            "_ws_id": 100
        }
        
        with patch.object(self.tracker, '_accept_mount') as mock_accept:
            with patch.object(self.tracker._lan, 'toast') as mock_toast:
                self.tracker._lan_apply_action(msg)
                
                # Request should be cleared
                self.assertNotIn(request_id, self.tracker._pending_mount_requests)
                mock_accept.assert_not_called()
                
                # Toast should be sent to requester
                mock_toast.assert_any_call(99, "Mount request declined.")

    def test_movement_off_turn_still_blocked(self):
        """Movement is still turn-gated."""
        msg = {
            "type": "move",
            "to": {"col": 5, "row": 5},
            "cid": self.mount_cid,
            "_claimed_cid": self.mount_cid,
            "_ws_id": 100
        }
        
        with patch.object(self.tracker._lan, 'toast') as mock_toast:
            self.tracker._lan_apply_action(msg)
            mock_toast.assert_any_call(100, "Not yer turn yet, matey.")

    def test_mount_response_wrong_claimant_rejected(self):
        """Wrong claimant cannot accept the mount request."""
        request_id = "mount:123:1:2"
        self.tracker._pending_mount_requests = {
            request_id: {
                "rider_cid": self.rider_cid,
                "mount_cid": self.mount_cid,
                "requester_ws": 99
            }
        }
        
        # Another character (cid=3) tries to respond to cid=2's request
        msg = {
            "type": "mount_response",
            "request_id": request_id,
            "accept": True,
            "cid": self.other_cid,
            "_claimed_cid": self.other_cid,
            "_ws_id": 101
        }
        
        with patch.object(self.tracker, '_accept_mount') as mock_accept:
            with patch.object(self.tracker._lan, 'toast') as mock_toast:
                self.tracker._lan_apply_action(msg)
                
                # Request should still be pending
                self.assertIn(request_id, self.tracker._pending_mount_requests)
                mock_accept.assert_not_called()
                mock_toast.assert_any_call(101, "Ye are not the one being mounted, matey.")

    def test_mount_response_missing_claimant_rejected(self):
        """Missing claimant cannot accept the mount request."""
        request_id = "mount:123:1:2"
        self.tracker._pending_mount_requests = {
            request_id: {
                "rider_cid": self.rider_cid,
                "mount_cid": self.mount_cid,
                "requester_ws": 99
            }
        }
        
        # Message with no cid/claimed_cid
        msg = {
            "type": "mount_response",
            "request_id": request_id,
            "accept": True,
            "_ws_id": 102
        }
        
        with patch.object(self.tracker, '_accept_mount') as mock_accept:
            with patch.object(self.tracker._lan, 'toast') as mock_toast:
                self.tracker._lan_apply_action(msg)
                
                # Should be rejected by _lan_apply_action first ("Claim a character first")
                # or by PlayerCommandService if it gets past that.
                # In _lan_apply_action, it hits: 
                # if cid is None and not is_admin and typ not in ("set_auras_enabled",):
                # self._lan.toast(ws_id, "Claim a character first, matey.")
                
                mock_toast.assert_any_call(102, "Claim a character first, matey.")
                self.assertIn(request_id, self.tracker._pending_mount_requests)
                mock_accept.assert_not_called()

    def test_mount_response_admin_bypass_allowed(self):
        """Admin can accept mount request regardless of claim."""
        request_id = "mount:123:1:2"
        self.tracker._pending_mount_requests = {
            request_id: {
                "rider_cid": self.rider_cid,
                "mount_cid": self.mount_cid,
                "requester_ws": 99
            }
        }
        
        # Admin message with a token that we'll mock as valid
        msg = {
            "type": "mount_response",
            "request_id": request_id,
            "accept": True,
            "cid": None,
            "admin_token": "valid_token",
            "_ws_id": 103
        }
        
        with patch.object(self.tracker, '_is_admin_token_valid', return_value=True):
            with patch.object(self.tracker, '_accept_mount') as mock_accept:
                with patch.object(self.tracker._lan, 'toast') as mock_toast:
                    self.tracker._lan_apply_action(msg)
                    
                    self.assertNotIn(request_id, self.tracker._pending_mount_requests)
                    mock_accept.assert_called_once_with(self.rider_cid, self.mount_cid, 99, auto=False)

if __name__ == "__main__":
    unittest.main()
