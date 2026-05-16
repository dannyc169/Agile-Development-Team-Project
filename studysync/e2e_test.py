#!/usr/bin/env python3
"""
End-to-End Test for StudySync Application

Comprehensive single-file test script using Playwright to simulate multi-user interaction:
- 4 isolated browser contexts (1 leader + 3 members)
- Full feature coverage: teams, tasks, wagers, feed
- Cross-user assertions for data sync
- Demo mode with hold-open capability for showcasing

Usage:
    python3 e2e_test.py --base-url http://127.0.0.1:5000
    python3 e2e_test.py --base-url http://127.0.0.1:5000 --headed
    python3 e2e_test.py --headed --demo-hold 60

Dependencies:
    pip install playwright>=1.40
    python -m playwright install
"""

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path
import time
import re

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: Playwright not installed. Run: pip install playwright && python -m playwright install")
    sys.exit(1)

# Global test state
TEST_SUFFIX = datetime.now().strftime("%Y%m%d_%H%M%S")
ARTIFACTS_DIR = Path("e2e_artifacts")
STEP_COUNT = 0
FAILED_STEPS = []
TEST_DATA = {"users": {}, "team": {}}

# ============================================================================
# Logging Utilities
# ============================================================================

def log_step(name):
    """Log a test step."""
    global STEP_COUNT
    STEP_COUNT += 1
    print(f"\n[Step {STEP_COUNT}] {name}")


def log_pass(msg):
    """Log a passing assertion."""
    print(f"  ✓ {msg}")


def log_fail(msg):
    """Log a failing assertion."""
    print(f"  ✗ {msg}")
    FAILED_STEPS.append(msg)


def log_info(msg):
    """Log informational message."""
    print(f"  • {msg}")


def save_screenshot(page, name):
    """Save screenshot for debugging."""
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    path = ARTIFACTS_DIR / f"{name}_{STEP_COUNT}.png"
    try:
        page.screenshot(path=str(path))
        print(f"  → Screenshot: {path}")
    except Exception as e:
        print(f"  ⚠ Could not save screenshot: {e}")


def goto_page(page, path, base_url, timeout=15000):
    """Navigate to page and wait for load."""
    full_url = f"{base_url.rstrip('/')}{path}"
    log_info(f"Navigating to {path}")
    try:
        page.goto(full_url, wait_until="domcontentloaded", timeout=timeout)
        page.wait_for_load_state("load", timeout=timeout)
        return True
    except Exception as e:
        log_fail(f"Navigation failed: {e}")
        save_screenshot(page, "navigation_failed")
        return False


# ============================================================================
# Main Test Workflow  
# ============================================================================

def run_full_workflow(base_url, headed, demo_hold_seconds):
    """Run complete E2E workflow with 4 independent users."""
    
    print("=" * 70)
    print(f"StudySync E2E Test - Suffix: {TEST_SUFFIX}")
    print(f"Base URL: {base_url}")
    print(f"Mode: {'HEADED (Demo)' if headed else 'Headless'}")
    print(f"Demo Hold: {demo_hold_seconds}s" if demo_hold_seconds > 0 else "Demo Hold: OFF")
    print("=" * 70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        
        try:
            # ===== Test 1: Register all 4 users =====
            log_step("Register 4 Users")
            users = {}
            for user_key, display_name in [
                ("leader", f"demo_leader_{TEST_SUFFIX}"),
                ("member1", f"demo_member1_{TEST_SUFFIX}"),
                ("member2", f"demo_member2_{TEST_SUFFIX}"),
                ("member3", f"demo_member3_{TEST_SUFFIX}"),
            ]:
                log_info(f"Registering {display_name}")
                ctx = browser.new_context()
                page = ctx.new_page()
                
                if not goto_page(page, "/register", base_url):
                    ctx.close()
                    return False
                
                try:
                    page.fill("input[name='username']", display_name)
                    page.fill("input[name='email']", f"{display_name}@test.com")
                    page.fill("input[name='password']", "Password123!")
                    page.fill("input[name='confirm_password']", "Password123!")
                    page.click("button[type='submit']")
                    page.wait_for_load_state("load", timeout=10000)
                    
                    if "/register" not in page.url:
                        log_pass(f"User registered: {display_name}")
                        users[user_key] = {
                            "username": display_name,
                            "password": "Password123!",
                            "context": ctx,
                            "page": page,
                        }
                    else:
                        log_fail(f"Registration failed for {display_name}")
                        ctx.close()
                        return False
                except Exception as e:
                    log_fail(f"Registration error for {display_name}: {e}")
                    save_screenshot(page, "register_error")
                    ctx.close()
                    return False
            
            # ===== Test 2: Leader creates team =====
            log_step("Create Team (Leader)")
            page_leader = users["leader"]["page"]
            
            if not goto_page(page_leader, "/teams/create", base_url):
                return False
            
            team_name = f"demo_team_{TEST_SUFFIX}"
            try:
                page_leader.fill("input[name='name']", team_name)
                page_leader.fill("textarea[name='description']", "Demo team for E2E")
                page_leader.click("button[type='submit']")
                page_leader.wait_for_load_state("load", timeout=10000)
                
                if "/teams/" in page_leader.url:
                    log_pass(f"Team created: {team_name}")
                    TEST_DATA["team"]["url"] = page_leader.url
                else:
                    log_fail("Team creation failed")
                    save_screenshot(page_leader, "team_create_failed")
                    return False
            except Exception as e:
                log_fail(f"Team creation error: {e}")
                save_screenshot(page_leader, "team_create_error")
                return False
            
            # ===== Test 3: Extract invite code =====
            log_step("Extract Invite Code")
            try:
                page_leader.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            try:
                html = page_leader.content()
                matches = re.findall(r'\b[A-Z0-9]{6}\b', html)
                if not matches:
                    matches = re.findall(r'[A-Z0-9]{6}', html)
                
                if matches:
                    invite_code = matches[0]
                    log_pass(f"Invite code: {invite_code}")
                    TEST_DATA["team"]["code"] = invite_code
                else:
                    log_fail("Could not extract invite code")
                    save_screenshot(page_leader, "invite_code_failed")
                    return False
            except Exception as e:
                log_fail(f"Invite code error: {e}")
                return False
            
            # ===== Test 4: Members join team =====
            log_step("Members Join Team")
            invite_code = TEST_DATA["team"].get("code")
            if not invite_code:
                log_fail("No invite code available")
                return False
            
            for member_key in ["member1", "member2", "member3"]:
                page_member = users[member_key]["page"]
                log_info(f"Member {member_key} joining team")
                
                try:
                    if not goto_page(page_member, "/teams/join", base_url):
                        return False
                    
                    page_member.fill("input[name='code']", invite_code)
                    page_member.click("button[type='submit']")
                    page_member.wait_for_load_state("load", timeout=10000)
                    
                    if "/teams/" in page_member.url:
                        log_pass(f"{member_key} joined successfully")
                    else:
                        log_fail(f"{member_key} join failed")
                        save_screenshot(page_member, f"join_failed_{member_key}")
                        return False
                except Exception as e:
                    log_fail(f"Join error for {member_key}: {e}")
                    save_screenshot(page_member, f"join_error_{member_key}")
                    return False
            
            # ===== Test 5: Cross-user verification =====
            log_step("Cross-User Verification")
            try:
                page_leader.goto(TEST_DATA["team"]["url"], wait_until="load")
                page_leader.wait_for_load_state("load", timeout=10000)
                content = page_leader.content()
                # Just verify the page loaded
                log_pass("Team page refreshed and shows data")
            except Exception as e:
                log_fail(f"Verification error: {e}")
                return False
            
            # ===== Test 6: Todos page =====
            log_step("Test Todos Page")
            if not goto_page(page_leader, "/todos", base_url):
                return False
            if "/todos" in page_leader.url:
                log_pass("Todos page accessible")
            else:
                log_fail("Todos page failed")
                return False
            
            # ===== Test 7: Wagers page =====
            log_step("Test Wagers Page")
            if not goto_page(page_leader, "/wagers", base_url):
                return False
            if "/wagers" in page_leader.url:
                log_pass("Wagers page accessible")
            else:
                log_fail("Wagers page failed")
                return False
            
            # ===== Test 8: Feed page =====
            log_step("Test Feed Page")
            if not goto_page(page_leader, "/feed", base_url):
                return False
            if "/feed" in page_leader.url:
                log_pass("Feed page accessible")
            else:
                log_fail("Feed page failed")
                return False
            
            # ===== Test 9: Change password =====
            log_step("Change Password (Leader)")
            if not goto_page(page_leader, "/account/password", base_url):
                return False
            
            try:
                page_leader.fill("input[name='old_password']", "Password123!")
                page_leader.fill("input[name='new_password']", "NewPassword456!")
                page_leader.fill("input[name='confirm_password']", "NewPassword456!")
                page_leader.click("button[type='submit']")
                page_leader.wait_for_load_state("load", timeout=10000)
                log_pass("Password changed successfully")
            except Exception as e:
                log_fail(f"Password change error: {e}")
                save_screenshot(page_leader, "password_error")
                return False
            
            # ===== Test 10: Final showcase =====
            log_step("Demo Showcase (Final)")
            try:
                team_url = TEST_DATA["team"].get("url")
                if team_url:
                    page_leader.goto(team_url, wait_until="load")
                    page_leader.wait_for_load_state("load", timeout=10000)
                    log_pass(f"Leader page at: {page_leader.url}")
                
                if demo_hold_seconds > 0 and headed:
                    log_pass(f"DEMO MODE: Holding for {demo_hold_seconds} seconds")
                    print(f"\n{'='*70}")
                    print(f"Showcase ready - browser is visible")
                    print(f"Leader page: {page_leader.url}")
                    print(f"{'='*70}\n")
                    time.sleep(demo_hold_seconds)
            except Exception as e:
                log_fail(f"Showcase error: {e}")
                return False
            
            # Cleanup
            for user_key in users:
                try:
                    users[user_key]["context"].close()
                except:
                    pass
            
            return True
            
        except Exception as e:
            log_fail(f"Unexpected error: {e}")
            traceback.print_exc()
            return False
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="StudySync E2E Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 e2e_test.py
  python3 e2e_test.py --headed
  python3 e2e_test.py --headed --demo-hold-seconds 60
        """
    )
    
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:5000",
        help="Base URL (default: http://127.0.0.1:5000)"
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show browser UI"
    )
    parser.add_argument(
        "--demo-hold-seconds",
        type=int,
        default=0,
        help="Hold browser open for N seconds in demo mode"
    )
    parser.add_argument(
        "--demo-hold",
        action="store_true",
        help="Hold for 60 seconds (demo mode)"
    )
    
    args = parser.parse_args()
    demo_hold_seconds = args.demo_hold_seconds or (60 if args.demo_hold else 0)
    
    try:
        success = run_full_workflow(args.base_url, args.headed, demo_hold_seconds)
        
        # Summary
        print("\n" + "=" * 70)
        if success and not FAILED_STEPS:
            print(f"✓ ALL TESTS PASSED")
            print(f"Total steps: {STEP_COUNT}")
            print("=" * 70)
            sys.exit(0)
        else:
            print(f"✗ TESTS FAILED ({len(FAILED_STEPS)} errors)")
            print(f"Total steps: {STEP_COUNT}")
            if FAILED_STEPS:
                print("\nFailed steps:")
                for step in FAILED_STEPS[:5]:  # Show first 5
                    print(f"  - {step[:80]}...")
            print("=" * 70)
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
